"""
Kotak Neo API Client
Handles authentication and data fetching from Kotak Neo API
"""

import requests
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List
import json

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from utils.config import config
from utils.logger import app_logger
from api.kotak_websocket import KotakWebSocket


class KotakNeoClient:
    """
    Kotak Neo API Client
    Handles authentication and data fetching
    """
    
    def __init__(self):
        """Initialize Kotak Neo API client"""
        # Load credentials from config
        self.access_token = config.kotak_access_token
        self.mobile_number = config.kotak_mobile_number
        self.ucc = config.kotak_ucc
        self.mpin = config.kotak_mpin
        
        # API URLs
        self.login_url = config.kotak_login_url
        self.validate_url = config.kotak_validate_url
        
        # Session data (populated after login)
        self.view_token = None
        self.view_sid = None
        self.trade_token = None
        self.trade_sid = None
        self.base_url = None
        self.server_id = None
        
        # WebSocket client
        self.websocket = None
        
        # Authentication status
        self.is_authenticated = False
        app_logger.info("Kotak Neo Client initialized")



    def login(self, totp: str) -> bool:
        """
        Step 2: Login with TOTP
        
        Args:
            totp: 6-digit TOTP from Google Authenticator
        
        Returns:
            True if successful, False otherwise
        """
        headers = {
            "Authorization": self.access_token,
            "neo-fin-key": "neotradeapi",
            "Content-Type": "application/json"
        }
        
        payload = {
            "mobileNumber": self.mobile_number,
            "ucc": self.ucc,
            "totp": totp
        }
        
        try:
            app_logger.info("Attempting login with TOTP...")
            response = requests.post(self.login_url, headers=headers, json=payload)
            
            if response.status_code == 200:
                data = response.json().get('data', {})
                self.view_token = data.get('token')
                self.view_sid = data.get('sid')
                
                app_logger.info(f"Login successful. View token received.")
                return True
            else:
                app_logger.error(f"Login failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            app_logger.error(f"Login exception: {str(e)}")
            return False




    def validate(self) -> bool:
        """
        Step 3: Validate with MPIN to get trade token
        
        Returns:
            True if successful, False otherwise
        """
        if not self.view_token or not self.view_sid:
            app_logger.error("Must login first before validation")
            return False
        
        headers = {
            "Authorization": self.access_token,
            "neo-fin-key": "neotradeapi",
            "Content-Type": "application/json",
            "sid": self.view_sid,
            "Auth": self.view_token
        }
        
        payload = {
            "mpin": self.mpin
        }
        
        try:
            app_logger.info("Validating with MPIN...")
            response = requests.post(self.validate_url, headers=headers, json=payload)
            
            if response.status_code == 200:
                data = response.json().get('data', {})
                self.trade_token = data.get('token')
                self.trade_sid = data.get('sid')
                self.base_url = data.get('baseUrl')
                self.server_id = data.get('serverId', self.base_url.split('//')[1].split('.')[0])
                self.is_authenticated = True
                
                app_logger.info(f"Validation successful. Trade token received. Base URL: {self.base_url}")
                
                # Initialize WebSocket
                self.websocket = KotakWebSocket(
                    sid=self.trade_sid,
                    auth_token=self.trade_token,
                    server_id=self.server_id
                )
                app_logger.info("WebSocket client initialized")
                
                return True
            else:
                app_logger.error(f"Validation failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            app_logger.error(f"Validation exception: {str(e)}")
            return False


    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authenticated headers for API calls"""
        if not self.is_authenticated:
            raise Exception("Not authenticated. Call login() and validate() first.")
        
        return {
            "Authorization": self.access_token,
            "Sid": self.trade_sid,
            "Auth": self.trade_token,
            "neo-fin-key": "neotradeapi"
        }

    def get_scrip_master_urls(self) -> Optional[List[str]]:
        """
        Get URLs for scrip master CSV files
        
        Returns:
            List of CSV file URLs or None if failed
        """
        if not self.is_authenticated:
            app_logger.error("Not authenticated")
            return None
        
        url = f"{self.base_url}/script-details/1.0/masterscrip/file-paths"
        headers = self._get_auth_headers()
        
        try:
            app_logger.info("Fetching scrip master file URLs...")
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json().get('data', {})
                file_paths = data.get('filesPaths', [])
                app_logger.info(f"Retrieved {len(file_paths)} scrip master files")
                return file_paths
            else:
                app_logger.error(f"Failed to get scrip master: {response.status_code}")
                return None
                
        except Exception as e:
            app_logger.error(f"Exception getting scrip master: {str(e)}")
            return None

    def get_scrip_master_urls(self) -> Optional[List[str]]:
        """
        Get URLs for scrip master CSV files
        
        Returns:
            List of CSV file URLs or None if failed
        """
        if not self.is_authenticated:
            app_logger.error("Not authenticated")
            return None
        
        url = f"{self.base_url}/script-details/1.0/masterscrip/file-paths"
        headers = self._get_auth_headers()
        
        try:
            app_logger.info("Fetching scrip master file URLs...")
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json().get('data', {})
                file_paths = data.get('filesPaths', [])
                app_logger.info(f"Retrieved {len(file_paths)} scrip master files")
                return file_paths
            else:
                app_logger.error(f"Failed to get scrip master: {response.status_code}")
                return None
                
        except Exception as e:
            app_logger.error(f"Exception getting scrip master: {str(e)}")
            return None
    def get_quotes(self, symbol: str, exchange_segment: str = "nse_fo") -> Optional[Dict]:
        """
        Get quotes for a specific instrument (REST API - may not work outside market hours)
        For real-time data, use subscribe_live_feed() instead
        
        Args:
            symbol: Trading symbol (e.g., "NIFTY26FEB2224400CE")
            exchange_segment: Exchange segment (nse_fo, nse_cm, etc.)
        
        Returns:
            Quote data dictionary or None
        """
        if not self.is_authenticated:
            app_logger.error("Not authenticated")
            return None
        
        # Use dynamic base URL from authentication
        url = f"{self.base_url}/quotes/1.0/quote/getquote"
        headers = self._get_auth_headers()
        
        # Build query parameter
        instrument = f"{exchange_segment}|{symbol}"
        params = {"sId": instrument}
        
        try:
            app_logger.info(f"Fetching quote for {symbol}...")
            response = requests.get(url, headers=headers, params=params)
            
            print(f"🔍 DEBUG - Response Status: {response.status_code}")
            print(f"🔍 DEBUG - Response Body: {response.text[:500]}")
            
            if response.status_code == 200:
                data = response.json().get('data', [])
                if data:
                    return data[0]
                return None
            else:
                app_logger.error(f"Failed to get quote: {response.status_code} - {response.text[:200]}")
                return None
                
        except Exception as e:
            app_logger.error(f"Exception getting quote: {str(e)}")
            return None


    def test_symbol(self, symbol: str, exchange_segment: str = "nse_fo") -> bool:
        """
        Test if a symbol exists and is valid
        
        Args:
            symbol: Trading symbol to test
            exchange_segment: Exchange segment
        
        Returns:
            True if symbol exists and can be queried
        """
        print(f"\n🔍 Testing symbol: {symbol} on {exchange_segment}")
        
        # First try to get quote
        quote = self.get_quotes(symbol, exchange_segment)
        
        if quote:
            print(f"✅ Symbol EXISTS and is valid!")
            print(f"   Symbol: {quote.get('sym', symbol)}")
            print(f"   LTP: {quote.get('ltp', 'N/A')}")
            print(f"   Trading Symbol: {quote.get('tsym', 'N/A')}")
            return True
        else:
            print(f"❌ Symbol NOT FOUND or market closed")
            print(f"   This could mean:")
            print(f"   1. Symbol format is incorrect")
            print(f"   2. Strike doesn't exist")
            print(f"   3. Market is closed")
            print(f"   4. Option hasn't started trading yet")
            return False


    def get_historical_data(
        self, 
        symbol: str, 
        exchange_segment: str = "nse_fo",
        from_date: str = None,
        to_date: str = None,
        interval: str = "5"
    ) -> Optional[pd.DataFrame]:
        """
        Get historical OHLC data
        
        Args:
            symbol: Trading symbol
            exchange_segment: Exchange segment
            from_date: Start date (YYYY-MM-DD) - defaults to today
            to_date: End date (YYYY-MM-DD) - defaults to today
            interval: Candle interval in minutes (1, 5, 15, 30, 60, D, W, M)
        
        Returns:
            DataFrame with OHLC data or None
        """
        if not self.is_authenticated:
            app_logger.error("Not authenticated")
            return None
        
        # Default to today if dates not provided
        if not from_date:
            from_date = datetime.now().strftime("%Y-%m-%d")
        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")
        
        # Use dynamic base URL from authentication
        url = f"{self.base_url}/chart/1.0/chart/intraday"
        headers = self._get_auth_headers()
        
        # Build query parameter
        instrument = f"{exchange_segment}|{symbol}"
        
        params = {
            "sId": instrument,
            "from": from_date,
            "to": to_date,
            "resolution": interval
        }
        
        try:
            app_logger.info(f"Fetching historical data for {symbol} ({from_date} to {to_date}, {interval}min)")
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if data exists
                if data.get('s') == 'ok' and 't' in data:
                    # Convert to DataFrame
                    df = pd.DataFrame({
                        'timestamp': pd.to_datetime(data['t'], unit='s'),
                        'open': data['o'],
                        'high': data['h'],
                        'low': data['l'],
                        'close': data['c'],
                        'volume': data.get('v', [0] * len(data['t']))
                    })
                    
                    app_logger.info(f"Retrieved {len(df)} candles")
                    return df
                else:
                    app_logger.warning(f"No data available: {data.get('s', 'unknown status')}")
                    return None
            else:
                app_logger.error(f"Failed to get historical data: {response.status_code}")
                return None
                
        except Exception as e:
            app_logger.error(f"Exception getting historical data: {str(e)}")
            return None
    
    def download_and_search_symbols(self, search_term: str = "NIFTY", strike: int = None):
        """
        Download NSE F&O scrip master and search for symbols
        
        Args:
            search_term: Symbol to search (e.g., "NIFTY", "BANKNIFTY")
            strike: Strike price to filter (e.g., 24800)
        """
        urls = self.get_scrip_master_urls()
        if not urls:
            return
        
        # Find nse_fo CSV
        nse_fo_url = None
        for url in urls:
            if 'nse_fo' in url:
                nse_fo_url = url
                break
        
        if not nse_fo_url:
            print("❌ NSE F&O file not found")
            return
        
        print(f"\n📥 Downloading: {nse_fo_url}")
        
        try:
            # Download CSV
            df = pd.read_csv(nse_fo_url)
            print(f"✅ Downloaded {len(df)} instruments")
            print(f"📋 Available columns: {', '.join(df.columns.tolist()[:10])}...")
            
            # Convert columns to proper types
            if 'pTrdSymbol' in df.columns:
                df['pTrdSymbol'] = df['pTrdSymbol'].astype(str)
            
            # Debug: Show sample of data
            print(f"\n🔍 Sample pTrdSymbol values:")
            print(df['pTrdSymbol'].head(20).tolist())
            
            # Search in pTrdSymbol (trading symbol) which contains actual symbol names
            filtered = df[df['pTrdSymbol'].str.contains(search_term, case=False, na=False)]
            print(f"After search term '{search_term}': {len(filtered)} symbols")
            
            # Filter by strike price - find the correct column name
            strike_col = None
            for col in ['lStrikePrice', 'strikePrice', 'strike_price', 'strike', 'pISIN']:
                if col in df.columns:
                    strike_col = col
                    break
            
            if strike and strike_col:
                print(f"Filtering by strike {strike} using column: {strike_col}")
                try:
                    # For pTrdSymbol, the strike is embedded in the string
                    # E.g., NIFTY2620325000PE has 25000 in it
                    filtered = filtered[filtered['pTrdSymbol'].str.contains(str(strike), na=False)]
                    print(f"After strike filter: {len(filtered)} symbols")
                except Exception as e:
                    print(f"⚠️ Could not filter by strike: {e}")
            
            print(f"\n🔍 Found {len(filtered)} matching symbols:")
            print("\nSample symbols (first 10):")
            for idx, row in filtered.head(10).iterrows():
                # Format strike price properly (no scientific notation)
                strike_val = 'N/A'
                for col in ['lStrikePrice', 'strikePrice', 'strike_price', 'strike']:
                    if col in row and row.get(col) is not None:
                        try:
                            strike_val = int(float(row[col]))
                            break
                        except:
                            pass
                
                print(f"  Trading Symbol: {row.get('pTrdSymbol', 'N/A')}")
                print(f"    Instrument Token: {row.get('pSymbol', 'N/A')}")
                print(f"    Scrip Key: {row.get('pScripRefKey', 'N/A')}")
                print(f"    Exchange: {row.get('pExchSeg', 'N/A')}")
                print(f"    Strike: {strike_val}")
                print(f"    Expiry: {row.get('lExpiryDate', 'N/A')}")
                print(f"    Option Type: {row.get('pOptionType', 'N/A')}")
                print()
            
            return filtered
            
        except Exception as e:
            print(f"❌ Error downloading CSV: {e}")
            return None
    
    def connect_websocket(self):
        """Connect to WebSocket for live data"""
        if not self.websocket:
            app_logger.error("WebSocket not initialized. Complete authentication first.")
            return False
        
        self.websocket.connect()
        return True
    
    def subscribe_live_feed(self, instrument_tokens: List[Dict]) -> bool:
        """
        Subscribe to live market data via WebSocket
        
        Args:
            instrument_tokens: List of {"instrument_token": "symbol", "exchange_segment": "nse_fo"}
        
        Returns:
            True if subscription successful
        """
        if not self.websocket:
            app_logger.error("WebSocket not initialized")
            return False
        
        return self.websocket.subscribe(instrument_tokens)
    
    def get_live_quote(self, instrument_token: str) -> Optional[Dict]:
        """Get latest quote from WebSocket feed"""
        if not self.websocket:
            return None
        
        return self.websocket.get_quote(instrument_token)
    
    def set_websocket_callbacks(self, on_message=None, on_error=None, on_open=None, on_close=None):
        """Set WebSocket event callbacks"""
        if self.websocket:
            if on_message:
                self.websocket.on_message = on_message
            if on_error:
                self.websocket.on_error = on_error
            if on_open:
                self.websocket.on_open = on_open
            if on_close:
                self.websocket.on_close = on_close
            
# Test authentication and data fetching
if __name__ == "__main__":
    print("=" * 60)
    print("Kotak Neo API Client - Full Test")
    print("=" * 60)
    
    client = KotakNeoClient()
    
    print(f"\nCredentials loaded:")
    print(f"  Mobile: {client.mobile_number}")
    print(f"  UCC: {client.ucc}")
    
    # Step 1: Get TOTP from user
    print("\n" + "=" * 60)
    print("STEP 1: Authentication")
    print("=" * 60)
    print("Open Google Authenticator and enter the 6-digit TOTP:")
    totp = input("TOTP: ").strip()
    
    # Step 2: Login and Validate
    if client.login(totp) and client.validate():
        print("✅ Authentication successful!")
        print(f"Base URL: {client.base_url}")
        
        # Test 1: Get Scrip Master URLs
        print("\n" + "=" * 60)
        print("STEP 2: Fetching Scrip Master URLs")
        print("=" * 60)
        urls = client.get_scrip_master_urls()
        if urls:
            print(f"✅ Found {len(urls)} instrument files:")
            for url in urls[:3]:  # Show first 3
                print(f"  - {url.split('/')[-1]}")
        
        # Test 2.5: Find Available Nifty Options
        print("\n" + "=" * 60)
        print("STEP 2.5: Finding Available Nifty Options")
        print("=" * 60)
        print("Enter strike price to search (or press Enter for 24800):")
        strike_input = input("Strike: ").strip()
        strike = int(strike_input) if strike_input else 24800
        
        symbols = client.download_and_search_symbols("NIFTY", strike=strike)
        
        # Test 3: Get Quotes (example with Nifty Spot)
        print("\n" + "=" * 60)
        print("STEP 3: Getting Nifty Spot Price for ATM Strike")
        print("=" * 60)
        print("Fetching Nifty spot price...")
        quote = client.get_quotes("NIFTY 50", "nse_cm")
        
        nifty_spot = None
        if quote:
            nifty_spot = quote.get('ltp')
            print(f"✅ NIFTY Spot: {nifty_spot}")
        else:
            print("⚠️ Could not fetch spot price, using default")
        
        # Calculate ATM strike
        if nifty_spot:
            # Round to nearest 50
            atm_strike = round(float(nifty_spot) / 50) * 50
        else:
            # Default to a reasonable strike
            atm_strike = 23500
        
        print(f"📊 Using ATM Strike: {atm_strike}")
        print(f"💡 This should have active trading and real-time data!")
        
        # Search for options near ATM
        print(f"\nSearching for options at strike {atm_strike}...")
        atm_symbols = client.download_and_search_symbols("NIFTY", strike=atm_strike)
        
        # Find next week's CE option
        symbol = None
        if atm_symbols is not None and not atm_symbols.empty:
            # Filter for CE options expiring next week (not today)
            weekly_options = atm_symbols[
                (atm_symbols['pTrdSymbol'].str.contains('26FEB', na=False)) |
                (atm_symbols['pTrdSymbol'].str.contains('2621', na=False)) & 
                ~(atm_symbols['pTrdSymbol'].str.contains('2621025000', na=False))  # Not today
            ]
            
            ce_options = weekly_options[weekly_options['pOptionType'] == 'CE']
            
            if not ce_options.empty:
                symbol = ce_options.iloc[0]['pTrdSymbol']
                print(f"✅ Selected: {symbol}")
            else:
                print("⚠️ No suitable options found, using manual selection")
        
        if not symbol:
            print("\nFalling back to manual selection...")
            print("Enter the exact symbol from CSV (or press Enter to use example):")
            print("Example: NIFTY26FEB23500CE")
            symbol = input("Symbol: ").strip()
            
            if not symbol:
                symbol = "NIFTY26FEB23500CE"
                print(f"Using default: {symbol}")
        
        exchange = "nse_fo"
        
        # Skip symbol validation (will fail when market closed)
        # Go straight to historical data test
        print("\n" + "=" * 60)
        print("STEP 5: Fetching YESTERDAY's Historical Data")
        print("=" * 60)
        print("Trying to fetch last 7 days of data...")
        
        # Try fetching last week's data
        from datetime import datetime, timedelta
        today = datetime.now()
        from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        to_date = today.strftime("%Y-%m-%d")
        
        print(f"Date range: {from_date} to {to_date}")
        
        df = client.get_historical_data(
            symbol, 
            exchange, 
            from_date=from_date,
            to_date=to_date,
            interval="5"
        )
        
        if df is not None and not df.empty:
            
            if df is not None and not df.empty:
                print(f"✅ Retrieved {len(df)} candles!")
                print("\nLast 5 candles:")
                print(df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail())
                
                # Test with Moving Average Strategy!
                print("\n" + "=" * 60)
                print("BONUS: Testing Moving Average Strategy on Real Data!")
                print("=" * 60)
                
                try:
                    from strategies import MovingAverageStrategy
                    
                    ma_strategy = MovingAverageStrategy(period=20)
                    signal = ma_strategy.calculate(df)
                    
                    print(f"Strategy: {ma_strategy.name}")
                    print(f"Signal: {signal}")
                    print(f"Current Price: {df['close'].iloc[-1]:.2f}")
                    
                    signal_data = ma_strategy.get_signal()
                    if signal_data['metadata']:
                        print(f"MA Value: {signal_data['metadata'].get('ma_value', 'N/A'):.2f}")
                        print(f"Distance: {signal_data['metadata'].get('distance_from_ma', 'N/A'):.2f}")
                    
                    print("\n🎉 Strategy tested on REAL market data!")
                except Exception as e:
                    print(f"Could not test strategy: {e}")
        else:
            print("❌ No historical data available")
            print("This could mean:")
            print("  1. API is completely down outside market hours (even for historical)")
            print("  2. Symbol format is incorrect")
            print("  3. Data not available for these dates")
            print("\n💡 Try again during market hours: 9:15 AM - 3:30 PM IST")
        
        # Test WebSocket (if market is open)
        print("\n" + "=" * 60)
        print("STEP 4: Testing WebSocket Live Feed")
        print("=" * 60)
        print("Connecting to WebSocket for live data...")
        
        # Set up callback to print live data
        def on_ws_message(message):
            print(f"📊 Live Data: {message}")
        
        client.set_websocket_callbacks(on_message=on_ws_message)
        
        if client.connect_websocket():
            print("✅ WebSocket connection initiated!")
            print("Waiting for connection to establish...")
            
            import time
            time.sleep(3)  # Wait for WebSocket to connect
            
            if client.websocket.is_connected:
                print("✅ WebSocket connected!")
                print("Subscribing to live feed...")
                
                # Get the instrument token from the CSV search
                print(f"\nSearching for instrument token for {symbol}...")
                
                # Download and search for exact symbol match
                scrip_urls = client.get_scrip_master_urls()
                if scrip_urls:
                    import pandas as pd
                    import requests
                    from io import StringIO
                    
                    # Find NSE F&O CSV URL
                    csv_url = None
                    for url in scrip_urls:
                        if 'nse_fo' in url:
                            csv_url = url
                            break
                    
                    if csv_url:
                        response = requests.get(csv_url)
                        df = pd.read_csv(StringIO(response.text))
                        
                        # Search for exact symbol match
                        matching = df[df['pTrdSymbol'] == symbol]
                        
                        if not matching.empty:
                            instrument_token = int(matching.iloc[0]['pSymbol'])
                            exchange_seg = matching.iloc[0]['pExchSeg']
                            
                            print(f"✅ Found instrument token: {instrument_token}")
                            
                            # Subscribe to the symbol
                            instruments = [
                                {"instrument_token": instrument_token, "exchange_segment": exchange_seg}
                            ]
                            
                            if client.subscribe_live_feed(instruments):
                                print(f"✅ Subscribed to {symbol}")
                                print("Listening for live updates for 30 seconds...")
                                
                                time.sleep(30)
                                
                                # Get latest quote
                                quote = client.get_live_quote(instrument_token)
                                if quote:
                                    print(f"\n📈 Latest Quote: {quote}")
                                else:
                                    print("\n⚠️ No quote data received yet")
                            else:
                                print("❌ Subscription failed")
                        else:
                            print(f"❌ Could not find {symbol} in CSV")
                    else:
                        print("❌ Could not find NSE F&O CSV")
                else:
                    print("❌ Could not get scrip URLs")
            else:
                print("❌ WebSocket failed to connect (normal if market is closed)")
        else:
            print("❌ WebSocket connection failed (normal if market is closed)")