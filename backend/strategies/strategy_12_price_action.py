"""
Strategy 12: Price Action / Candle Patterns
Detects key reversal and continuation candle patterns on 5-minute charts.

Patterns detected:
  BULLISH  → BUY  signal:
    - Hammer (bullish reversal at bottom)
    - Bullish Engulfing
    - Bullish Marubozu (strong bull candle)
    - Morning Star (3-candle reversal)

  BEARISH  → SELL signal:
    - Shooting Star / Inverted Hammer (at top)
    - Bearish Engulfing
    - Bearish Marubozu (strong bear candle)
    - Evening Star (3-candle reversal)

  NEUTRAL patterns → no trade:
    - Doji (indecision)
    - Spinning top
    - No recognisable pattern
"""
import pandas as pd
from .base_strategy import BaseStrategy


def _body(candle):
    return abs(candle["close"] - candle["open"])

def _range(candle):
    return candle["high"] - candle["low"]

def _upper_wick(candle):
    return candle["high"] - max(candle["open"], candle["close"])

def _lower_wick(candle):
    return min(candle["open"], candle["close"]) - candle["low"]

def _is_bull(candle):
    return candle["close"] > candle["open"]

def _is_bear(candle):
    return candle["close"] < candle["open"]


class PriceActionStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="PriceAction")

    def calculate(self, df: pd.DataFrame) -> str:
        self.validate_dataframe(df)

        if len(df) < 3:
            return "NEUTRAL"

        c0 = df.iloc[-1]   # Latest candle
        c1 = df.iloc[-2]   # Previous candle
        c2 = df.iloc[-3]   # Two candles ago

        r0 = _range(c0)
        b0 = _body(c0)
        uw0 = _upper_wick(c0)
        lw0 = _lower_wick(c0)

        if r0 == 0:
            return "NEUTRAL"

        body_ratio = b0 / r0   # How much of the candle is body

        # ── DOJI (indecision) ──────────────────────────────────────
        # Body < 10% of range
        if body_ratio < 0.10:
            return "NEUTRAL"

        # ── MARUBOZU ──────────────────────────────────────────────
        # Body > 80% of range → very strong candle, no wicks
        if body_ratio > 0.80:
            return "BUY" if _is_bull(c0) else "SELL"

        # ── HAMMER (bullish reversal) ──────────────────────────────
        # Small body at top, long lower wick (≥2× body), tiny upper wick
        if (
            _is_bull(c0)
            and lw0 >= 2 * b0
            and uw0 <= 0.2 * r0
            and body_ratio < 0.35
        ):
            return "BUY"

        # ── SHOOTING STAR (bearish reversal) ──────────────────────
        # Small body at bottom, long upper wick (≥2× body), tiny lower wick
        if (
            _is_bear(c0)
            and uw0 >= 2 * b0
            and lw0 <= 0.2 * r0
            and body_ratio < 0.35
        ):
            return "SELL"

        # ── BULLISH ENGULFING ──────────────────────────────────────
        # Current bull candle body completely wraps previous bear candle body
        if (
            _is_bull(c0)
            and _is_bear(c1)
            and c0["open"] <= c1["close"]
            and c0["close"] >= c1["open"]
            and b0 > _body(c1)
        ):
            return "BUY"

        # ── BEARISH ENGULFING ──────────────────────────────────────
        if (
            _is_bear(c0)
            and _is_bull(c1)
            and c0["open"] >= c1["close"]
            and c0["close"] <= c1["open"]
            and b0 > _body(c1)
        ):
            return "SELL"

        # ── MORNING STAR (3-candle bullish reversal) ───────────────
        # c2=big bear, c1=small body (star), c0=big bull
        if (
            _is_bear(c2) and _body(c2) > 0.5 * _range(c2)
            and _body(c1) < 0.3 * _range(c2)
            and _is_bull(c0) and _body(c0) > 0.5 * _range(c0)
            and c0["close"] > (c2["open"] + c2["close"]) / 2
        ):
            return "BUY"

        # ── EVENING STAR (3-candle bearish reversal) ───────────────
        if (
            _is_bull(c2) and _body(c2) > 0.5 * _range(c2)
            and _body(c1) < 0.3 * _range(c2)
            and _is_bear(c0) and _body(c0) > 0.5 * _range(c0)
            and c0["close"] < (c2["open"] + c2["close"]) / 2
        ):
            return "SELL"

        return "NEUTRAL"
