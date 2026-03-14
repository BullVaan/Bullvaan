"""
Premarket Signal Engine
=======================
Generates trading signals BEFORE market open (before 9:15 AM IST) based on:
- Previous day's closing patterns
- Gap analysis (current open vs previous close)
- Volume reversals
- Support/Resistance levels
"""

import logging
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List

logger = logging.getLogger("premarket_signals")

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))

class PremarketSignalEngine:
    """Generate signals before market open"""
    
    def __init__(self, kite=None):
        self.kite = kite
    
    def get_premarket_signals(self, symbol: str) -> Dict:
        """
        Generate premarket signals for a stock/index
        
        Returns:
            {
                'symbol': 'NIFTY',
                'signal': 'BUY'|'SELL'|'NEUTRAL',
                'strength': 'STRONG'|'MEDIUM'|'WEAK',
                'gap_percent': 2.5,
                'gap_direction': 'UP'|'DOWN',
                'reason': 'Strong gap up with high volume',
                'support_level': 22450,
                'resistance_level': 22650,
                'previous_close': 22500,
                'prev_volume_avg': 450000,
                'timestamp': datetime.now(IST).isoformat()
            }
        """
        try:
            df = self._fetch_historical_data(symbol)
            if df is None or len(df) < 2:
                return self._neutral_signal(symbol, "Insufficient data")
            
            # Calculate metrics
            yesterday = df.iloc[-1]
            day_before = df.iloc[-2]
            
            prev_close = yesterday['close']
            current_open = self._get_current_open(symbol) or prev_close
            
            # Gap Analysis
            gap_percent = ((current_open - prev_close) / prev_close) * 100
            gap_direction = 'UP' if gap_percent > 0 else 'DOWN'
            
            # Volume Analysis
            prev_avg_volume = df['volume'].tail(10).mean()
            yesterday_volume = yesterday['volume']
            volume_ratio = yesterday_volume / prev_avg_volume if prev_avg_volume > 0 else 1
            
            # Support & Resistance (from last 20 days)
            support = df['low'].tail(20).min()
            resistance = df['high'].tail(20).max()
            
            # Price Action Patterns
            yesterday_close = yesterday['close']
            yesterday_open = yesterday['open']
            yesterday_range = yesterday['high'] - yesterday['low']
            body = abs(yesterday_close - yesterday_open)
            is_bullish_candle = yesterday_close > yesterday_open
            
            # Signal Logic
            signal, strength, reason = self._analyze_pattern(
                gap_percent=gap_percent,
                gap_direction=gap_direction,
                volume_ratio=volume_ratio,
                is_bullish_candle=is_bullish_candle,
                body_percent=body / yesterday_range if yesterday_range > 0 else 0,
                support=support,
                prev_close=prev_close,
                resistance=resistance,
                current_open=current_open
            )
            
            return {
                'symbol': symbol,
                'signal': signal,
                'strength': strength,
                'gap_percent': round(gap_percent, 2),
                'gap_direction': gap_direction,
                'reason': reason,
                'support_level': round(support, 2),
                'resistance_level': round(resistance, 2),
                'previous_close': round(prev_close, 2),
                'current_open': round(current_open, 2),
                'prev_volume_avg': int(prev_avg_volume),
                'yesterday_volume': int(yesterday_volume),
                'timestamp': datetime.now(IST).isoformat()
            }
        except Exception as e:
            logger.error(f"Error generating premarket signal for {symbol}: {e}")
            return self._neutral_signal(symbol, str(e))
    
    def _analyze_pattern(self, gap_percent, gap_direction, volume_ratio, 
                        is_bullish_candle, body_percent, support, prev_close,
                        resistance, current_open) -> tuple:
        """
        Analyze pattern and return (signal, strength, reason)
        """
        
        # Strong gap conditions
        strong_gap_up = gap_percent > 1.5 and gap_direction == 'UP'
        strong_gap_down = gap_percent < -1.5 and gap_direction == 'DOWN'
        
        # Strong volume (>130% of average)
        high_volume = volume_ratio > 1.3
        
        # Strong body (>70% of range)
        strong_body = body_percent > 0.7
        
        # ========== BULLISH SCENARIOS ==========
        if strong_gap_up and high_volume and is_bullish_candle:
            return 'BUY', 'STRONG', f'Strong gap up {gap_percent}% + high volume + bullish close'
        
        if strong_gap_up and is_bullish_candle:
            return 'BUY', 'MEDIUM', f'Gap up {gap_percent}% with bullish candle'
        
        if is_bullish_candle and strong_body and high_volume:
            return 'BUY', 'MEDIUM', 'Strong bullish close with high volume'
        
        if current_open < support and is_bullish_candle:
            return 'BUY', 'MEDIUM', 'Price bounced from support level'
        
        # ========== BEARISH SCENARIOS ==========
        if strong_gap_down and high_volume and not is_bullish_candle:
            return 'SELL', 'STRONG', f'Strong gap down {gap_percent}% + high volume + bearish close'
        
        if strong_gap_down and not is_bullish_candle:
            return 'SELL', 'MEDIUM', f'Gap down {gap_percent}% with bearish candle'
        
        if not is_bullish_candle and strong_body and high_volume:
            return 'SELL', 'MEDIUM', 'Strong bearish close with high volume'
        
        if current_open > resistance and not is_bullish_candle:
            return 'SELL', 'MEDIUM', 'Price rejected from resistance level'
        
        # ========== NEUTRAL / WATCH ==========
        if abs(gap_percent) < 0.5:
            return 'NEUTRAL', 'WEAK', 'Minimal gap, market tends to reverse'
        
        return 'NEUTRAL', 'WEAK', 'Insufficient pattern formation'
    
    def _fetch_historical_data(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """Fetch last 30 days of historical data from Zerodha"""
        try:
            from utils.zerodha_data import fetch_zerodha_history
            
            if not self.kite:
                logger.error("KiteConnect not initialized")
                return None
            
            # Fetch daily candles for last N days
            df = fetch_zerodha_history(
                self.kite,
                symbol=symbol,
                interval="1d",
                days=days,
                get_spot_token_fn=None
            )
            
            if df is None or len(df) < 2:
                logger.warning(f"Insufficient data for {symbol} ({len(df) if df is not None else 0} rows)")
                return None
            
            logger.debug(f"Fetched {len(df)} days of history for {symbol}")
            return df
        except Exception as e:
            logger.error(f"Failed to fetch history for {symbol}: {e}")
            return None
    
    def _get_current_open(self, symbol: str) -> Optional[float]:
        """Get current market open price from KiteTicker during premarket"""
        try:
            # During premarket, try to get live tick data
            # This will be populated when market opens or from IPE (if available)
            from api.server import _tick_store, _token_map
            
            # Find instrument token for this symbol
            token = None
            for tok, info in _token_map.items():
                if info.get('symbol') == symbol or info.get('tradingsymbol') == symbol:
                    token = tok
                    break
            
            if token and token in _tick_store:
                tick = _tick_store[token]
                price = tick.get("last_price")
                if price:
                    logger.debug(f"Live price for {symbol}: {price}")
                    return price
            
            return None
        except Exception as e:
            logger.debug(f"Could not get live current open for {symbol}: {e}")
            return None
    
    def _neutral_signal(self, symbol: str, reason: str) -> Dict:
        """Return neutral signal"""
        return {
            'symbol': symbol,
            'signal': 'NEUTRAL',
            'strength': 'WEAK',
            'gap_percent': 0,
            'gap_direction': 'NONE',
            'reason': reason,
            'support_level': 0,
            'resistance_level': 0,
            'previous_close': 0,
            'current_open': 0,
            'prev_volume_avg': 0,
            'yesterday_volume': 0,
            'timestamp': datetime.now(IST).isoformat()
        }
    
    def get_premarket_signals_batch(self, symbols: List[str]) -> List[Dict]:
        """Get signals for multiple symbols"""
        return [self.get_premarket_signals(sym) for sym in symbols]
