"""
Zerodha Kite Connect - Connection Test
Run this to generate access_token for the day
"""

from kiteconnect import KiteConnect
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")

print(f"API Key: {api_key}")
print(f"API Secret: {api_secret[:5]}..." if api_secret else "API Secret: None")

kite = KiteConnect(api_key=api_key)

# Step 1: Print login URL
print("\n" + "="*50)
print("STEP 1: Open this URL in browser and login:")
print("="*50)
print(kite.login_url())
print("\nAfter login, you'll be redirected to a URL like:")
print("https://127.0.0.1/?request_token=XXXXX&action=login&status=success")
print("\nCopy the 'request_token' value from that URL")
print("="*50 + "\n")

# Step 2: After login, paste your request_token
request_token = input("Paste your request_token: ").strip()

# Step 3: Exchange for access token
if request_token:
    try:
        data = kite.generate_session(request_token, api_secret=api_secret)
        access_token = data["access_token"]
        print("\n" + "="*50)
        print("SUCCESS! Your Access Token:")
        print("="*50)
        print(access_token)
        print("\nUpdate your .env file with:")
        print(f'ACCESS_TOKEN = "{access_token}"')
        print("="*50)
        
        # Test the connection
        kite.set_access_token(access_token)
        profile = kite.profile()
        print(f"\nLogged in as: {profile['user_name']} ({profile['user_id']})")
        
    except Exception as e:
        print(f"\nError: {e}")
else:
    print("No request_token provided.")
