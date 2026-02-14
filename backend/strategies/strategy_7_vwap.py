"""
Strategy 7: VWAP (Volume Weighted Average Price)
Intraday benchmark - institutional traders reference point
"""
import pandas as pd
from .base_strategy import BaseStrategy

class VWAPStrategy(BaseStrategy):
    def __init__(self):
        """Initialize VWAP Strategy"""
        super().__init__(name="VWAP")
    
    def calculate(self, df):
        """
        Calculate VWAP and generate trading signal
        
        VWAP Logic:
        - Price above VWAP → Bullish → BUY
        - Price below VWAP → Bearish → SELL
        - Price near VWAP (±0.1%) → NEUTRAL
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            str: "BUY", "SELL", or "NEUTRAL"
        """
        # Validate input data
        self.validate_dataframe(df)
        
        if len(df) < 2:
            return "NEUTRAL"
        
        df_copy = df.copy()
        
        # Calculate typical price
        df_copy['typical_price'] = (df_copy['high'] + df_copy['low'] + df_copy['close']) / 3
        
        # Calculate cumulative TPV (Typical Price × Volume)
        df_copy['tpv'] = df_copy['typical_price'] * df_copy['volume']
        df_copy['cum_tpv'] = df_copy['tpv'].cumsum()
        df_copy['cum_volume'] = df_copy['volume'].cumsum()
        
        # Calculate VWAP
        df_copy['vwap'] = df_copy['cum_tpv'] / df_copy['cum_volume']
        
        # Get latest values
        latest_price = df_copy['close'].iloc[-1]
        latest_vwap = df_copy['vwap'].iloc[-1]
        
        # Calculate distance from VWAP
        distance_percent = ((latest_price - latest_vwap) / latest_vwap) * 100
        
        # Generate signal
        signal = "NEUTRAL"
        
        # Price significantly above VWAP (>0.1%)
        if distance_percent > 0.1:
            signal = "BUY"
        # Price significantly below VWAP (<-0.1%)
        elif distance_percent < -0.1:
            signal = "SELL"
        # Price very close to VWAP (within ±0.1%)
        else:
            signal = "NEUTRAL"
        
        # Update internal state
        metadata = {
            'vwap': round(latest_vwap, 2),
            'distance': round(latest_price - latest_vwap, 2),
            'distance_percent': round(distance_percent, 2)
        }
        
        self.update_signal(signal, latest_price, **metadata)
        
        return signal
