"""
Strategy 10: Bollinger Bands
Detects breakouts and squeeze situations on 5-minute charts.
- Price breaks above upper band → BUY  (breakout)
- Price breaks below lower band → SELL  (breakdown)
- Price inside bands but band width is very tight (squeeze) → upcoming move, NEUTRAL
- Price near middle band → NEUTRAL
"""
import pandas as pd
from .base_strategy import BaseStrategy


class BollingerBandsStrategy(BaseStrategy):
    def __init__(self, period=20, std_dev=2.0):
        super().__init__(name=f"BB({period},{int(std_dev)})")
        self.period = period
        self.std_dev = std_dev

    def calculate(self, df: pd.DataFrame) -> str:
        self.validate_dataframe(df)

        if len(df) < self.period + 1:
            return "NEUTRAL"

        close = df["close"]

        # Bollinger Bands
        sma = close.rolling(window=self.period).mean()
        std = close.rolling(window=self.period).std()
        upper = sma + self.std_dev * std
        lower = sma - self.std_dev * std

        price = close.iloc[-1]
        cur_upper = upper.iloc[-1]
        cur_lower = lower.iloc[-1]
        cur_sma   = sma.iloc[-1]

        if pd.isna(cur_upper) or pd.isna(cur_lower):
            return "NEUTRAL"

        band_width = (cur_upper - cur_lower) / cur_sma if cur_sma != 0 else 0

        # Squeeze: very narrow bands (< 1% of price) — about to break
        if band_width < 0.01:
            return "NEUTRAL"

        # Breakout above upper band
        if price > cur_upper:
            return "BUY"

        # Breakdown below lower band
        if price < cur_lower:
            return "SELL"

        # Inside bands — check momentum: closer to which band?
        mid_pct = (price - cur_lower) / (cur_upper - cur_lower)
        if mid_pct > 0.80:        # In top 20% of band → bullish
            return "BUY"
        elif mid_pct < 0.20:      # In bottom 20% of band → bearish
            return "SELL"

        return "NEUTRAL"
