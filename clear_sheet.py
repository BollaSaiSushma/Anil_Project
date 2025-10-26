import gspread
from google.oauth2.service_account import Credentials
from app.utils.config_loader import SETTINGS

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def clear_sheet_data():
    """Clear all data from the sheet except headers."""
    try:
        # Initialize Google Sheets client
        creds = Credentials.from_service_account_file(
            SETTINGS.google_credentials_path, scopes=SCOPES
        )
        gc = gspread.authorize(creds)
        
        # Open the spreadsheet
        print(f"[Sheets] Opening spreadsheet: {SETTINGS.google_sheets_id}")
        sh = gc.open_by_key(SETTINGS.google_sheets_id)
        
        # Access the DevelopmentLeads worksheet
        ws = sh.worksheet("DevelopmentLeads")
        
        # Get the current headers
        headers = ws.row_values(1)
        print(f"[Sheets] Found headers: {headers}")
        
        # Clear everything except the first row
        ws.resize(rows=1)  # Resize to just the header row
        ws.resize(rows=1000)  # Resize back to have empty rows
        
        print("[Sheets] Successfully cleared data while preserving headers ✓")
        
    except Exception as e:
        print(f"[Sheets] Error clearing sheet: {str(e)}")

if __name__ == "__main__":
    clear_sheet_data()