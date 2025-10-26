from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv
import os

# Force reload environment variables
if 'OPENAI_API_KEY' in os.environ:
    del os.environ['OPENAI_API_KEY']

load_dotenv(override=True)

@dataclass
class Settings:
    serpapi_key: str = os.getenv("SERPAPI_API_KEY", "")
    openai_key: str = os.getenv("OPENAI_API_KEY", "")
    google_credentials_path: str = os.getenv("GOOGLE_CREDENTIALS_PATH", "./google_credentials.json")
    google_sheets_id: str = os.getenv("GOOGLE_SHEETS_ID", "")
    email_user: str = os.getenv("EMAIL_USER", "")
    email_password: str = os.getenv("EMAIL_PASSWORD", "")
    target_city: str = os.getenv("TARGET_CITY", "Newton, MA")
    database_path: str = os.getenv("DATABASE_PATH", "./data/development_leads.db")

    def validate(self) -> None:
        missing = []
        for k, v in self.__dict__.items():
            if k.endswith("_key") or k.endswith("_id") or k.endswith("_password"):
                if not v:
                    missing.append(k)
        if missing:
            raise ValueError(f"Missing critical settings: {', '.join(missing)}. Check your .env")


SETTINGS = Settings()
