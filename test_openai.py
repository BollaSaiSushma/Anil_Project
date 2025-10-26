from openai import OpenAI
from app.utils.config_loader import SETTINGS
import os

def debug_env_variables():
    print("=== Environment Variables Debug ===")
    print("1. Direct environment check:")
    print(f"OPENAI_API_KEY in os.environ: {'OPENAI_API_KEY' in os.environ}")
    
    print("\n2. Settings object check:")
    print(f"OPENAI_API_KEY in SETTINGS: {bool(SETTINGS.openai_key)}")
    print(f"SETTINGS.openai_key value: {SETTINGS.openai_key if SETTINGS.openai_key else 'None'}")
    
    print("\n3. Current working directory:")
    print(f"CWD: {os.getcwd()}")
    
    print("\n4. .env file check:")
    env_path = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_path):
        print(f".env file exists at: {env_path}")
        with open(env_path, 'r') as f:
            lines = f.readlines()
            print("\nContent of .env file:")
            for line in lines:
                if line.strip() and not line.strip().startswith('#'):
                    key = line.split('=')[0]
                    print(f"{key}={'*' * 10}")  # Show keys but mask values
    else:
        print(".env file not found!")

def test_openai_connection():
    print("\n=== OpenAI API Test ===")
    if not SETTINGS.openai_key:
        print("❌ No OpenAI API key found in settings!")
        return
        
    try:
        # Initialize the client
        client = OpenAI(api_key=SETTINGS.openai_key)
        
        # Try a simple completion
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "user",
                "content": "Please respond with 'OpenAI API is working correctly' if you receive this message."
            }],
            max_tokens=50
        )
        
        # Get the response
        result = response.choices[0].message.content
        print("\n✅ API Test Successful!")
        print("Response received:", result)
        print("\nAPI connection is working properly.")
        
    except Exception as e:
        print("\n❌ API Test Failed!")
        print("Error:", str(e))
        print("\nPlease check your API key and internet connection.")

if __name__ == "__main__":
    debug_env_variables()
    test_openai_connection()