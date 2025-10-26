import pandas as pd
from app.scraper.fetch_properties import fetch_redfin
from app.utils.config_loader import SETTINGS

def debug_data_flow():
    print("=== Debugging Data Flow ===\n")
    
    # 1. Test Redfin scraper directly
    print("1. Testing Redfin scraper...")
    redfin_df = fetch_redfin(SETTINGS.target_city)
    print("\nRedfin Data Columns:")
    print(redfin_df.columns.tolist())
    print("\nFirst row:")
    if not redfin_df.empty:
        row = redfin_df.iloc[0]
        print(f"Address: {row.get('address', 'Missing')}")
        print(f"Beds: {row.get('beds', 'Missing')}")
        print(f"Baths: {row.get('baths', 'Missing')}")
        print(f"Lot sqft: {row.get('lot_sqft', 'Missing')}")
    
    # Save raw data for inspection
    redfin_df.to_csv("debug_redfin.csv", index=False)
    print("\nSaved debug data to debug_redfin.csv")

if __name__ == "__main__":
    debug_data_flow()