from app.utils.config_loader import SETTINGS

if __name__ == "__main__":
    try:
        SETTINGS.validate()
        print(".env looks OK ✓")
        print(SETTINGS)
    except Exception as e:
        print(".env problem:", e)
