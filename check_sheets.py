import gspread
from google.oauth2.service_account import Credentials
from app.utils.config_loader import SETTINGS

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def check_sheets_content():
    creds = Credentials.from_service_account_file(
        SETTINGS.google_credentials_path, scopes=SCOPES
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SETTINGS.google_sheets_id)
    worksheet = sh.worksheet("DevelopmentLeads")
    
    # Get all values including headers
    values = worksheet.get_all_values()
    
    # Print headers
    print("\nHeaders:", values[0])
    print("\nFirst few rows:")
    # Print first 3 rows of data
    for row in values[1:4]:
        print(row)

if __name__ == "__main__":
    check_sheets_content()