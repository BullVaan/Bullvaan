"""
Strategy 8: Stochastic Oscillator
Momentum indicator comparing closing price to price range
"""
import pandas as pd
from .base_strategy import BaseStrategy

class StochasticStrategy(BaseStrategy):
    def __init__(self, k_period=14, d_period=3, oversold=30, overbought=70):
        """
        Initialize Stochastic Strategy
        
        Args:
            k_period: %K period (default: 14)
            d_period: %D smoothing period (default: 3)
            oversold: Oversold threshold (default: 30)
            overbought: Overbought threshold (default: 70)
        """
        super().__init__(name=f"Stoch({k_period},{d_period})")
        self.k_period = k_period
        self.d_period = d_period
        self.oversold = oversold
        self.overbought = overbought
    
    def calculate(self, df):
        """
        Calculate Stochastic Oscillator and generate trading signal
        
        Stochastic Logic:
        - %K < 30 and %K crosses above %D → Oversold reversal → BUY
        - %K > 70 and %K crosses below %D → Overbought reversal → SELL
        - Otherwise → NEUTRAL
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            str: "BUY", "SELL", or "NEUTRAL"
        """
        # Validate input data
        self.validate_dataframe(df)
        
        if len(df) < self.k_period:
            return "NEUTRAL"
        
        df_copy = df.copy()
        
        # Calculate %K
        df_copy['lowest_low'] = df_copy['low'].rolling(window=self.k_period).min()
        df_copy['highest_high'] = df_copy['high'].rolling(window=self.k_period).max()
        
        df_copy['k'] = 100 * ((df_copy['close'] - df_copy['lowest_low']) / 
                               (df_copy['highest_high'] - df_copy['lowest_low']))
        
        # Calculate %D (SMA of %K)
        df_copy['d'] = df_copy['k'].rolling(window=self.d_period).mean()
        
        # Get latest values
        latest_k = df_copy['k'].iloc[-1]
        latest_d = df_copy['d'].iloc[-1]
        latest_price = df_copy['close'].iloc[-1]
        
        # Generate signal
        signal = "NEUTRAL"
        
        if pd.isna(latest_k) or pd.isna(latest_d):
            signal = "NEUTRAL"
        # Oversold and %K > %D
        elif latest_k < self.oversold and latest_k > latest_d:
            signal = "BUY"
        # Overbought and %K < %D
        elif latest_k > self.overbought and latest_k < latest_d:
            signal = "SELL"
        # Generally oversold
        elif latest_k < self.oversold:
            signal = "BUY"
        # Generally overbought
        elif latest_k > self.overbought:
            signal = "SELL"
        
        # Update internal state
        metadata = {
            'k': round(latest_k, 2) if not pd.isna(latest_k) else None,
            'd': round(latest_d, 2) if not pd.isna(latest_d) else None,
            'oversold_threshold': self.oversold,
            'overbought_threshold': self.overbought
        }
        
        self.update_signal(signal, latest_price, **metadata)
        
        return signal
