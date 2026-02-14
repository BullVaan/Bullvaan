"""
Strategy 5: EMA Crossover
Fast and slow exponential moving averages crossover strategy
"""
import pandas as pd
from .base_strategy import BaseStrategy

class EMACrossoverStrategy(BaseStrategy):
    def __init__(self, fast_period=9, slow_period=21):
        """
        Initialize EMA Crossover Strategy
        
        Args:
            fast_period: Fast EMA period (default: 9)
            slow_period: Slow EMA period (default: 21)
        """
        super().__init__(name=f"EMA({fast_period},{slow_period})")
        self.fast_period = fast_period
        self.slow_period = slow_period
    
    def calculate(self, df):
        """
        Calculate EMA Crossover and generate trading signal
        
        EMA Crossover Logic:
        - Fast EMA > Slow EMA → Uptrend → BUY
        - Fast EMA < Slow EMA → Downtrend → SELL
        - Fast EMA ≈ Slow EMA → NEUTRAL
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            str: "BUY", "SELL", or "NEUTRAL"
        """
        # Validate input data
        self.validate_dataframe(df)
        
        if len(df) < self.slow_period:
            return "NEUTRAL"
        
        # Calculate EMAs
        close_prices = df['close'].copy()
        
        fast_ema = close_prices.ewm(span=self.fast_period, adjust=False).mean()
        slow_ema = close_prices.ewm(span=self.slow_period, adjust=False).mean()
        
        # Get latest values
        latest_fast = fast_ema.iloc[-1]
        latest_slow = slow_ema.iloc[-1]
        latest_price = close_prices.iloc[-1]
        
        # Calculate distance between EMAs
        distance = latest_fast - latest_slow
        distance_percent = (distance / latest_slow) * 100
        
        # Generate signal
        signal = "NEUTRAL"
        
        # Fast EMA significantly above Slow EMA (>0.02% - more sensitive for scalping)
        if distance_percent > 0.02:
            signal = "BUY"
        # Fast EMA significantly below Slow EMA (<-0.02%)
        elif distance_percent < -0.02:
            signal = "SELL"
        # EMAs very close together (within ±0.02%)
        else:
            signal = "NEUTRAL"
        
        # Update internal state
        metadata = {
            'fast_ema': round(latest_fast, 2),
            'slow_ema': round(latest_slow, 2),
            'distance': round(distance, 2),
            'distance_percent': round(distance_percent, 2)
        }
        
        self.update_signal(signal, latest_price, **metadata)
        
        return signal
