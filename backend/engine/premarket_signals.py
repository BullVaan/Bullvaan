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
        Generate premarket signals showing YESTERDAY'S CONTEXT + TODAY'S LEVELS
        
        This analyzes yesterday's close to prepare traders for today's trading.
        Returns:
            {
                'symbol': 'NIFTY',
                'yesterday_summary': {...},
                'support_resistance': {...},
                'today_levels': {...},
                'signal': 'BUY'|'SELL'|'NEUTRAL',
                'reason': 'Strong close in upper range - expect continuation',
                'timestamp': datetime.now(IST).isoformat()
            }
        """
        try:
            df = self._fetch_historical_data(symbol)
            if df is None or len(df) < 2:
                return self._neutral_signal(symbol, "Insufficient data")
            
            # Get yesterday's complete data
            yesterday = df.iloc[-1]
            
            yesterday_open = yesterday['open']
            yesterday_close = yesterday['close']
            yesterday_high = yesterday['high']
            yesterday_low = yesterday['low']
            yesterday_volume = yesterday['volume']
            yesterday_range = yesterday_high - yesterday_low
            
            # Volume context (last 10 days)
            volume_avg_10d = df['volume'].tail(10).mean()
            volume_ratio = yesterday_volume / volume_avg_10d if volume_avg_10d > 0 else 1
            volume_trend = 'HIGH' if volume_ratio > 1.2 else ('LOW' if volume_ratio < 0.8 else 'NORMAL')
            
            # Where did yesterday close in its range?
            close_ratio = (yesterday_close - yesterday_low) / yesterday_range if yesterday_range > 0 else 0.5
            if close_ratio >= 0.67:
                close_position = 'UPPER'
                close_signal = '⬆️'
            elif close_ratio >= 0.33:
                close_position = 'MIDDLE'
                close_signal = '➡️'
            else:
                close_position = 'LOWER'
                close_signal = '⬇️'
            
            # Support & Resistance Levels for TODAY
            # Level 1: Yesterday's high/low (immediate)
            s1 = yesterday_low
            r1 = yesterday_high
            
            # Level 2: 20-day high/low (medium term)
            s2 = df['low'].tail(20).min()
            r2 = df['high'].tail(20).max()
            
            # Expected intraday range based on yesterday's ATR or range
            yesterday_atr = df['high'].tail(5).mean() - df['low'].tail(5).mean()
            expected_range = max(yesterday_range, yesterday_atr)
            
            # Signal logic based on yesterday's close position
            signal, reason = self._get_premarket_signal(
                close_position=close_position,
                yesterday_volume_ratio=volume_ratio,
                yesterday_range=yesterday_range,
                yesterday_open=yesterday_open,
                yesterday_close=yesterday_close,
                close_signal=close_signal
            )
            
            # Determine strength
            strength = 'STRONG' if volume_ratio > 1.3 and abs(close_ratio - 0.5) > 0.25 else ('MEDIUM' if volume_ratio > 0.9 else 'WEAK')
            
            return {
                # New structure (detailed)
                'symbol': symbol,
                'date': 'TODAY (premarket view)',
                'yesterday_summary': {
                    'open': round(yesterday_open, 2),
                    'high': round(yesterday_high, 2),
                    'low': round(yesterday_low, 2),
                    'close': round(yesterday_close, 2),
                    'range': round(yesterday_range, 2),
                    'volume': int(yesterday_volume),
                    'close_position': f'{close_signal} {close_position}'
                },
                'volume_analysis': {
                    'yesterday_volume': int(yesterday_volume),
                    'avg_10d_volume': int(volume_avg_10d),
                    'volume_ratio': round(volume_ratio, 2),
                    'trend': volume_trend
                },
                'support_resistance': {
                    'support_1': round(s1, 2),
                    'support_1_label': 'Yesterday Low',
                    'support_2': round(s2, 2),
                    'support_2_label': '20-day Low',
                    'resistance_1': round(r1, 2),
                    'resistance_1_label': 'Yesterday High',
                    'resistance_2': round(r2, 2),
                    'resistance_2_label': '20-day High',
                },
                'today_levels': {
                    'previous_close': round(yesterday_close, 2),
                    'expected_intraday_range': round(expected_range, 2),
                    'range_up': round(yesterday_close + expected_range * 0.5, 2),
                    'range_down': round(yesterday_close - expected_range * 0.5, 2),
                },
                'signal': signal,
                'reason': reason,
                'trading_recommendation': self._get_trading_rec(signal, close_position, volume_trend),
                
                # Old structure (backward compatibility with frontend)
                'strength': strength,
                'gap_percent': 0,  # During premarket, no gap available yet
                'gap_direction': 'NONE',
                'previous_close': round(yesterday_close, 2),
                'current_open': round(yesterday_close, 2),  # Same as close until market opens
                'support_level': round(s1, 2),
                'resistance_level': round(r1, 2),
                'yesterday_volume': int(yesterday_volume),
                'prev_volume_avg': int(volume_avg_10d),
                
                'timestamp': datetime.now(IST).isoformat()
            }
        except Exception as e:
            logger.error(f"Error generating premarket signal for {symbol}: {e}")
            return self._neutral_signal(symbol, str(e))
    
    def _get_premarket_signal(self, close_position, yesterday_volume_ratio, yesterday_range, 
                              yesterday_open, yesterday_close, close_signal) -> tuple:
        """
        Generate signal based on yesterday's close position and volume
        Returns (signal, reason)
        """
        # Bullish scenario: closed in upper range with normal/high volume
        if close_position == 'UPPER' and yesterday_volume_ratio >= 0.9:
            signal = 'BUY'
            reason = f'{close_signal} Strong close in upper range + {yesterday_volume_ratio:.1f}x volume = Expect continuation'
        elif close_position == 'UPPER':
            signal = 'BUY'
            reason = f'{close_signal} Closed in upper range ({(yesterday_close-yesterday_open)/yesterday_open*100:+.2f}%) - Watch for breakout'
        
        # Bearish scenario: closed in lower range with normal/high volume
        elif close_position == 'LOWER' and yesterday_volume_ratio >= 0.9:
            signal = 'SELL'
            reason = f'{close_signal} Strong close in lower range + {yesterday_volume_ratio:.1f}x volume = Expect weakness'
        elif close_position == 'LOWER':
            signal = 'SELL'
            reason = f'{close_signal} Closed in lower range ({(yesterday_close-yesterday_open)/yesterday_open*100:+.2f}%) - Watch for breakdown'
        
        # Neutral/indecision
        else:
            if yesterday_close > yesterday_open:
                signal = 'BUY'
                reason = f'{close_signal} Neutral: Small body in middle range - Slight bullish bias'
            else:
                signal = 'SELL'
                reason = f'{close_signal} Neutral: Small body in middle range - Slight bearish bias'
        
        return signal, reason
    
    def _get_trading_rec(self, signal, close_position, volume_trend) -> str:
        """Get actionable trading recommendation"""
        if signal == 'BUY':
            if volume_trend == 'HIGH':
                return '✅ BUY near support, target resistance | Strong volume backing'
            else:
                return '⚠️ BUY with caution, watch volume | Not fully confirmed'
        elif signal == 'SELL':
            if volume_trend == 'HIGH':
                return '❌ SELL near resistance, target support | Strong volume backing'
            else:
                return '⚠️ SELL with caution, watch volume | Not fully confirmed'
        else:
            return '⏳ WAIT for better setup | Check after market open'
    
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
        """Return neutral signal with backward compatibility"""
        return {
            # New structure
            'symbol': symbol,
            'date': 'TODAY (premarket view)',
            'yesterday_summary': {
                'open': 0,
                'high': 0,
                'low': 0,
                'close': 0,
                'range': 0,
                'volume': 0,
                'close_position': '⏳ NO DATA'
            },
            'volume_analysis': {
                'yesterday_volume': 0,
                'avg_10d_volume': 0,
                'volume_ratio': 0,
                'trend': 'N/A'
            },
            'support_resistance': {
                'support_1': 0,
                'support_1_label': 'N/A',
                'support_2': 0,
                'support_2_label': 'N/A',
                'resistance_1': 0,
                'resistance_1_label': 'N/A',
                'resistance_2': 0,
                'resistance_2_label': 'N/A',
            },
            'today_levels': {
                'previous_close': 0,
                'expected_intraday_range': 0,
                'range_up': 0,
                'range_down': 0,
            },
            'signal': 'NEUTRAL',
            'reason': reason,
            'trading_recommendation': '⏳ WAIT for data',
            
            # Old structure (backward compatibility)
            'strength': 'WEAK',
            'gap_percent': 0,
            'gap_direction': 'NONE',
            'previous_close': 0,
            'current_open': 0,
            'support_level': 0,
            'resistance_level': 0,
            'yesterday_volume': 0,
            'prev_volume_avg': 0,
            
            'timestamp': datetime.now(IST).isoformat()
        }
    
    def get_premarket_signals_batch(self, symbols: List[str]) -> List[Dict]:
        """Get signals for multiple symbols"""
        return [self.get_premarket_signals(sym) for sym in symbols]
