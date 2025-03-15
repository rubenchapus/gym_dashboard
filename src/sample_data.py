import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_sample_workout_data(days=90):
    """Generate sample workout data for testing"""
    start_date = datetime.now() - timedelta(days=days)
    dates = []
    exercises = []
    reps = []
    weights = []
    
    # Common exercises with typical weight ranges
    exercise_configs = {
        'Bench Press': (135, 225),
        'Squat': (185, 315),
        'Deadlift': (225, 405),
        'Shoulder Press': (95, 155),
        'Barbell Row': (135, 225),
        'Pull Ups': ('Body', 'Body'),
        'Push Ups': ('Body', 'Body')
    }
    
    # Generate 4-5 workouts per week
    current_date = start_date
    while current_date < datetime.now():
        # Skip some days to simulate rest days
        if np.random.random() > 0.6:  # 60% chance of workout on any day
            current_date += timedelta(days=1)
            continue
            
        # Add 3-5 exercises per workout
        num_exercises = np.random.randint(3, 6)
        selected_exercises = np.random.choice(list(exercise_configs.keys()), num_exercises, replace=False)
        
        for exercise in selected_exercises:
            min_weight, max_weight = exercise_configs[exercise]
            
            # Generate 3-4 sets per exercise
            num_sets = np.random.randint(3, 5)
            
            if min_weight == 'Body':
                weight_list = ['Body'] * num_sets
                rep_list = [np.random.randint(8, 15) for _ in range(num_sets)]
            else:
                # Add some progression over time
                progress_factor = (current_date - start_date).days / days
                weight_range = max_weight - min_weight
                current_max = min_weight + (weight_range * progress_factor * 0.7)  # 70% of potential progress
                
                weight_list = [round(np.random.uniform(min_weight, current_max)) for _ in range(num_sets)]
                rep_list = [np.random.randint(5, 13) for _ in range(num_sets)]
            
            dates.append(current_date)
            exercises.append(exercise)
            reps.append(','.join(map(str, rep_list)))
            weights.append(','.join(map(str, weight_list)))
        
        current_date += timedelta(days=1)
    
    return pd.DataFrame({
        'Date': dates,
        'Exercise': exercises,
        'Reps': reps,
        'Weight': weights
    })

def generate_sample_garmin_data(workout_dates):
    """Generate sample Garmin data matching workout dates"""
    garmin_data = []
    
    for date in workout_dates:
        # Generate realistic workout duration (30-90 minutes)
        duration = np.random.randint(30, 91) * 60  # convert to seconds
        moving_duration = int(duration * np.random.uniform(0.85, 0.95))  # 85-95% of total duration
        
        # Generate heart rate data
        avg_hr = np.random.randint(130, 160)
        max_hr = avg_hr + np.random.randint(20, 40)
        
        # Generate time in different HR zones (total should equal duration)
        zone_times = np.random.dirichlet(np.array([1, 2, 3, 2, 1])) * duration
        
        garmin_data.append({
            'timestamp': date.timestamp(),
            'duration': duration,
            'moving_duration': moving_duration,
            'avg_hr': avg_hr,
            'max_hr': max_hr,
            'hr_zone_1': zone_times[0],
            'hr_zone_2': zone_times[1],
            'hr_zone_3': zone_times[2],
            'hr_zone_4': zone_times[3],
            'hr_zone_5': zone_times[4],
            'calories': np.random.randint(300, 600)
        })
    
    return pd.DataFrame(garmin_data)

if __name__ == "__main__":
    # Generate sample data
    workout_df = generate_sample_workout_data()
    garmin_df = generate_sample_garmin_data(workout_df['Date'].unique())
    
    # Save to CSV for testing
    workout_df.to_csv('sample_workout_data.csv', index=False)
    garmin_df.to_csv('sample_garmin_data.csv', index=False)
