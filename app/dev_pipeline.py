import pandas as pd
import numpy as np
from app.scraper.fetch_properties import fetch_redfin, fetch_zillow, fetch_realtor
from app.classifier.llm_classifier import run_classifier
from app.integrations.database_manager import upsert_leads, init_db
from app.integrations.google_sheets_uploader import upload_dataframe
from app.integrations.map_generator import create_map
from app.integrations.alerts import send_alert
from app.integrations.roi_calculator import enrich_with_roi
from app.utils.helpers import safe_write_csv
from app.utils.config_loader import SETTINGS
from app.utils.logger import logger


# File paths
CLASSIFIED_CSV = "./data/classified_listings.csv"
DEV_LEADS_CSV = "./data/development_leads.csv"


def run_pipeline(mode="full"):
    """
    Run the property pipeline
    :param mode: 'full' for complete run, 'price_update' for price-only check
    """
    logger.info("Starting property pipeline for %s (mode=%s)", SETTINGS.target_city, mode)

    # --- STAGE 1: SCRAPE DATA ---
    redfin_df = fetch_redfin(SETTINGS.target_city)
    zillow_df = fetch_zillow(SETTINGS.target_city)
    realtor_df = fetch_realtor(SETTINGS.target_city)


    print(f"[redfin] {len(redfin_df)} rows")
    print(f"[zillow] {len(zillow_df)} rows")
    print(f"[realtor] {len(realtor_df)} rows")

    all_data = pd.concat([redfin_df, zillow_df, realtor_df], ignore_index=True)
    all_data.replace([pd.NA, np.nan, np.inf, -np.inf], "", inplace=True)

    if all_data.empty:
        logger.warning("No property data found. Check scrapers or network issues.")
        send_alert("Pipeline Failed", "No property listings found in any source.")
        return

    # --- STAGE 2: NLP CLASSIFICATION ---
    print("Running NLP LLM classification...")
    classified = run_classifier(all_data)
    classified.replace([pd.NA, np.nan, np.inf, -np.inf], "", inplace=True)
    safe_write_csv(classified, CLASSIFIED_CSV)
    print(f"Classified properties saved to {CLASSIFIED_CSV}")

    # --- STAGE 3: ROI & ENRICHMENT ---
    print("Calculating ROI and enrichment metrics...")
    
    # First geocode the properties
    from app.enrichment.gis_enrichment import geocode_and_enrich
    print("Geocoding properties...")
    with_geo = geocode_and_enrich(classified)
    
    # Then calculate ROI
    with_roi = enrich_with_roi(with_geo)

    # --- STAGE 4: SAVE LEADS & CLEANUP ---
    safe_write_csv(with_roi, DEV_LEADS_CSV)

    # Clean invalid entries before upload
    if with_roi is not None and hasattr(with_roi, "replace"):
        with_roi = with_roi.replace([pd.NA, np.nan, np.inf, -np.inf], "")
    else:
        print("No DataFrame produced for with_roi; skipping upload.")

    # Ensure essential property details are included
    essential_columns = ["address", "beds", "baths", "lot_sqft", "price", "url"]
    for col in essential_columns:
        if col not in with_roi.columns and col in classified.columns:
            with_roi[col] = classified[col]

    # Limit long text fields for Google Sheets
    max_len = 49000
    for col in ["snippet", "llm_reason", "description"]:
        if col in with_roi.columns:
            with_roi[col] = with_roi[col].astype(str).str.slice(0, max_len)

    # --- STAGE 5: GOOGLE SHEETS UPLOAD ---
    try:
        upload_dataframe(with_roi)
        logger.info("Uploaded data to Google Sheets successfully.")
    except Exception as e:
        logger.error("Google Sheets upload failed: %s", e)
        send_alert("Upload Failure", f"Google Sheets upload failed: {e}")


    # --- STAGE 6: DATABASE SYNC ---
    init_db()
    inserted = upsert_leads(with_roi)
    logger.info("Database updated. Rows inserted: %s", inserted)

    # --- STAGE 7: MAP CREATION ---
    try:
        # Get data from Google Sheets to ensure map matches exactly
        from app.integrations.google_sheets_uploader import get_sheet_data
        sheet_data = get_sheet_data()
        if sheet_data is not None and not sheet_data.empty:
            map_path = create_map(sheet_data)
            logger.info("Map created at %s", map_path)
        else:
            map_path = None
            logger.warning("No data found in Google Sheets for map creation")
    except Exception as e:
        map_path = None
        logger.warning("Map generation failed: %s", e)

    # --- STAGE 8: FINAL ALERT ---
    send_alert(
        "Pipeline Completed",
        f"Processed {len(with_roi)} rows; inserted {inserted}; map at {map_path or 'N/A'}"
    )

    logger.info(
        "Pipeline completed successfully: rows=%s, inserted=%s, map=%s",
    )
