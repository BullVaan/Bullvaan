"""
Strategy 4: Bollinger Bands
Volatility indicator that measures price relative to standard deviations
"""
import pandas as pd
from .base_strategy import BaseStrategy

class BollingerBandsStrategy(BaseStrategy):
    def __init__(self, period=20, std_dev=2):
        """
        Initialize Bollinger Bands Strategy
        
        Args:
            period: Moving average period (default: 20)
            std_dev: Standard deviation multiplier (default: 2)
        """
        super().__init__(name=f"BB({period},{std_dev})")
        self.period = period
        self.std_dev = std_dev
    
    def calculate(self, df):
        """
        Calculate Bollinger Bands and generate trading signal
        
        Bollinger Bands Logic:
        - Price touches/breaks lower band → Oversold → BUY
        - Price touches/breaks upper band → Overbought → SELL
        - Price near middle band → NEUTRAL
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            str: "BUY", "SELL", or "NEUTRAL"
        """
        # Validate input data
        self.validate_dataframe(df)
        
        if len(df) < self.period:
            return "NEUTRAL"
        
        # Calculate Bollinger Bands
        close_prices = df['close'].copy()
        
        # Middle Band = Simple Moving Average
        middle_band = close_prices.rolling(window=self.period).mean()
        
        # Standard Deviation
        std = close_prices.rolling(window=self.period).std()
        
        # Upper Band = Middle + (std_dev * Standard Deviation)
        upper_band = middle_band + (self.std_dev * std)
        
        # Lower Band = Middle - (std_dev * Standard Deviation)
        lower_band = middle_band - (self.std_dev * std)
        
        # Get latest values
        latest_price = close_prices.iloc[-1]
        latest_upper = upper_band.iloc[-1]
        latest_middle = middle_band.iloc[-1]
        latest_lower = lower_band.iloc[-1]
        
        # Calculate position within bands (%)
        band_width = latest_upper - latest_lower
        price_position = ((latest_price - latest_lower) / band_width) * 100 if band_width > 0 else 50
        
        # Generate signal
        signal = "NEUTRAL"
        
        # Price at or below lower band (0-25% of band width)
        if price_position <= 25:
            signal = "BUY"
        # Price at or above upper band (75-100% of band width)
        elif price_position >= 75:
            signal = "SELL"
        # Price in middle zone (45-55%)
        elif 45 <= price_position <= 55:
            signal = "NEUTRAL"
        # Price in lower-middle zone (25-45%)
        elif 25 < price_position < 45:
            signal = "BUY"
        # Price in upper-middle zone (55-75%)
        elif 55 < price_position < 75:
            signal = "SELL"
        
        # Update internal state
        metadata = {
            'upper_band': round(latest_upper, 2),
            'middle_band': round(latest_middle, 2),
            'lower_band': round(latest_lower, 2),
            'price_position': round(price_position, 2),
            'band_width': round(band_width, 2)
        }
        
        self.update_signal(signal, latest_price, **metadata)
        
        return signal
