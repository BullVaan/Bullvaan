"""
Base Strategy Class
Abstract base class that all trading strategies must inherit from
Provides common structure and methods for all strategies
"""

from abc import ABC, abstractmethod
import pandas as pd
from datetime import datetime

# Signal constants
SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"
SIGNAL_NEUTRAL = "NEUTRAL"

class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies
    
    All strategies must implement:
    - calculate(df): Calculate indicator and generate signal
    """
    
    def __init__(self, name: str):
        """
        Initialize strategy
        
        Args:
            name: Strategy name (e.g., "RSI", "Moving Average")
        """
        self.name = name
        self.signal = SIGNAL_NEUTRAL  # Default signal
        self.last_updated = None
        self.signal_price = None
        self.metadata = {}  # Store additional info


    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> str:
        """
        Calculate the strategy indicator and generate signal
        This method MUST be implemented by all child strategies
        
        Args:
            df: DataFrame with OHLC data (columns: open, high, low, close, volume)
        
        Returns:
            Signal string: BUY, SELL, or NEUTRAL
        """
        pass

    
    def get_signal(self) -> dict:
        """
        Get current signal with metadata
        
        Returns:
            Dictionary with signal, strategy name, timestamp, and metadata
        """
        return {
            "strategy": self.name,
            "signal": self.signal,
            "timestamp": self.last_updated,
            "price": self.signal_price,
            "metadata": self.metadata
        }


    def update_signal(self, signal: str, price: float = None, **metadata):
        """
        Update the strategy signal and metadata
        
        Args:
            signal: New signal (BUY/SELL/NEUTRAL)
            price: Price at signal generation
            **metadata: Additional data to store
        """
        self.signal = signal
        self.signal_price = price
        self.last_updated = datetime.now()
        self.metadata.update(metadata)

    

    def __repr__(self):
        """String representation of strategy"""
        return f"<{self.name} signal={self.signal} updated={self.last_updated}>"
    
    def __str__(self):
        """Human-readable string"""
        return f"{self.name}: {self.signal}"



    @staticmethod
    def validate_dataframe(df: pd.DataFrame) -> bool:
        """
        Validate that DataFrame has required columns
        
        Args:
            df: DataFrame to validate
        
        Returns:
            True if valid, False otherwise
        """
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        
        if df is None or df.empty:
            return False
        
        for col in required_columns:
            if col not in df.columns:
                return False
        
        return True



# Example test
if __name__ == "__main__":
    # You can't create instance of abstract class directly
    # This would fail: strategy = BaseStrategy("Test")
    
    print("=" * 50)
    print("Base Strategy Template")
    print("=" * 50)
    print("This is an abstract class.")
    print("All strategies must inherit from this class")
    print("and implement the calculate() method.")
    print()
    print("Signal Constants:")
    print(f"  BUY: {SIGNAL_BUY}")
    print(f"  SELL: {SIGNAL_SELL}")
    print(f"  NEUTRAL: {SIGNAL_NEUTRAL}")
    print("=" * 50)