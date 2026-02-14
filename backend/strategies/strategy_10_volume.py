"""
Strategy 10: Volume Analysis
Analyzes volume patterns for confirmation
"""
import pandas as pd
from .base_strategy import BaseStrategy

class VolumeStrategy(BaseStrategy):
    def __init__(self, period=20, volume_threshold=1.5):
        """
        Initialize Volume Strategy
        
        Args:
            period: Period for volume average (default: 20)
            volume_threshold: Volume spike multiplier (default: 1.5x average)
        """
        super().__init__(name=f"Volume({period})")
        self.period = period
        self.volume_threshold = volume_threshold
    
    def calculate(self, df):
        """
        Calculate Volume analysis and generate trading signal
        
        Volume Logic:
        - High volume + price up → Strong buying → BUY
        - High volume + price down → Strong selling → SELL
        - Low volume → NEUTRAL
        
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
        
        # Calculate average volume
        df_copy['avg_volume'] = df_copy['volume'].rolling(window=self.period).mean()
        
        # Calculate price change
        df_copy['price_change'] = df_copy['close'].pct_change() * 100
        
        # Get latest values
        latest_volume = df_copy['volume'].iloc[-1]
        latest_avg_volume = df_copy['avg_volume'].iloc[-1]
        latest_price_change = df_copy['price_change'].iloc[-1]
        latest_price = df_copy['close'].iloc[-1]
        
        # Calculate volume ratio
        volume_ratio = latest_volume / latest_avg_volume if latest_avg_volume > 0 else 1
        
        # Generate signal
        signal = "NEUTRAL"
        
        # High volume spike
        if volume_ratio >= self.volume_threshold:
            # Price going up with high volume
            if latest_price_change > 0.1:
                signal = "BUY"
            # Price going down with high volume
            elif latest_price_change < -0.1:
                signal = "SELL"
        # Normal/low volume - check trend
        else:
            # Gradual price increase
            if latest_price_change > 0.2:
                signal = "BUY"
            # Gradual price decrease
            elif latest_price_change < -0.2:
                signal = "SELL"
        
        # Update internal state
        metadata = {
            'volume': int(latest_volume),
            'avg_volume': int(latest_avg_volume),
            'volume_ratio': round(volume_ratio, 2),
            'price_change_pct': round(latest_price_change, 2),
            'volume_signal': 'spike' if volume_ratio >= self.volume_threshold else 'normal'
        }
        
        self.update_signal(signal, latest_price, **metadata)
        
        return signal
