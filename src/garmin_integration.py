import os
from datetime import datetime, timedelta
import pandas as pd
from garminconnect import Garmin
from dotenv import load_dotenv

load_dotenv()

class GarminDataLoader:
    def __init__(self):
        self.email = os.getenv('GARMIN_EMAIL')
        self.password = os.getenv('GARMIN_PASSWORD')
        self.garmin = None
        self.garth_home = os.getenv("GARTH_HOME", "~/.garth")

    def connect(self):
        """Initialize Garmin connection"""
        try:
            self.garmin = Garmin(self.email, self.password)
            self.garmin.login()
            self.garmin.garth.dump(self.garth_home)
            return True
        except Exception as e:
            print(f"Error connecting to Garmin: {str(e)}")
            return False

    def get_activities(self, start_date=None, end_date=None):
        """Get activities between dates"""
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")

        try:
            activities = self.garmin.get_activities_by_date(start_date, end_date)
            return self._process_activities(activities)
        except Exception as e:
            print(f"Error fetching activities: {str(e)}")
            return pd.DataFrame()

    def get_exercise_sets(self, activity_id):
        """Get exercise sets for a specific activity"""
        try:
            sets = self.garmin.get_activity_exercise_sets(activity_id)
            return self._process_exercise_sets(sets)
        except Exception as e:
            print(f"Error fetching exercise sets: {str(e)}")
            return pd.DataFrame()

    def _process_activities(self, activities):
        """Process raw activities data into a DataFrame"""
        processed_data = []
        
        for activity in activities:
            data = {
                'activity_id': activity.get('activityId'),
                'date': activity.get('startTimeLocal', '').split()[0],
                'name': activity.get('activityName'),
                'type': activity.get('activityType', {}).get('typeKey'),
                'duration': activity.get('duration'),
                'distance': activity.get('distance'),
                'avg_hr': activity.get('averageHR'),
                'max_hr': activity.get('maxHR'),
                'calories': activity.get('calories'),
                'avg_speed': activity.get('averageSpeed'),
                'max_speed': activity.get('maxSpeed'),
                'total_sets': activity.get('totalSets'),
                'total_reps': activity.get('totalReps')
            }
            processed_data.append(data)
        
        df = pd.DataFrame(processed_data)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
        return df

    def _process_exercise_sets(self, sets_data):
        """Process raw exercise sets data into a DataFrame"""
        if not sets_data or 'exerciseSets' not in sets_data:
            return pd.DataFrame()

        processed_sets = []
        for exercise_set in sets_data['exerciseSets']:
            for set_data in exercise_set.get('sets', []):
                data = {
                    'exercise_name': exercise_set.get('exerciseName'),
                    'exercise_category': exercise_set.get('category'),
                    'set_number': set_data.get('setNumber'),
                    'reps': set_data.get('repetitionCount'),
                    'weight': set_data.get('weightValue'),
                    'weight_unit': set_data.get('weightUnit'),
                    'duration': set_data.get('duration')
                }
                processed_sets.append(data)
        
        return pd.DataFrame(processed_sets)

    def get_combined_workout_data(self, start_date=None, end_date=None):
        """Get combined activities and exercise sets data"""
        activities_df = self.get_activities(start_date, end_date)
        if activities_df.empty:
            return pd.DataFrame()

        all_exercises = []
        for _, activity in activities_df.iterrows():
            if activity['type'] == 'STRENGTH_TRAINING':
                exercise_sets = self.get_exercise_sets(activity['activity_id'])
                if not exercise_sets.empty:
                    exercise_sets['date'] = activity['date']
                    exercise_sets['activity_id'] = activity['activity_id']
                    all_exercises.append(exercise_sets)

        if all_exercises:
            combined_df = pd.concat(all_exercises, ignore_index=True)
            # Convert weight to kg if in lbs
            mask = combined_df['weight_unit'] == 'POUND'
            combined_df.loc[mask, 'weight'] = combined_df.loc[mask, 'weight'] * 0.453592
            return combined_df
        return pd.DataFrame()
