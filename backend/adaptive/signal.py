"""
Adaptive Approach — pure config, no I/O.

Strategy:
  - Direction filter : GIFT NIFTY gap (same as Bulls Approach)
  - Strike          : ATM  (nearest 50-pt multiple to spot)
  - Entry time      : 10:00 AM IST (fixed, market settled after 45-min)
  - Option type     : CE for BULLISH gap, PE for BEARISH gap
  - Target          : +20 pts on option price
  - Stop Loss       : -30 pts on option price
  - EOD exit        : 15:25 IST
"""

GAP_THRESHOLD = 30       # |gap| must exceed this to trade (same as Bulls Approach)

TARGET_PTS  = 20
SL_PTS      = 30
CAPITAL     = 20_000     # Rs per trade (configurable via --capital flag)
LOT_SIZE    = 65
INTERVAL    = 50         # NIFTY strike rounding interval
EXCHANGE    = "NFO"
KITE_SPOT   = "NSE:NIFTY 50"
ENTRY_TIME  = "10:00"    # IST HH:MM
EOD_EXIT    = (15, 25)   # (hour, minute) IST


def get_atm_strike(spot: float) -> float:
    """Round spot to nearest NIFTY strike interval."""
    return round(spot / INTERVAL) * INTERVAL


def get_direction(gap: float) -> str:
    if gap > GAP_THRESHOLD:
        return "BULLISH"
    elif gap < -GAP_THRESHOLD:
        return "BEARISH"
    return "FLAT"


def get_opt_type(direction: str) -> str:
    return "CE" if direction == "BULLISH" else "PE"
