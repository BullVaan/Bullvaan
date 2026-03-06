"""
Strategy 8: Stochastic Oscillator
Fast oscillator for overbought/oversold detection
Perfect for scalping and mean-reversion trades
"""
import pandas as pd
import numpy as np
from .base_strategy import BaseStrategy

class StochasticStrategy(BaseStrategy):
    def __init__(self, k_period=5, k_smooth=3, d_smooth=3):
        """
        Initialize Stochastic Strategy
        
        Args:
            k_period: Period for %K calculation (default: 5 for scalping)
            k_smooth: Smoothing for %K (default: 3)
            d_smooth: Smoothing for %D (default: 3)
        """
        super().__init__(name=f"Stoch({k_period},{k_smooth},{d_smooth})")
        self.k_period = k_period
        self.k_smooth = k_smooth
        self.d_smooth = d_smooth
    
    def calculate(self, df):
        """
        Calculate Stochastic and generate trading signal
        
        Stochastic Logic:
        - %K < 20: Oversold → BUY
        - %K > 80: Overbought → SELL
        - 20 <= %K <= 80: NEUTRAL
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            str: "BUY", "SELL", or "NEUTRAL"
        """
        # Validate input data
        self.validate_dataframe(df)
        
        if len(df) < self.k_period + 1:
            return "NEUTRAL"
        
        df_copy = df.copy()
        
        # Calculate Highest High and Lowest Low over k_period
        df_copy['highest_high'] = df_copy['high'].rolling(window=self.k_period).max()
        df_copy['lowest_low'] = df_copy['low'].rolling(window=self.k_period).min()
        
        # Calculate %K (Fast Stochastic)
        df_copy['fastk'] = 100 * (
            (df_copy['close'] - df_copy['lowest_low']) / 
            (df_copy['highest_high'] - df_copy['lowest_low'])
        )
        
        # Replace NaN with 50 (neutral)
        df_copy['fastk'] = df_copy['fastk'].fillna(50)
        
        # Calculate %K (Slow - smoothed Fast K)
        df_copy['stoch_k'] = df_copy['fastk'].rolling(window=self.k_smooth).mean()
        
        # Calculate %D (Signal line - smoothed %K)
        df_copy['stoch_d'] = df_copy['stoch_k'].rolling(window=self.d_smooth).mean()
        
        # Get latest values
        latest_k = df_copy['stoch_k'].iloc[-1]
        latest_d = df_copy['stoch_d'].iloc[-1]
        latest_price = df_copy['close'].iloc[-1]
        
        # Handle NaN values
        if pd.isna(latest_k):
            return "NEUTRAL"
        
        # Generate signal
        if latest_k < 20:
            signal = "BUY"
        elif latest_k > 80:
            signal = "SELL"
        else:
            signal = "NEUTRAL"
        
        # Update internal state
        metadata = {
            'stoch_k': round(latest_k, 2),
            'stoch_d': round(latest_d, 2) if not pd.isna(latest_d) else None,
            'condition': 'oversold' if latest_k < 20 else 'overbought' if latest_k > 80 else 'neutral'
        }
        
        self.update_signal(signal, latest_price, **metadata)
        
        return signal
