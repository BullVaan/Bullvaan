import os
from kiteconnect import KiteConnect
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")

kite = KiteConnect(api_key=api_key)

print("1. Go to this URL and login:")
print(kite.login_url())

request_token = input("\n2. Paste the request_token from the URL after login: ")

data = kite.generate_session(request_token, api_secret=api_secret)

print("\nYour new access_token:")
print(data["access_token"])
print("\nSave this in your .env as ACCESS_TOKEN=")
