"""
Moving Average Strategy
Simple but effective trend-following strategy

Logic:
- Calculate average price of last N candles
- If current price > MA → Uptrend → BUY
- If current price < MA → Downtrend → SELL
- If equal or no data → NEUTRAL
"""

import pandas as pd
from .base_strategy import BaseStrategy, SIGNAL_BUY, SIGNAL_SELL, SIGNAL_NEUTRAL

class MovingAverageStrategy(BaseStrategy):
    """
    Moving Average Strategy Implementation
    
    Compares current price with moving average to determine trend
    """
    
    def __init__(self, period: int = 20):
        """
        Initialize Moving Average Strategy
        
        Args:
            period: Number of candles for MA calculation (default: 20)
        """
        super().__init__(name=f"MA({period})")
        self.period = period
    
    def calculate(self, df: pd.DataFrame) -> str:
        """
        Calculate Moving Average and generate signal
        
        Args:
            df: DataFrame with columns ['open', 'high', 'low', 'close', 'volume']
        
        Returns:
            Signal: BUY, SELL, or NEUTRAL
        """
        # Validate DataFrame
        if not self.validate_dataframe(df):
            self.update_signal(SIGNAL_NEUTRAL, metadata={"error": "Invalid DataFrame"})
            return SIGNAL_NEUTRAL
        
        # Need enough data for MA calculation
        if len(df) < self.period:
            self.update_signal(SIGNAL_NEUTRAL, metadata={"error": f"Not enough data (need {self.period} candles)"})
            return SIGNAL_NEUTRAL

        # Calculate Moving Average
        df = df.copy()  # Don't modify original
        df['ma'] = df['close'].rolling(window=self.period).mean()
        
        # Get latest values
        latest = df.iloc[-1]
        current_price = latest['close']
        ma_value = latest['ma']

        # Check if MA is valid (not NaN)
        if pd.isna(ma_value):
            self.update_signal(SIGNAL_NEUTRAL, metadata={"error": "MA value is NaN"})
            return SIGNAL_NEUTRAL
        
        # Generate signal based on price vs MA
        if current_price > ma_value:
            signal = SIGNAL_BUY
        elif current_price < ma_value:
            signal = SIGNAL_SELL
        else:
            signal = SIGNAL_NEUTRAL
        
        # Update signal with metadata
        self.update_signal(
            signal=signal,
            price=current_price,
            ma_value=ma_value,
            ma_period=self.period,
            distance_from_ma=current_price - ma_value,
            distance_percent=((current_price - ma_value) / ma_value) * 100
        )
        
        return signal


# Test the strategy
if __name__ == "__main__":
    print("=" * 60)
    print("Moving Average Strategy Test")
    print("=" * 60)
    
    # Create sample price data (simulating 5-min candles)
    import numpy as np
    
    dates = pd.date_range(start='2026-02-01 09:15', periods=50, freq='5min')
    
    # Generate sample OHLC data (trending upward)
    np.random.seed(42)
    close_prices = 100 + np.cumsum(np.random.randn(50) * 0.5)  # Random walk starting at 100
    
    sample_data = pd.DataFrame({
        'timestamp': dates,
        'open': close_prices + np.random.randn(50) * 0.2,
        'high': close_prices + np.abs(np.random.randn(50) * 0.5),
        'low': close_prices - np.abs(np.random.randn(50) * 0.5),
        'close': close_prices,
        'volume': np.random.randint(1000, 10000, 50)
    })
    
    # Test with period=20
    strategy = MovingAverageStrategy(period=20)
    signal = strategy.calculate(sample_data)
    
    print(f"\nStrategy: {strategy.name}")
    print(f"Period: {strategy.period}")
    print(f"Signal: {signal}")
    print(f"\nSignal Details:")
    signal_data = strategy.get_signal()
    for key, value in signal_data.items():
        if key == 'metadata':
            print(f"  {key}:")
            for k, v in value.items():
                if isinstance(v, float):
                    print(f"    {k}: {v:.2f}")
                else:
                    print(f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("Last 5 Candles:")
    print(sample_data[['timestamp', 'close']].tail())
    print("=" * 60)