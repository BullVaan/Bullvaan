"""
Strategy 2: RSI (Relative Strength Index)
Momentum oscillator that measures overbought/oversold conditions
"""
import pandas as pd
from .base_strategy import BaseStrategy

class RSIStrategy(BaseStrategy):
    def __init__(self, period=14, oversold=30, overbought=70):
        """
        Initialize RSI Strategy
        
        Args:
            period: RSI calculation period (default: 14)
            oversold: Oversold threshold (default: 30)
            overbought: Overbought threshold (default: 70)
        """
        super().__init__(name=f"RSI({period})")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
    
    def calculate(self, df):
        """
        Calculate RSI and generate trading signal
        
        RSI Logic:
        - RSI < 30: Oversold → BUY
        - RSI > 70: Overbought → SELL
        - 30 <= RSI <= 70: NEUTRAL
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            str: "BUY", "SELL", or "NEUTRAL"
        """
        # Validate input data
        self.validate_dataframe(df)
        
        if len(df) < self.period + 1:
            return "NEUTRAL"
        
        # Calculate RSI
        close_prices = df['close'].copy()
        
        # Calculate price changes
        delta = close_prices.diff()
        
        # Separate gains and losses
        gains = delta.where(delta > 0, 0)
        losses = -delta.where(delta < 0, 0)
        
        # Calculate average gains and losses
        avg_gains = gains.rolling(window=self.period, min_periods=self.period).mean()
        avg_losses = losses.rolling(window=self.period, min_periods=self.period).mean()
        
        # Calculate RS (Relative Strength)
        rs = avg_gains / avg_losses
        
        # Calculate RSI
        rsi = 100 - (100 / (1 + rs))
        
        # Get latest RSI value
        latest_rsi = rsi.iloc[-1]
        latest_price = close_prices.iloc[-1]
        
        # Determine signal
        if pd.isna(latest_rsi):
            signal = "NEUTRAL"
        elif latest_rsi < self.oversold:
            signal = "BUY"  # Oversold - potential bounce
        elif latest_rsi > self.overbought:
            signal = "SELL"  # Overbought - potential pullback
        else:
            signal = "NEUTRAL"
        
        # Update internal state
        metadata = {
            'rsi': round(latest_rsi, 2),
            'oversold_threshold': self.oversold,
            'overbought_threshold': self.overbought,
            'condition': 'oversold' if latest_rsi < self.oversold else 'overbought' if latest_rsi > self.overbought else 'neutral'
        }
        
        self.update_signal(signal, latest_price, **metadata)
        
        return signal
