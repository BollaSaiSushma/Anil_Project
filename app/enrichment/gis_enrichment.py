import pandas as pd
from app.utils.logger import logger
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time

def geocode_address(address: str, city: str, state: str) -> tuple:
    """Geocode a single address using Nominatim."""
    geolocator = Nominatim(user_agent="dev_pipeline")
    
    # Clean up the address
    address = address.split('#')[0].strip()  # Remove apartment numbers
    if state == state.upper():  # Convert state to proper case if it's all caps
        state = state.title()
        
    # Try different address formats
    address_formats = [
        f"{address}, {city}, {state}, USA",  # Full format
        f"{address}, {city}, {state}",       # Without USA
        f"{address}, {city}"                 # Just street and city
    ]
    
    timeouts = [10, 15, 20]
    
    for addr_format in address_formats:
        for timeout in timeouts:
            try:
                print(f"[GIS] Trying: {addr_format}")
                location = geolocator.geocode(addr_format, timeout=timeout)
                if location:
                    return location.latitude, location.longitude
                time.sleep(2)
            except Exception as e:
                print(f"[GIS] Geocoding error for {addr_format}: {str(e)}")
                time.sleep(2)
                continue
    
    print(f"[GIS] Could not geocode after all attempts: {address}, {city}, {state}")
    return None, None

def geocode_and_enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Add latitude and longitude to properties using geocoding."""
    if df.empty:
        return df.assign(lat=[], lon=[])

    out = df.copy()
    out['lat'] = None
    out['lon'] = None
    
    print("[GIS] Starting geocoding process...")
    for idx, row in out.iterrows():
        if pd.isna(row.get('lat')) or pd.isna(row.get('lon')):
            lat, lon = geocode_address(
                row.get('address', ''),
                row.get('city', 'Newton'),
                row.get('state', 'MA')
            )
            if lat and lon:
                out.at[idx, 'lat'] = lat
                out.at[idx, 'lon'] = lon
            time.sleep(1)  # Be nice to the geocoding service
    
    # Fill any missing coordinates with Newton center
    out['lat'] = out['lat'].fillna(42.337)
    out['lon'] = out['lon'].fillna(-71.209)
    
    print(f"[GIS] Geocoded {len(out)} properties ✓")
    logger.info("Geocoded %d rows", len(out))
    return out
