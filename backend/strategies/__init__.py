"""
Trading Strategies Package
Contains all strategy implementations
"""

# Import base strategy and constants
from .base_strategy import BaseStrategy, SIGNAL_BUY, SIGNAL_SELL, SIGNAL_NEUTRAL

# Import strategy implementations
from .strategy_1_moving_average import MovingAverageStrategy

# Export all strategies
__all__ = [
    'BaseStrategy',
    'SIGNAL_BUY',
    'SIGNAL_SELL', 
    'SIGNAL_NEUTRAL',
    'MovingAverageStrategy',
]