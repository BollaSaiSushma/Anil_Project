from pathlib import Path

expected = [
    "app/scraper/realtor_scraper.py",
    "app/nlp/openai_classifier.py",
    "app/integrations/map_generator.py",
    "data/maps",
]

missing = [p for p in expected if not Path(p).exists()]
print("Missing:" if missing else "All good ✓", missing)
