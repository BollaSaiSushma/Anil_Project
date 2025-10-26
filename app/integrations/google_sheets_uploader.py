import gspread
import numpy as np
import pandas as pd
from google.oauth2.service_account import Credentials
from app.utils.config_loader import SETTINGS

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def _client():
    creds = Credentials.from_service_account_file(
        SETTINGS.google_credentials_path, scopes=SCOPES
    )
    return gspread.authorize(creds)

def _sanitize_for_sheets(df: pd.DataFrame) -> list[list]:
    """
    Convert NaN/NA/Inf to empty strings so the JSON body is compliant.
    """
    safe = df.copy()

    # Replace NaN/NA/Inf/-Inf with empty string
    safe = safe.replace([pd.NA, np.nan, np.inf, -np.inf], "")

    # Ensure we don't send numpy types that JSON can’t handle
    # (object dtype preserves strings and numbers; empty cells become "")
    safe = safe.astype(object)

    # Convert to list-of-lists for gspread
    values = [safe.columns.tolist()] + safe.values.tolist()
    return values

def get_sheet_data(sheet_name: str = "DevelopmentLeads") -> pd.DataFrame:
    """Get data from Google Sheets as a DataFrame."""
    print(f"[Sheets] Fetching data from '{sheet_name}' worksheet...")
    
    try:
        gc = _client()
        sh = gc.open_by_key(SETTINGS.google_sheets_id)
        ws = sh.worksheet(sheet_name)
        
        # Get all values including headers
        all_values = ws.get_all_values()
        if not all_values:
            print("[Sheets] Sheet is empty.")
            return pd.DataFrame()
            
        # Convert to DataFrame using first row as headers
        df = pd.DataFrame(all_values[1:], columns=all_values[0])
        
        # Convert numeric columns
        numeric_cols = ['price', 'beds', 'baths', 'lot_sqft', 'lat', 'lon']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        print(f"[Sheets] Successfully fetched {len(df)} rows ✓")
        return df
        
    except Exception as e:
        print(f"[Sheets] Error fetching sheet data: {str(e)}")
        return pd.DataFrame()

def clear_sheet_data(sheet_name: str = "DevelopmentLeads"):
    """Clear all data rows from the sheet while preserving headers."""
    print(f"[Sheets] Clearing data from '{sheet_name}' worksheet...")
    
    try:
        gc = _client()
        sh = gc.open_by_key(SETTINGS.google_sheets_id)
        ws = sh.worksheet(sheet_name)
        
        # Get all values to find where data starts
        all_values = ws.get_all_values()
        if not all_values:
            print("[Sheets] Sheet is already empty.")
            return
            
        # Keep the header row
        headers = all_values[0]
        
        # Clear everything after the header row
        if len(all_values) > 1:
            # Calculate the range to clear (A2:ZZ999999)
            last_col = chr(ord('A') + len(headers) - 1)  # Convert number to letter
            range_to_clear = f'A2:{last_col}{len(all_values)}'
            
            # Clear the range
            ws.batch_clear([range_to_clear])
            print(f"[Sheets] Successfully cleared data rows, preserved headers ✓")
        else:
            print("[Sheets] No data rows to clear.")
            
    except Exception as e:
        print(f"[Sheets] Error clearing sheet: {str(e)}")
        raise

def upload_dataframe(df: pd.DataFrame, sheet_name: str = "DevelopmentLeads"):
    print(f"[Sheets] Spreadsheet ID: {SETTINGS.google_sheets_id}")
    if df is None or df.empty:
        print("[Sheets] DataFrame is empty — skipping upload.")
        return

    gc = _client()
    sh = gc.open_by_key(SETTINGS.google_sheets_id)

    try:
        ws = sh.worksheet(sheet_name)
        # Instead of clearing everything, only clear data rows
        clear_sheet_data(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        rows = max(len(df) + 10, 100)
        cols = max(len(df.columns) + 2, 10)
        ws = sh.add_worksheet(title=sheet_name, rows=str(rows), cols=str(cols))

    values = _sanitize_for_sheets(df)
    ws.update(values)
    print(f"[Sheets] Uploaded {len(df)} rows to '{sheet_name}' ✓")
