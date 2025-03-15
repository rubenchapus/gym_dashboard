import os
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

def test_google_sheets_connection():
    """Test the connection to Google Sheets"""
    print("Testing Google Sheets connection...")
    
    try:
        # Load environment variables
        load_dotenv()
        sheet_id = os.getenv('SHEET_ID')
        worksheet_name = os.getenv('WORKSHEET_NAME', 'Workouts')
        
        # Set up credentials
        scope = ['https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            'credentials/credentials.json', scope)
        
        # Connect to Google Sheets
        client = gspread.authorize(creds)
        print("✓ Successfully authenticated")
        
        # Open the spreadsheet
        sheet = client.open_by_key(sheet_id)
        print(f"✓ Successfully opened spreadsheet: {sheet.title}")
        
        # Check if worksheet exists, create if it doesn't
        try:
            worksheet = sheet.worksheet(worksheet_name)
            print(f"✓ Successfully accessed worksheet: {worksheet_name}")
        except gspread.WorksheetNotFound:
            print(f"Creating new worksheet: {worksheet_name}")
            worksheet = sheet.add_worksheet(worksheet_name, rows=1000, cols=20)
            
            # Add headers
            headers = ['Date', 'Exercise', 'Reps', 'Weight']
            worksheet.append_row(headers)
            
            # Add sample data
            sample_data = [
                ['2025-03-14', 'Bench Press', '8,8,6,6', '135,155,175,175'],
                ['2025-03-14', 'Squat', '10,8,8', '185,225,225'],
                ['2025-03-14', 'Pull Ups', '12,10,8', 'Body,Body,Body'],
                ['2025-03-15', 'Deadlift', '5,5,5', '225,275,315'],
                ['2025-03-15', 'Shoulder Press', '8,8,6', '95,115,115']
            ]
            for row in sample_data:
                worksheet.append_row(row)
            print("✓ Added sample data to worksheet")
        
        # Read the data
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        print("\nWorksheet contents:")
        print(df.head())
        
        print("\n✅ All connection tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    test_google_sheets_connection()
