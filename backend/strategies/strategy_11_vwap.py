"""
Strategy 11: VWAP (Volume Weighted Average Price)
The single most important intraday indicator for index options.
Institutions use VWAP as their benchmark — price above = bullish, below = bearish.

Signal logic:
- Price clearly above VWAP + rising momentum → BUY
- Price clearly below VWAP + falling momentum → SELL
- Price hugging VWAP (within 0.1%) → NEUTRAL (choppy zone)
"""
import pandas as pd
from .base_strategy import BaseStrategy


class VWAPStrategy(BaseStrategy):
    def __init__(self, band_pct=0.001):
        """
        band_pct: % distance from VWAP to consider as 'hugging' (neutral zone).
                  Default 0.1% (0.001). NIFTY at 22000 → ±22 points neutral zone.
        """
        super().__init__(name="VWAP")
        self.band_pct = band_pct

    def calculate(self, df: pd.DataFrame) -> str:
        self.validate_dataframe(df)

        if len(df) < 5:
            return "NEUTRAL"

        df_copy = df.copy()

        # VWAP = cumulative(price * volume) / cumulative(volume)
        # For intraday we reset at session open each day.
        # Since df may contain multiple days, we group by date.
        df_copy["date"] = pd.to_datetime(df_copy.index).date if not isinstance(
            df_copy.index, pd.DatetimeIndex
        ) else df_copy.index.date

        # Use only today's candles if we have them, else use last 50 candles
        today = df_copy["date"].iloc[-1]
        today_df = df_copy[df_copy["date"] == today]
        if len(today_df) < 3:
            today_df = df_copy.tail(50)

        typical_price = (today_df["high"] + today_df["low"] + today_df["close"]) / 3
        volume = today_df["volume"].replace(0, 1)  # Avoid division by zero

        cum_tp_vol = (typical_price * volume).cumsum()
        cum_vol    = volume.cumsum()
        vwap       = cum_tp_vol / cum_vol

        current_price = today_df["close"].iloc[-1]
        current_vwap  = vwap.iloc[-1]

        if pd.isna(current_vwap) or current_vwap == 0:
            return "NEUTRAL"

        deviation = (current_price - current_vwap) / current_vwap

        # Neutral zone: price too close to VWAP
        if abs(deviation) < self.band_pct:
            return "NEUTRAL"

        # Check momentum: is last candle confirming the direction?
        last_close = today_df["close"].iloc[-1]
        prev_close = today_df["close"].iloc[-2] if len(today_df) >= 2 else last_close
        momentum_up   = last_close >= prev_close
        momentum_down = last_close <= prev_close

        if deviation > 0 and momentum_up:
            return "BUY"
        elif deviation < 0 and momentum_down:
            return "SELL"
        elif deviation > 0:
            return "BUY"   # Above VWAP even without confirming candle
        else:
            return "SELL"
