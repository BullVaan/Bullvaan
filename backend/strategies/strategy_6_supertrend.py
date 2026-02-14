"""
Strategy 6: Supertrend
Trend-following indicator based on ATR (Average True Range)
"""
import pandas as pd
import numpy as np
from .base_strategy import BaseStrategy

class SupertrendStrategy(BaseStrategy):
    def __init__(self, period=10, multiplier=3):
        """
        Initialize Supertrend Strategy
        
        Args:
            period: ATR period (default: 10)
            multiplier: ATR multiplier (default: 3)
        """
        super().__init__(name=f"Supertrend({period},{multiplier})")
        self.period = period
        self.multiplier = multiplier
    
    def calculate(self, df):
        """
        Calculate Supertrend and generate trading signal
        
        Supertrend Logic:
        - Price above Supertrend line → Uptrend → BUY
        - Price below Supertrend line → Downtrend → SELL
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            str: "BUY", "SELL", or "NEUTRAL"
        """
        # Validate input data
        self.validate_dataframe(df)
        
        if len(df) < self.period:
            return "NEUTRAL"
        
        df_copy = df.copy()
        
        # Calculate True Range (TR)
        df_copy['prev_close'] = df_copy['close'].shift(1)
        df_copy['high_low'] = df_copy['high'] - df_copy['low']
        df_copy['high_pc'] = abs(df_copy['high'] - df_copy['prev_close'])
        df_copy['low_pc'] = abs(df_copy['low'] - df_copy['prev_close'])
        
        df_copy['tr'] = df_copy[['high_low', 'high_pc', 'low_pc']].max(axis=1)
        
        # Calculate ATR (Average True Range)
        df_copy['atr'] = df_copy['tr'].rolling(window=self.period).mean()
        
        # Calculate basic upper and lower bands
        df_copy['hl_avg'] = (df_copy['high'] + df_copy['low']) / 2
        df_copy['basic_upper'] = df_copy['hl_avg'] + (self.multiplier * df_copy['atr'])
        df_copy['basic_lower'] = df_copy['hl_avg'] - (self.multiplier * df_copy['atr'])
        
        # Calculate final Supertrend bands
        df_copy['final_upper'] = df_copy['basic_upper']
        df_copy['final_lower'] = df_copy['basic_lower']
        
        # Supertrend calculation
        supertrend = []
        for i in range(len(df_copy)):
            if i < self.period:
                supertrend.append(np.nan)
            else:
                if i == self.period:
                    # Initial value
                    if df_copy['close'].iloc[i] > df_copy['basic_upper'].iloc[i]:
                        supertrend.append(df_copy['basic_lower'].iloc[i])
                    else:
                        supertrend.append(df_copy['basic_upper'].iloc[i])
                else:
                    # Subsequent values
                    prev_supertrend = supertrend[i-1]
                    
                    if df_copy['close'].iloc[i] > prev_supertrend:
                        # Uptrend
                        supertrend.append(df_copy['basic_lower'].iloc[i])
                    else:
                        # Downtrend
                        supertrend.append(df_copy['basic_upper'].iloc[i])
        
        df_copy['supertrend'] = supertrend
        
        # Get latest values
        latest_price = df_copy['close'].iloc[-1]
        latest_supertrend = df_copy['supertrend'].iloc[-1]
        
        # Generate signal
        if pd.isna(latest_supertrend):
            signal = "NEUTRAL"
        elif latest_price > latest_supertrend:
            signal = "BUY"
        elif latest_price < latest_supertrend:
            signal = "SELL"
        else:
            signal = "NEUTRAL"
        
        # Update internal state
        metadata = {
            'supertrend': round(latest_supertrend, 2) if not pd.isna(latest_supertrend) else None,
            'atr': round(df_copy['atr'].iloc[-1], 2) if not pd.isna(df_copy['atr'].iloc[-1]) else None,
            'trend': 'up' if signal == "BUY" else 'down' if signal == "SELL" else 'neutral'
        }
        
        self.update_signal(signal, latest_price, **metadata)
        
        return signal
