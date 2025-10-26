import pandas as pd
from datetime import datetime
from app.enrichment.data_enrichment import enrich_property_data
from app.core.price_tracker import price_tracker
from app.core.scheduler import scheduler
from app.utils.logger import logger

def test_all_components():
    print("=== Testing New Pipeline Components ===\n")
    
    # 1. Test Data Enrichment
    print("1. Testing Data Enrichment...")
    test_data = pd.DataFrame([
        {
            "address": "123 Test St",
            "city": "Newton",
            "state": "MA",
            "price": "750000",
            "living_area": "2000",
            "lot_sqft": "5000",
            "year_built": "1950",
            "description": "Great opportunity for builders! This property needs work and is perfect for redevelopment.",
            "list_date": "2025-10-20",
            "url": "https://example.com/property1"
        }
    ])
    
    enriched_data = enrich_property_data(test_data)
    print("\nEnriched Data Fields:")
    print(enriched_data.columns.tolist())
    print("\nSample Calculations:")
    print(f"Price per SF: ${enriched_data['price_per_sf'].iloc[0]:.2f}")
    print(f"Property Age: {enriched_data['property_age'].iloc[0]} years")
    print(f"Condition Keywords: {enriched_data['condition_keywords'].iloc[0]}")
    
    # 2. Test Price Tracking
    print("\n2. Testing Price Tracking...")
    tracked_data = price_tracker.track_price_changes(test_data)
    print("\nPrice Tracking Fields:")
    print(tracked_data.columns.tolist())
    
    # 3. Test Scheduler Setup
    print("\n3. Testing Scheduler...")
    try:
        scheduler.start()
        status = scheduler.get_status()
        print("\nScheduler Status:")
        print(f"Running: {status['running']}")
        print("\nScheduled Jobs:")
        for job in status['jobs']:
            print(f"- {job['name']}: Next run at {job['next_run']}")
        scheduler.stop()
        print("\nScheduler stopped successfully")
    except Exception as e:
        print(f"Scheduler test error: {e}")

if __name__ == "__main__":
    test_all_components()