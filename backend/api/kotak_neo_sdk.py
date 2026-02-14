"""
Kotak Neo API Client using Official SDK
Wrapper around neo_api_client for easier integration
"""

import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List
from neo_api_client import NeoAPI
from utils.logger import app_logger
from utils.config import config


class KotakNeoSDK:
    """Wrapper around official Kotak Neo SDK"""
    
    def __init__(self):
        """Initialize Kotak Neo SDK Client"""
        # Use access token from config
        self.client = NeoAPI(
            consumer_key="",
            consumer_secret="",
            environment='prod',
            access_token=config.kotak_access_token,
            neo_fin_key="neotradeapi"
        )
        
        self.mobile_number = config.kotak_mobile_number
        self.mpin = config.kotak_mpin
        
        # WebSocket callbacks
        self.client.on_message = self._on_message
        self.client.on_error = self._on_error
        self.client.on_close = self._on_close
        self.client.on_open = self._on_open
        
        self.quote_data = {}
        
        app_logger.info("Kotak Neo SDK Client initialized")
    
    def _on_message(self, message):
        """Handle WebSocket messages"""
        app_logger.debug(f"WS Message: {message}")
        # Store quote data
        if isinstance(message, dict) and 'lp' in message:
            token = message.get('tk')
            self.quote_data[token] = message
    
    def _on_error(self, error):
        """Handle WebSocket errors"""
        app_logger.error(f"WS Error: {error}")
    
    def _on_close(self, message):
        """Handle WebSocket close"""
        app_logger.info(f"WS Closed: {message}")
    
    def _on_open(self, message):
        """Handle WebSocket open"""
        app_logger.info(f"WS Opened: {message}")
    
    def login(self, otp: str) -> bool:
        """
        Complete login with OTP (using access token + MPIN flow)
        
        Args:
            otp: OTP from Google Authenticator (TOTP)
        
        Returns:
            True if login successful
        """
        try:
            app_logger.info("Logging in with access token + MPIN...")
            
            # The SDK might handle this differently
            # For now, try the mobilenumber + mpin approach
            result = self.client.login(
                mobilenumber=self.mobile_number,
                password=self.mpin  # Using MPIN as password
            )
            
            app_logger.info(f"Login initiated: {result}")
            
            # Complete 2FA with OTP
            result = self.client.session_2fa(OTP=otp)
            
            if result:
                app_logger.info("Login successful!")
                return True
            else:
                app_logger.error("Login failed")
                return False
                
        except Exception as e:
            app_logger.error(f"Login exception: {str(e)}")
            print(f"Error details: {e}")
            return False
    
    def get_quotes(self, instrument_tokens: List[Dict], quote_type: str = None) -> Dict:
        """
        Get quotes for instruments
        
        Args:
            instrument_tokens: List of {"instrument_token": "token", "exchange_segment": "nse_fo"}
            quote_type: Type of quote (market_depth, ohlc, ltp, 52w, circuit_limits, scrip_details)
        
        Returns:
            Quote data dictionary
        """
        try:
            app_logger.info(f"Getting quotes for {len(instrument_tokens)} instruments")
            result = self.client.quotes(
                instrument_tokens=instrument_tokens,
                quote_type=quote_type,
                isIndex=False
            )
            return result
        except Exception as e:
            app_logger.error(f"Get quotes error: {str(e)}")
            return None
    
    def search_scrip(self, symbol: str, exchange_segment: str = "nse_fo", 
                     strike_price: str = "", expiry: str = "", 
                     option_type: str = "") -> List[Dict]:
        """
        Search for scrip in master
        
        Args:
            symbol: Symbol to search (e.g., "NIFTY")
            exchange_segment: Exchange segment
            strike_price: Strike price filter
            expiry: Expiry date filter
            option_type: CE or PE
        
        Returns:
            List of matching scrips
        """
        try:
            app_logger.info(f"Searching scrip: {symbol}")
            result = self.client.search_scrip(
                exchange_segment=exchange_segment,
                symbol=symbol,
                expiry=expiry,
                option_type=option_type,
                strike_price=strike_price
            )
            return result
        except Exception as e:
            app_logger.error(f"Search scrip error: {str(e)}")
            return []
    
    def subscribe_live_feed(self, instrument_tokens: List[Dict], isDepth: bool = False) -> bool:
        """
        Subscribe to live feed via WebSocket
        
        Args:
            instrument_tokens: List of instruments
            isDepth: Subscribe to depth data
        
        Returns:
            True if subscription successful
        """
        try:
            app_logger.info(f"Subscribing to {len(instrument_tokens)} instruments")
            self.client.subscribe(
                instrument_tokens=instrument_tokens,
                isIndex=False,
                isDepth=isDepth
            )
            return True
        except Exception as e:
            app_logger.error(f"Subscribe error: {str(e)}")
            return False


# Test the SDK
if __name__ == "__main__":
    print("=" * 60)
    print("Kotak Neo SDK Client - Test")
    print("=" * 60)
    
    client = KotakNeoSDK()
    
    # Get OTP from user
    print("\nStep 1: Initiating login...")
    print("Enter TOTP from Google Authenticator (6 digits):")
    otp = input("TOTP: ").strip()
    
    if client.login(otp):
        print("✅ Login successful!")
        
        # Search for Nifty options
        print("\n" + "=" * 60)
        print("Searching for Nifty 25000 options...")
        print("=" * 60)
        
        scrips = client.search_scrip(
            symbol="NIFTY",
            exchange_segment="nse_fo",
            strike_price="25000",
            option_type="PE"
        )
        
        if scrips:
            print(f"\n✅ Found {len(scrips)} scrips!")
            for scrip in scrips[:5]:
                print(f"\nSymbol: {scrip.get('pSymbol', 'N/A')}")
                print(f"  Trading Symbol: {scrip.get('pTrdSymbol', 'N/A')}")
                print(f"  Token: {scrip.get('pSymbol', 'N/A')}")
                print(f"  Strike: {scrip.get('dStrikePrice;', 'N/A')}")
                print(f"  Expiry: {scrip.get('lExpiryDate', 'N/A')}")
        else:
            print("❌ No scrips found")
    else:
        print("❌ Login failed")
