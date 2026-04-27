"""
Strategy 13: Key Level Proximity
Checks if price is near a key level — a critical confluence filter for scalping.

Key levels checked (in priority order):
  1. Previous Day High (PDH)
  2. Previous Day Low (PDL)
  3. Round numbers (every 100 pts for NIFTY, 200 for BANKNIFTY)
  4. Previous Day Close (PDC) — acts as psychological level

Signal logic:
  - Price within `proximity_pts` of a key level → BUY/SELL based on direction
    - Near PDH/resistance + price below level → SELL (likely to reject)
    - Near PDH/resistance + price above level (breakout) → BUY
    - Near PDL/support + price above level → BUY (bouncing)
    - Near PDL/support + price below level (breakdown) → SELL
  - Price not near any key level → NEUTRAL (mid-range, risky zone)
"""
import pandas as pd
from .base_strategy import BaseStrategy


class KeyLevelStrategy(BaseStrategy):
    def __init__(self, proximity_pts=30, round_number_interval=100):
        """
        proximity_pts: How many points away from a level to consider "near".
                       30 pts for NIFTY (≈0.13%), 50-60 for BANKNIFTY.
                       We use 30 as a reasonable default for all indices.
        round_number_interval: Interval for round numbers (100 for NIFTY).
        """
        super().__init__(name="KeyLevel")
        self.proximity_pts = proximity_pts
        self.round_number_interval = round_number_interval

    def calculate(self, df: pd.DataFrame) -> str:
        self.validate_dataframe(df)

        if len(df) < 2:
            return "NEUTRAL"

        # ── Get previous day's OHLC ─────────────────────────────
        df_copy = df.copy()
        if not isinstance(df_copy.index, pd.DatetimeIndex):
            try:
                df_copy.index = pd.to_datetime(df_copy.index)
            except Exception:
                return "NEUTRAL"

        df_copy["date"] = df_copy.index.date
        today = df_copy["date"].iloc[-1]
        prev_days = df_copy[df_copy["date"] < today]

        if len(prev_days) == 0:
            # No previous day data — fall back to session high/low from current data
            prev_day = df_copy
        else:
            last_prev_date = prev_days["date"].iloc[-1]
            prev_day = prev_days[prev_days["date"] == last_prev_date]

        pdh = float(prev_day["high"].max())
        pdl = float(prev_day["low"].min())
        pdc = float(prev_day["close"].iloc[-1])

        current_price = float(df_copy["close"].iloc[-1])
        prox = self.proximity_pts

        # ── Find nearest round number ──────────────────────────
        interval = self.round_number_interval
        nearest_round_below = (current_price // interval) * interval
        nearest_round_above = nearest_round_below + interval
        round_levels = [nearest_round_below, nearest_round_above]

        # ── Collect all key levels with their type ─────────────
        levels = [
            ("PDH", pdh, "resistance"),
            ("PDL", pdl, "support"),
            ("PDC", pdc, "pivot"),
        ]
        for r in round_levels:
            if r > 0:
                levels.append(("Round", r, "round"))

        # ── Check proximity ─────────────────────────────────────
        nearest_level = None
        nearest_dist = float("inf")
        nearest_type = None
        nearest_role = None

        for name, level, role in levels:
            dist = abs(current_price - level)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_level = level
                nearest_type = name
                nearest_role = role

        if nearest_dist > prox:
            # Not near any key level — mid-range, low probability zone
            return "NEUTRAL"

        # ── Price is near a key level → determine direction ─────
        if nearest_role == "resistance":  # PDH
            if current_price >= nearest_level:
                # Breakout above resistance → BUY
                return "BUY"
            else:
                # Approaching resistance from below → SELL (likely rejection)
                return "SELL"

        elif nearest_role == "support":  # PDL
            if current_price <= nearest_level:
                # Breakdown below support → SELL
                return "SELL"
            else:
                # Bouncing off support → BUY
                return "BUY"

        elif nearest_role == "pivot":  # PDC
            # At previous close: direction = current candle direction
            last_open = float(df_copy["open"].iloc[-1])
            return "BUY" if current_price >= last_open else "SELL"

        else:  # Round number
            # Round numbers act as both support and resistance
            # Direction follows the candle
            last_open = float(df_copy["open"].iloc[-1])
            return "BUY" if current_price >= last_open else "SELL"
