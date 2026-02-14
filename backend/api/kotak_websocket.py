"""
WebSocket client for Kotak Neo real-time data
"""

import json
import threading
import websocket
from typing import Callable, Dict, Optional
from utils.logger import app_logger


class KotakWebSocket:
    """WebSocket client for live market data"""
    
    def __init__(self, sid: str, auth_token: str, server_id: str):
        """
        Initialize WebSocket client
        
        Args:
            sid: Session ID
            auth_token: Authentication token
            server_id: Server ID
        """
        self.sid = sid
        self.auth_token = auth_token
        self.server_id = server_id
        self.ws_url = "wss://mlhsm.kotaksecurities.com"
        self.ws = None
        self.is_connected = False
        
        # Callbacks
        self.on_message = None
        self.on_error = None
        self.on_close = None
        self.on_open = None
        
        # Data storage
        self.quote_data = {}
        
    def connect(self):
        """Connect to WebSocket"""
        try:
            app_logger.info(f"Connecting to WebSocket: {self.ws_url}")
            
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            
            # Run in separate thread
            wst = threading.Thread(target=self.ws.run_forever)
            wst.daemon = True
            wst.start()
            
            app_logger.info("WebSocket connection initiated")
            
        except Exception as e:
            app_logger.error(f"WebSocket connection error: {str(e)}")
    
    def _on_open(self, ws):
        """Handle WebSocket open"""
        self.is_connected = True
        app_logger.info("WebSocket connected")
        
        # Send connection payload
        connection_payload = {
            "type": "cn",
            "Authorization": self.auth_token,
            "Sid": self.sid,
            "ServerId": self.server_id
        }
        
        ws.send(json.dumps(connection_payload))
        app_logger.info("Sent connection payload")
        
        if self.on_open:
            self.on_open("WebSocket opened")
    
    def _on_message(self, ws, message):
        """Handle incoming messages"""
        try:
            print(f"🔔 RAW WebSocket Message: {message[:200]}")  # Print first 200 chars
            data = json.loads(message)
            app_logger.debug(f"WS Message: {data}")
            print(f"📨 Parsed Message Type: {data.get('type') if isinstance(data, dict) else 'unknown'}")
            
            # Store quote data
            if isinstance(data, dict):
                msg_type = data.get('type')
                
                if msg_type == 'cn':
                    app_logger.info("Connection acknowledged")
                    print("✅ Connection acknowledged by server")
                elif msg_type in ['sf', 'if', 'dp']:  # Scrip/Index/Depth data
                    # Store the quote
                    token = data.get('tk')
                    if token:
                        self.quote_data[token] = data
                        print(f"💰 Quote stored for token {token}: LTP={data.get('lp')}")
            
            if self.on_message:
                self.on_message(data)
                
        except Exception as e:
            app_logger.error(f"Error processing message: {str(e)}")
    
    def _on_error(self, ws, error):
        """Handle errors"""
        app_logger.error(f"WebSocket error: {error}")
        if self.on_error:
            self.on_error(error)
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle close"""
        self.is_connected = False
        app_logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        if self.on_close:
            self.on_close(f"Closed: {close_msg}")
    
    def subscribe(self, instrument_tokens: list, quote_type: str = "ltp"):
        """
        Subscribe to instruments
        
        Args:
            instrument_tokens: List of {"instrument_token": "token", "exchange_segment": "nse_fo"}
            quote_type: Type of data (ltp, quotes, depth)
        """
        if not self.is_connected:
            app_logger.error("WebSocket not connected")
            return False
        
        try:
            # Build subscription payload
            scrips = []
            for item in instrument_tokens:
                token = item.get('instrument_token')
                exchange = item.get('exchange_segment', 'nse_fo')
                
                scrips.append({
                    "symbol": token,
                    "exchangeSegment": exchange
                })
            
            payload = {
                "type": "s",  # Subscribe
                "scrips": scrips,
                "channelnum": "1"
            }
            
            self.ws.send(json.dumps(payload))
            app_logger.info(f"Subscribed to {len(scrips)} instruments")
            return True
            
        except Exception as e:
            app_logger.error(f"Subscribe error: {str(e)}")
            return False
    
    def unsubscribe(self, instrument_tokens: list):
        """Unsubscribe from instruments"""
        if not self.is_connected:
            return False
        
        try:
            scrips = []
            for item in instrument_tokens:
                token = item.get('instrument_token')
                exchange = item.get('exchange_segment', 'nse_fo')
                
                scrips.append({
                    "symbol": token,
                    "exchangeSegment": exchange
                })
            
            payload = {
                "type": "u",  # Unsubscribe
                "scrips": scrips,
                "channelnum": "1"
            }
            
            self.ws.send(json.dumps(payload))
            app_logger.info(f"Unsubscribed from {len(scrips)} instruments")
            return True
            
        except Exception as e:
            app_logger.error(f"Unsubscribe error: {str(e)}")
            return False
    
    def get_quote(self, instrument_token: str) -> Optional[Dict]:
        """Get latest quote for instrument"""
        return self.quote_data.get(instrument_token)
    
    def close(self):
        """Close WebSocket connection"""
        if self.ws:
            self.ws.close()
            app_logger.info("WebSocket closed")
