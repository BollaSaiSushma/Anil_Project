from app.utils.config_loader import SETTINGS

def main():
    print("Checking environment variables:")
    print(f"OpenAI API Key exists: {bool(SETTINGS.openai_key)}")
    print(f"OpenAI API Key: {SETTINGS.openai_key[:10]}... (truncated)")
    print(f"Google Sheets ID: {SETTINGS.google_sheets_id}")
    print(f"Target City: {SETTINGS.target_city}")
    
    try:
        SETTINGS.validate()
        print("\nAll required settings are present!")
    except ValueError as e:
        print("\nMissing settings:", e)

if __name__ == "__main__":
    main()