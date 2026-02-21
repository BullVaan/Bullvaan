from kiteconnect import KiteConnect
from fastapi import FastAPI, Query
import re

app = FastAPI()

# Zerodha credentials (move to env vars in production)
API_KEY = "yi4arzszbdqujyt0"
API_SECRET = "sqbpnp0s1li9cwal29j2nsntuh0c52kw"
ACCESS_TOKEN = "XhXpuBnfsrPsZNGbq50yRMvLMh8MVXsS"

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

# Helper to parse option input to Zerodha tradingsymbol

def parse_option_input(query):
    # Example input: "25500 NIFTY CE 24FEB" or "25500 NIFTY CE" (default expiry)
    # Accepts: strike, symbol, type, expiry
    pattern = r"(\d+)\s*(NIFTY|BANKNIFTY)\s*(CE|PE)\s*(\d{1,2}[A-Z]{3})?"
    match = re.match(pattern, query.upper())
    if not match:
        return None
    strike, symbol, opt_type, expiry = match.groups()
    # Default expiry if not provided
    if not expiry:
        expiry = "24FEB"  # You can update this to current expiry
    tradingsymbol = f"{symbol}{expiry}{strike}{opt_type}"
    return tradingsymbol

@app.get("/zerodha-option-price")
def zerodha_option_price(query: str):

    tradingsymbol = query.upper().replace(" ", "")

    exchange = "NFO"   # options always NFO
    symbol = f"{exchange}:{tradingsymbol}"

    try:
        instrument = kite.ltp([symbol])
        price = instrument[symbol]["last_price"]

        return {
            "success": True,
            "price": price,
            "tradingsymbol": tradingsymbol
        }

    except Exception as e:
        return {"success": False, "error": str(e)}