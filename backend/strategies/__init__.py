"""
Trading Strategies Package
Contains all 7 strategy implementations (3 categories)
"""

from .base_strategy import BaseStrategy, SIGNAL_BUY, SIGNAL_SELL, SIGNAL_NEUTRAL

# Trend (2)
from .strategy_1_moving_average import MovingAverageStrategy
from .strategy_5_ema_crossover import EMACrossoverStrategy

# Momentum (3)
from .strategy_2_rsi import RSIStrategy
from .strategy_3_macd import MACDStrategy
from .strategy_8_stochastic import StochasticStrategy

# Strength (2)
from .strategy_6_supertrend import SupertrendStrategy
from .strategy_9_adx import ADXStrategy

#Export All Strategies
__all__ = [
    'BaseStrategy', 'SIGNAL_BUY', 'SIGNAL_SELL', 'SIGNAL_NEUTRAL',
    # Trend
    'MovingAverageStrategy', 'EMACrossoverStrategy',
    # Momentum
    'RSIStrategy', 'MACDStrategy', 'StochasticStrategy',
    # Strength
    'SupertrendStrategy', 'ADXStrategy',
]