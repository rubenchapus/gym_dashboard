import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import os
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from garmin_integration import GarminDataLoader

# Load environment variables
load_dotenv()

# Page config
st.set_page_config(
    page_title="Gym Routine Tracker",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stat-card {
        padding: 20px;
        border-radius: 10px;
        background-color: #f0f2f6;
        text-align: center;
        margin: 5px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
    .big-number {
        font-size: 32px;
        font-weight: 700;
        color: #0068c9;
        margin: 10px 0;
    }
    .stat-label {
        font-size: 16px;
        color: #555;
        font-weight: 500;
    }
    .trend-positive {
        color: #28a745;
        font-size: 14px;
    }
    .trend-negative {
        color: #dc3545;
        font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def load_garmin_data(start_date=None, end_date=None):
    """Load data from Garmin Connect"""
    garmin_loader = GarminDataLoader()
    if not garmin_loader.connect():
        st.error("Failed to connect to Garmin. Check your credentials.")
        return pd.DataFrame()
    return garmin_loader.get_combined_workout_data(start_date, end_date)

@st.cache_data(ttl=3600)
def load_sheet_data():
    """Load and process Google Sheets data"""
    try:
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            'credentials/credentials.json', scope)
        client = gspread.authorize(creds)
        
        sheet = client.open_by_key(os.getenv('SHEET_ID')).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Clean column names
        df.columns = [col.strip().replace('\t', '') for col in df.columns]
        
        # Convert date format
        df['date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y')
        
        def parse_reps(x):
            if pd.isna(x) or str(x).strip() == '':
                return []
            return [int(r.strip()) for r in str(x).split(';') if r.strip().isdigit()]
        
        def parse_weights(x, num_sets):
            if pd.isna(x) or str(x).strip() == '':
                return []
            
            weights = []
            weight_items = str(x).split(';')
            
            # If there's just a single 'Body' value and multiple sets
            if len(weight_items) == 1 and 'body' in weight_items[0].lower() and num_sets > 1:
                base_weight = 70  # Default body weight
                if 'band' in weight_items[0].lower():
                    return [base_weight + 10] * num_sets  # Body weight + band resistance for each set
                else:
                    return [base_weight] * num_sets  # Just body weight for each set
            
            # Normal processing for multiple weights or non-body weight cases
            for w in weight_items:
                w = w.strip().lower()
                if 'body' in w:
                    base_weight = 120  # Default body weight is 2/3 my body weight in LBS
                    if 'band' in w:
                        weights.append(base_weight + 10)  # Body weight + band resistance
                    else:
                        weights.append(base_weight)
                elif w.replace('.', '').isdigit():
                    weights.append(float(w))
            
            return weights
        
        # Count sets (number of comma-separated values in Reps)
        df['sets'] = df['Reps'].apply(lambda x: len(str(x).split(';')) if not pd.isna(x) and str(x).strip() != '' else 0)
        
        # Process reps
        df['reps_list'] = df['Reps'].apply(parse_reps)
        
        # Process weights with set count information
        df['weights_list'] = df.apply(lambda row: parse_weights(row['Weight'], row['sets']), axis=1)
        
        # Calculate volume
        df['volume_per_set'] = df.apply(
            lambda row: [r * w for r, w in zip(row['reps_list'], row['weights_list'])],
            axis=1
        )
        df['total_volume'] = df['volume_per_set'].apply(sum)
        df['max_weight'] = df['weights_list'].apply(lambda x: max(x) if x else 0)
        
        # Handle time data if present
        if 'Time seconds' in df.columns:
            df['duration'] = pd.to_numeric(df['Time seconds'], errors='coerce').fillna(0)
        
        return df
    except Exception as e:
        st.error(f"Error loading Google Sheets data: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_combined_data(data_sources, time_period, start_date=None, end_date=None):
    """Load and combine data from selected sources"""
    workout_data = pd.DataFrame()
    
    if "Google Sheets" in data_sources:
        sheets_data = load_sheet_data()
        if not sheets_data.empty:
            workout_data = sheets_data
    
    if "Garmin Connect" in data_sources:
        try:
            if time_period == "Custom":
                garmin_data = load_garmin_data(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            else:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=time_period)
                garmin_data = load_garmin_data(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            
            if not garmin_data.empty:
                if not workout_data.empty:
                    workout_data = combine_workout_data(workout_data, garmin_data)
                else:
                    workout_data = garmin_data
        except Exception as e:
            st.sidebar.error(f"Error loading Garmin data: {str(e)}")
    
    return workout_data

def calculate_streak(df):
    """Calculate workout streak"""
    df['week'] = df['date'].dt.isocalendar().week
    df['year'] = df['date'].dt.isocalendar().year
    weekly_counts = df.groupby(['year', 'week']).size().reset_index(name='workout_count')
    
    streak = 0
    current_streak = 0
    for _, row in weekly_counts.sort_values(['year', 'week']).iterrows():
        if row['workout_count'] >= 5:
            current_streak += 1
            streak = max(streak, current_streak)
        else:
            current_streak = 0
    
    return streak, weekly_counts

def create_streak_visualization(weekly_counts):
    """Create streak visualization"""
    fig = go.Figure()
    
    # Add bars for workout counts
    fig.add_trace(go.Bar(
        x=weekly_counts.apply(lambda x: f"{x['year']}-W{x['week']}", axis=1),
        y=weekly_counts['workout_count'],
        marker_color=weekly_counts['workout_count'].apply(
            lambda x: '#28a745' if x >= 5 else '#dc3545'
        ),
        name='Workouts'
    ))
    
    fig.update_layout(
        title='Weekly Workout Streak',
        xaxis_title='Week',
        yaxis_title='Set Count',
        height=300
    )
    
    return fig

def create_progress_chart(df, exercise_name):
    """Create progress chart for specific exercise"""
    if df.empty or exercise_name not in df['Exercise'].unique():
        return None
        
    exercise_data = df[df['Exercise'] == exercise_name].copy()
    
    # Create figure with secondary y-axis
    fig = go.Figure()
    
    # Add weight progress
    fig.add_trace(
        go.Scatter(
            x=exercise_data['date'],
            y=exercise_data['max_weight'],
            name='Max Weight',
            line=dict(color='#0068c9', width=2)
        )
    )
    
    # Add volume progress on secondary axis
    fig.add_trace(
        go.Scatter(
            x=exercise_data['date'],
            y=exercise_data['total_volume'],
            name='Total Volume',
            yaxis='y2',
            line=dict(color='#28a745', width=2, dash='dot')
        )
    )
    
    # Update layout with secondary y-axis
    fig.update_layout(
        title=f'{exercise_name} Progress',
        xaxis_title='Date',
        yaxis_title='Max Weight (lbs)',
        yaxis2=dict(
            title='Total Volume',
            overlaying='y',
            side='right'
        ),
        height=400,
        showlegend=True,
        legend=dict(
            yanchor='top',
            y=0.99,
            xanchor='left',
            x=0.01
        ),
        hovermode='x unified'
    )
    
    return fig

def calculate_pr_table(df):
    """Calculate personal records table"""
    prs = []
    
    for exercise in df['Exercise'].unique():
        exercise_df = df[df['Exercise'] == exercise]
        
        for _, row in exercise_df.iterrows():
            for reps, weight in zip(row['reps_list'], row['weights_list']):
                prs.append({
                    'Exercise': exercise,
                    'Reps': reps,
                    'Weight': weight,
                    'Date': row['date']
                })
    
    pr_df = pd.DataFrame(prs)
    pr_df['Volume'] = pr_df['Reps'] * pr_df['Weight']
    
    # Get max weight for different rep ranges
    max_weight_prs = pr_df.sort_values('Weight', ascending=False).groupby('Exercise').first()
    max_volume_prs = pr_df.sort_values('Volume', ascending=False).groupby('Exercise').first()
    
    return max_weight_prs, max_volume_prs

def combine_workout_data(sheets_df, garmin_df):
    """Combine data from Google Sheets and Garmin"""
    if garmin_df.empty:
        return sheets_df
        
    # Process Garmin data to match sheets format
    garmin_processed = garmin_df.copy()
    garmin_processed = garmin_processed.rename(columns={
        'exercise_name': 'Exercise',
        'weight': 'Weight',
        'reps': 'Reps'
    })
    
    # Convert weights and reps to lists format
    garmin_processed['weights_list'] = garmin_processed['Weight'].apply(lambda x: [float(x)] if pd.notnull(x) else [])
    garmin_processed['reps_list'] = garmin_processed['Reps'].apply(lambda x: [int(x)] if pd.notnull(x) else [])
    
    # Calculate volume
    garmin_processed['volume_per_set'] = garmin_processed.apply(
        lambda row: [r * w for r, w in zip(row['reps_list'], row['weights_list'])],
        axis=1
    )
    garmin_processed['total_volume'] = garmin_processed['volume_per_set'].apply(sum)
    garmin_processed['max_weight'] = garmin_processed['weights_list'].apply(lambda x: max(x) if x else 0)
    
    # Combine dataframes
    combined_df = pd.concat([sheets_df, garmin_processed[[col for col in sheets_df.columns if col in garmin_processed.columns]]], 
                          ignore_index=True)
    
    # Sort by date and remove duplicates
    combined_df = combined_df.sort_values('date').drop_duplicates(
        subset=['date', 'Exercise', 'Reps', 'Weight'], 
        keep='last'
    )
    
    return combined_df

def main():
    st.title("💪 Gym Routine Tracker")
    
    # Data source selector in sidebar
    st.sidebar.header("Data Sources")
    data_sources = st.sidebar.multiselect(
        "Select Data Sources",
        ["Google Sheets", "Garmin Connect"],
        default=["Google Sheets"]
    )
    
    # Time period selector
    st.sidebar.header("Time Period")
    time_options = {
        "Last 7 days": 7,
        "Last 30 days": 30,
        "Last 90 days": 90,
        "Custom": 0
    }
    
    selected_time = st.sidebar.selectbox("Select Time Period", list(time_options.keys()))
    
    # Date range selector for custom time period
    if selected_time == "Custom":
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input("Start Date", datetime.now() - timedelta(days=30))
        with col2:
            end_date = st.date_input("End Date", datetime.now())
    else:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=time_options[selected_time])
    
    # Load data from selected sources
    workout_data = load_combined_data(
        data_sources,
        "Custom" if selected_time == "Custom" else time_options[selected_time],
        start_date,
        end_date
    )
    
    if workout_data.empty:
        st.warning("No workout data available. Please check your data source connections.")
        return
        
    # Filter data based on selected time period
    filtered_data = workout_data[
        (workout_data['date'].dt.date >= start_date.date()) &
        (workout_data['date'].dt.date <= end_date.date())
    ].copy()
    

    
    # Load data from selected sources
    workout_data = pd.DataFrame()
    
    if "Google Sheets" in data_sources:
        sheets_data = load_sheet_data()
        workout_data = sheets_data
    
    if "Garmin Connect" in data_sources:
        try:
            if selected_time == "Custom":
                garmin_data = load_garmin_data(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            else:
                days = time_options[selected_time]
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
                garmin_data = load_garmin_data(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            
            if not garmin_data.empty:
                if not workout_data.empty:
                    workout_data = combine_workout_data(workout_data, garmin_data)
                else:
                    workout_data = garmin_data
        except Exception as e:
            st.sidebar.error(f"Error loading Garmin data: {str(e)}")
    
    if workout_data.empty:
        st.warning("No workout data available. Please check your data source connections.")
        return
    
    # Time period selector
    time_options = {
        'This Week': 7,
        'Last Week': 14,
        'This Month': 30,
        'Last Month': 60,
        'This Quarter': 90,
        'Last Quarter': 180,
        'This Year (YTD)': 365,
        'Custom Range': -1
    }
    
    selected_time = st.selectbox('Select Time Period', list(time_options.keys()))
    
    if selected_time == 'Custom Range':
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input('Start Date')
        with col2:
            end_date = st.date_input('End Date')
        
        filtered_data = workout_data[
            (workout_data['date'].dt.date >= start_date) &
            (workout_data['date'].dt.date <= end_date)
        ]
    else:
        days = time_options[selected_time]
        filtered_data = workout_data[
            workout_data['date'] >= (datetime.now() - timedelta(days=days))
        ]
    
    # Calculate metrics
    streak_count, weekly_counts = calculate_streak(filtered_data)
    
    # Top section - Key stats
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">Workout Streak</div>
            <div class="big-number">{streak_count} weeks</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        workout_count = len(filtered_data)
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">Sets</div>
            <div class="big-number">{workout_count}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        total_volume = filtered_data['total_volume'].sum()
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">Total Volume (lbs)</div>
            <div class="big-number">{total_volume:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        avg_exercises = filtered_data.groupby('date')['Exercise'].count().mean() if not filtered_data.empty else 0
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">Avg Exercises/Session</div>
            <div class="big-number">{avg_exercises:.1f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Streak visualization
    st.plotly_chart(create_streak_visualization(weekly_counts), use_container_width=True)
    
    # Exercise progress section
    st.subheader("Exercise Progress")
    
    # Add exercise type filter
    exercise_types = {
        'All': filtered_data['Exercise'].unique(),
        'Upper Body': ['Bench Press', 'Shoulder Press', 'Pull Ups', 'Push Ups', 'Standing Cable Fly'],
        'Lower Body': ['Squat', 'Deadlift', 'Leg Press', 'Lunges'],
        'Core': ['Incline Abs', 'Plank', 'Russian Twists']
    }
    
    col1, col2 = st.columns([1, 3])
    with col1:
        selected_type = st.selectbox("Exercise Type", list(exercise_types.keys()))
    
    with col2:
        available_exercises = exercise_types[selected_type] if selected_type != 'All' else filtered_data['Exercise'].unique()
        selected_exercise = st.selectbox(
            "Select Exercise",
            sorted([ex for ex in available_exercises if ex in filtered_data['Exercise'].unique()])
        )
    
    progress_chart = create_progress_chart(filtered_data, selected_exercise)
    if progress_chart:
        st.plotly_chart(progress_chart, use_container_width=True)
    else:
        st.info("No data available for the selected exercise in the current time period.")
    
    # Personal records section
    st.subheader("Personal Records")
    max_weight_prs, max_volume_prs = calculate_pr_table(filtered_data)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Max Weight PRs")
        st.dataframe(max_weight_prs[['Weight', 'Reps', 'Date']])
    
    with col2:
        st.markdown("#### Max Volume PRs")
        st.dataframe(max_volume_prs[['Volume', 'Reps', 'Weight', 'Date']])
    
    # show data source
    st.subheader("Data Source")
    st.dataframe(filtered_data)

if __name__ == "__main__":
    main()
