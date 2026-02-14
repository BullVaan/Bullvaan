"""
Test WebSocket with Nifty Spot Index - Most liquid instrument
"""
import time
from api.kotak_neo import KotakNeoAPI

def main():
    # Initialize client
    print("=" * 60)
    print("TESTING WEBSOCKET WITH NIFTY SPOT INDEX")
    print("=" * 60)
    print("Nifty Spot always has continuous data during market hours!")
    print()
    
    client = KotakNeoAPI()
    
    # Authenticate
    print("Step 1: Authenticating...")
    if not client.authenticate():
        print("❌ Authentication failed")
        return
    
    print("✅ Authenticated!")
    
    # Connect WebSocket
    print("\nStep 2: Connecting WebSocket...")
    
    # Set up callback
    received_data = {'count': 0}
    
    def on_message(message):
        received_data['count'] += 1
        print(f"\n📊 Message #{received_data['count']}: {message}")
    
    client.set_websocket_callbacks(on_message=on_message)
    
    if not client.connect_websocket():
        print("❌ WebSocket connection failed")
        return
    
    print("✅ WebSocket initiated")
    time.sleep(2)
    
    if not client.websocket.is_connected:
        print("❌ WebSocket not connected")
        return
    
    print("✅ WebSocket connected!")
    
    # Subscribe to Nifty Spot
    print("\nStep 3: Subscribing to NIFTY SPOT (NSE_CM)...")
    print("Searching for Nifty Spot instrument token...")
    
    # Get scrip URLs
    scrip_urls = client.get_scrip_master_urls()
    if not scrip_urls:
        print("❌ Could not get scrip URLs")
        return
    
    # Find NSE CM (cash market) CSV
    import pandas as pd
    import requests
    from io import StringIO
    
    nse_cm_url = None
    for url in scrip_urls:
        if 'nse_cm' in url.lower():
            nse_cm_url = url
            break
    
    if not nse_cm_url:
        print("❌ Could not find NSE_CM CSV")
        return
    
    print(f"📥 Downloading NSE CM data...")
    response = requests.get(nse_cm_url)
    df = pd.read_csv(StringIO(response.text))
    
    # Search for NIFTY 50
    nifty_rows = df[df['pTrdSymbol'].str.contains('NIFTY 50', case=False, na=False)]
    
    if nifty_rows.empty:
        # Try alternative names
        nifty_rows = df[df['pTrdSymbol'].str.contains('NIFTY', case=False, na=False) & 
                       df['pTrdSymbol'].str.contains('50', case=False, na=False)]
    
    if nifty_rows.empty:
        print("❌ Could not find NIFTY 50")
        print("Available symbols sample:")
        print(df['pTrdSymbol'].head(20).tolist())
        return
    
    # Get first match
    nifty_row = nifty_rows.iloc[0]
    instrument_token = int(nifty_row['pSymbol'])
    exchange_seg = nifty_row['pExchSeg']
    
    print(f"✅ Found NIFTY SPOT")
    print(f"   Symbol: {nifty_row['pTrdSymbol']}")
    print(f"   Token: {instrument_token}")
    print(f"   Exchange: {exchange_seg}")
    
    # Subscribe
    instruments = [
        {"instrument_token": instrument_token, "exchange_segment": exchange_seg}
    ]
    
    if not client.subscribe_live_feed(instruments):
        print("❌ Subscription failed")
        return
    
    print("✅ Subscribed to NIFTY SPOT!")
    print("\n" + "=" * 60)
    print("LISTENING FOR 45 SECONDS...")
    print("=" * 60)
    print("(Market hours: 9:15 AM - 3:30 PM IST)")
    print()
    
    # Wait for data
    time.sleep(45)
    
    # Check results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    if received_data['count'] > 0:
        print(f"✅ SUCCESS! Received {received_data['count']} messages!")
        
        # Try to get latest quote
        quote = client.get_live_quote(instrument_token)
        if quote:
            print(f"\n📈 Latest Quote:")
            print(f"   LTP: {quote.get('ltp', 'N/A')}")
            print(f"   Volume: {quote.get('volume', 'N/A')}")
            print(f"   Open: {quote.get('open', 'N/A')}")
            print(f"   High: {quote.get('high', 'N/A')}")
            print(f"   Low: {quote.get('low', 'N/A')}")
    else:
        print("❌ NO DATA RECEIVED")
        print("\nPossible reasons:")
        print("  1. Markets are closed (9:15 AM - 3:30 PM IST)")
        print("  2. WebSocket message format not recognized")
        print("  3. Need to verify subscription payload format")
        
        current_time = time.strftime("%H:%M %Z")
        print(f"\nCurrent time: {current_time}")
        print("Oslo 8:45 AM = India 1:15 PM IST (markets SHOULD be open)")

if __name__ == "__main__":
    main()
