"""
Strategy 9: ADX (Average Directional Index)
Measures trend strength - helps avoid ranging markets
"""
import pandas as pd
from .base_strategy import BaseStrategy

class ADXStrategy(BaseStrategy):
    def __init__(self, period=14, adx_threshold=25):
        """
        Initialize ADX Strategy
        
        Args:
            period: ADX period (default: 14)
            adx_threshold: Minimum ADX for strong trend (default: 25)
        """
        super().__init__(name=f"ADX({period})")
        self.period = period
        self.adx_threshold = adx_threshold
    
    def calculate(self, df):
        """
        Calculate ADX and generate trading signal
        
        ADX Logic:
        - ADX > 25 and +DI > -DI → Strong uptrend → BUY
        - ADX > 25 and -DI > +DI → Strong downtrend → SELL
        - ADX < 25 → Weak trend → NEUTRAL
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            str: "BUY", "SELL", or "NEUTRAL"
        """
        # Validate input data
        self.validate_dataframe(df)
        
        if len(df) < self.period + 1:
            return "NEUTRAL"
        
        df_copy = df.copy()
        
        # Calculate +DM and -DM
        df_copy['high_diff'] = df_copy['high'].diff()
        df_copy['low_diff'] = -df_copy['low'].diff()
        
        df_copy['plus_dm'] = df_copy.apply(
            lambda row: row['high_diff'] if row['high_diff'] > row['low_diff'] and row['high_diff'] > 0 else 0,
            axis=1
        )
        df_copy['minus_dm'] = df_copy.apply(
            lambda row: row['low_diff'] if row['low_diff'] > row['high_diff'] and row['low_diff'] > 0 else 0,
            axis=1
        )
        
        # Calculate True Range
        df_copy['prev_close'] = df_copy['close'].shift(1)
        df_copy['high_low'] = df_copy['high'] - df_copy['low']
        df_copy['high_pc'] = abs(df_copy['high'] - df_copy['prev_close'])
        df_copy['low_pc'] = abs(df_copy['low'] - df_copy['prev_close'])
        df_copy['tr'] = df_copy[['high_low', 'high_pc', 'low_pc']].max(axis=1)
        
        # Smooth +DM, -DM, and TR
        df_copy['plus_dm_smooth'] = df_copy['plus_dm'].rolling(window=self.period).sum()
        df_copy['minus_dm_smooth'] = df_copy['minus_dm'].rolling(window=self.period).sum()
        df_copy['tr_smooth'] = df_copy['tr'].rolling(window=self.period).sum()
        
        # Calculate +DI and -DI
        df_copy['plus_di'] = 100 * (df_copy['plus_dm_smooth'] / df_copy['tr_smooth'])
        df_copy['minus_di'] = 100 * (df_copy['minus_dm_smooth'] / df_copy['tr_smooth'])
        
        # Calculate DX and ADX
        df_copy['dx'] = 100 * abs(df_copy['plus_di'] - df_copy['minus_di']) / (df_copy['plus_di'] + df_copy['minus_di'])
        df_copy['adx'] = df_copy['dx'].rolling(window=self.period).mean()
        
        # Get latest values
        latest_adx = df_copy['adx'].iloc[-1]
        latest_plus_di = df_copy['plus_di'].iloc[-1]
        latest_minus_di = df_copy['minus_di'].iloc[-1]
        latest_price = df_copy['close'].iloc[-1]
        
        # Generate signal
        signal = "NEUTRAL"
        
        if pd.isna(latest_adx) or pd.isna(latest_plus_di) or pd.isna(latest_minus_di):
            signal = "NEUTRAL"
        # Strong uptrend
        elif latest_adx > self.adx_threshold and latest_plus_di > latest_minus_di:
            signal = "BUY"
        # Strong downtrend
        elif latest_adx > self.adx_threshold and latest_minus_di > latest_plus_di:
            signal = "SELL"
        # Weak trend
        else:
            signal = "NEUTRAL"
        
        # Update internal state
        metadata = {
            'adx': round(latest_adx, 2) if not pd.isna(latest_adx) else None,
            'plus_di': round(latest_plus_di, 2) if not pd.isna(latest_plus_di) else None,
            'minus_di': round(latest_minus_di, 2) if not pd.isna(latest_minus_di) else None,
            'trend_strength': 'strong' if latest_adx > self.adx_threshold else 'weak'
        }
        
        self.update_signal(signal, latest_price, **metadata)
        
        return signal
