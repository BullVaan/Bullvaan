"""
Strategy 3: MACD (Moving Average Convergence Divergence)
Momentum indicator that shows the relationship between two moving averages
"""
import pandas as pd
from .base_strategy import BaseStrategy

class MACDStrategy(BaseStrategy):
    def __init__(self, fast_period=5, slow_period=13, signal_period=1):
        """
        Initialize MACD Strategy
        
        Args:
            fast_period: Fast EMA period (default: 5 for scalping, vs 12 for normal)
            slow_period: Slow EMA period (default: 13 for scalping, vs 26 for normal)
            signal_period: Signal line EMA period (default: 1 for scalping, vs 9 for normal)
        """
        super().__init__(name=f"MACD({fast_period},{slow_period},{signal_period})")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
    
    def calculate(self, df):
        """
        Calculate MACD and generate trading signal
        
        MACD Logic:
        - MACD crosses above Signal → Bullish → BUY
        - MACD crosses below Signal → Bearish → SELL
        - No crossover → NEUTRAL
        
        Args:
            df: DataFrame with OHLC data
            
        Returns:
            str: "BUY", "SELL", or "NEUTRAL"
        """
        # Validate input data
        self.validate_dataframe(df)
        
        if len(df) < self.slow_period + self.signal_period:
            return "NEUTRAL"
        
        # Calculate MACD components
        close_prices = df['close'].copy()
        
        # Calculate EMAs
        fast_ema = close_prices.ewm(span=self.fast_period, adjust=False).mean()
        slow_ema = close_prices.ewm(span=self.slow_period, adjust=False).mean()
        
        # MACD Line = Fast EMA - Slow EMA
        macd_line = fast_ema - slow_ema
        
        # Signal Line = EMA of MACD Line
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
        
        # MACD Histogram = MACD Line - Signal Line
        histogram = macd_line - signal_line
        
        # Get current and previous values
        latest_macd = macd_line.iloc[-1]
        latest_signal = signal_line.iloc[-1]
        latest_histogram = histogram.iloc[-1]
        
        prev_macd = macd_line.iloc[-2] if len(macd_line) > 1 else latest_macd
        prev_signal = signal_line.iloc[-2] if len(signal_line) > 1 else latest_signal
        
        latest_price = close_prices.iloc[-1]
        
        # Detect crossover
        signal = "NEUTRAL"
        
        # Bullish crossover: MACD crosses above Signal
        if prev_macd <= prev_signal and latest_macd > latest_signal:
            signal = "BUY"
        # Bearish crossover: MACD crosses below Signal
        elif prev_macd >= prev_signal and latest_macd < latest_signal:
            signal = "SELL"
        # Additional momentum check - histogram growing
        elif latest_histogram > 0 and latest_macd > latest_signal:
            signal = "BUY"
        elif latest_histogram < 0 and latest_macd < latest_signal:
            signal = "SELL"
        
        # Update internal state
        metadata = {
            'macd': round(latest_macd, 2),
            'signal_line': round(latest_signal, 2),
            'histogram': round(latest_histogram, 2),
            'crossover': 'bullish' if signal == "BUY" else 'bearish' if signal == "SELL" else 'none'
        }
        
        self.update_signal(signal, latest_price, **metadata)
        
        return signal
