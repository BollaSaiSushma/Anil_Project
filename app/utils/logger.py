import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Create logs directory if it doesn't exist
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Define the log formatter
_formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Create a rotating file handler (max 2MB per file, keep 3 backups)
_handler = RotatingFileHandler(
    LOG_DIR / "app.log",
    maxBytes=2_000_000,
    backupCount=3
)
_handler.setFormatter(_formatter)

# Configure the logger
logger = logging.getLogger("dev_leads")
logger.setLevel(logging.INFO)
logger.addHandler(_handler)
logger.propagate = False
