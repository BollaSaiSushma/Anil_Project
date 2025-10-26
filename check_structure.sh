#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo "Checking project structure..."

# Required directories
directories=(
    "app"
    "app/scraper"
    "app/nlp"
    "app/geo"
    "app/classifier"
    "app/enrichment"
    "app/core"
    "app/integrations"
    "app/utils"
    "data"
    "data/maps"
    "data/zoning_shapefile"
    "data/logs"
    "logs"
)

# Required files
files=(
    ".env"
    ".env.example"
    "requirements.txt"
    "google_credentials.json"
    "main.py"
    "test_map_generator.py"
    "test_database.py"
    "test_alerts.py"
    "test_fastapi.py"
    "verify_env.py"
    "verify_structure.py"
)

# Check directories
for dir in "${directories[@]}"; do
    if [ -d "$dir" ]; then
        echo -e "${GREEN}✓${NC} Directory exists: $dir"
    else
        echo -e "${RED}✗${NC} Missing directory: $dir"
    fi
done

# Check files
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} File exists: $file"
    else
        echo -e "${RED}✗${NC} Missing file: $file"
    fi
done

# Check Python packages
echo -e "\nChecking Python packages..."
pip list | grep -E "pandas|numpy|requests|openai|gspread|folium|pytest"