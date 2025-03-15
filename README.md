# Gym Tracking Dashboard

A Streamlit-based dashboard for tracking and visualizing gym progress, integrating data from Google Sheets and Garmin smartwatch.

## Features

- Weekly workout streak tracking
- Comprehensive workout statistics
- Progress visualization for key exercises
- Personal records tracking
- Integration with Google Sheets and Garmin data
- Customizable time period analysis

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up Google Sheets API:
   - Create a Google Cloud project
   - Enable Google Sheets API
   - Create service account credentials
   - Save the credentials as `credentials.json` in the project root
   - Share your workout tracking sheet with the service account email

3. Configure environment variables:
   - Create a `.env` file in the project root
   - Add your Google Sheet ID:
     ```
     SHEET_ID=your_sheet_id_here
     ```

## Running the Dashboard

```bash
streamlit run src/app.py
```

## Data Structure

### Google Sheets Format
- Date: YYYY-MM-DD
- Exercise: Exercise name
- Reps: Comma-separated list of repetitions
- Weight: Comma-separated list of weights

### Garmin Data Format
JSON format containing:
- Timestamp
- Duration
- Heart rate data
- Exercise categorization
