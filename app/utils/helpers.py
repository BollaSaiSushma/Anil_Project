from pathlib import Path
import pandas as pd

# Create data directories
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
(DATA_DIR / "maps").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "logs").mkdir(parents=True, exist_ok=True)

# Define file paths
RAW_CSV = DATA_DIR / "raw_listings.csv"
CLASSIFIED_CSV = DATA_DIR / "classified_listings.csv"
CLASSIFIED_JSON = DATA_DIR / "classified_listings.json"
DEV_LEADS_CSV = DATA_DIR / "development_leads.csv"
DB_PATH = DATA_DIR / "development_leads.db"
LATEST_MAP = DATA_DIR / "maps" / "latest_map.html"

# Helper function to safely write a DataFrame to CSV
def safe_write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8")
