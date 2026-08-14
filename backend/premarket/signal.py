"""
backend/premarket/signal.py
============================
Pure calculation module — no Kite dependency, no I/O, no side effects.
All thresholds, per-index config, and signal logic live here.

Used by:
    run_signal.py   morning decision report
    executor.py     trade placement
    capital_sim.py  backtest (gap/direction logic)
"""

# ─── Thresholds (Chapter 2, PREMARKET_README.md) ─────────────────────────────
GAP_THRESHOLD    = 30    # |gap| must exceed this for a directional signal (pts)
STRONG_THRESHOLD = 150   # |gap| above this → enter at 9:15, else 9:20
IEP_NOISE_FLOOR  = 20    # |IEP gap| below this → treat as neutral noise (pts)

CAPITAL_PER_INDEX = 100_000  # Rs 1 lakh per index for lot sizing

# ─── Per-index config ─────────────────────────────────────────────────────────
# ce_offset: pts to subtract from ATM for the CE strike (ITM_100 = ATM - 100)
# pe_offset: pts to subtract from ATM for the PE strike (OTM_50 style)
#   NIFTY    interval=50  → OTM_50 PE = ATM - 50  (1 strike below)
#   BN/SENSEX interval=100 → nearest OTM PE = ATM - 100 (1 strike below)
INDEX_CONFIG = {
    "NIFTY": {
        "lot_size":   65,
        "sl_pts":     45,
        "target_pts": 55,
        "interval":   50,
        "ce_offset":  -100,   # CE strike = ATM - 100  (ITM_100)
        "pe_offset":  +100,    # PE strike = ATM + 100  (ITM_100 for puts)
        "exchange":   "NFO",
        "kite_spot":  "NSE:NIFTY 50",
    },
    "BANKNIFTY": {
        "lot_size":   30,
        "sl_pts":     75,
        "target_pts": 60,
        "interval":   100,
        "ce_offset":  -100,   # CE strike = ATM - 100  (ITM_100)
        "pe_offset":  +100,   # PE strike = ATM + 100  (ITM_100 for puts)
        "exchange":   "NFO",
        "kite_spot":  "NSE:NIFTY BANK",
    },
    "SENSEX": {
        "lot_size":   20,
        "sl_pts":     75,
        "target_pts": 60,
        "interval":   100,
        "ce_offset":  -100,
        "pe_offset":  +100,
        "exchange":   "BFO",
        "kite_spot":  "BSE:SENSEX",
    },
}


# ─── Core calculations ────────────────────────────────────────────────────────

def compute_gap(gift_price: float, nifty_prev_close: float):
    """
    Compute GIFT NIFTY gap and determine directional signal.

    Args:
        gift_price:       GIFT NIFTY last_price at 9:00 AM IST
        nifty_prev_close: NIFTY ohlc.close from previous session

    Returns:
        (gap: float, direction: str)
        direction ∈ {'BULLISH', 'BEARISH', 'FLAT'}
    """
    gap = round(gift_price - nifty_prev_close, 2)
    if gap > GAP_THRESHOLD:
        direction = "BULLISH"
    elif gap < -GAP_THRESHOLD:
        direction = "BEARISH"
    else:
        direction = "FLAT"
    return gap, direction


def get_entry_time(gap: float) -> str:
    """Strong gap (|gap| >= 150) → 9:15; moderate gap → 9:20 to avoid first-candle whipsaw."""
    return "09:15" if abs(gap) >= STRONG_THRESHOLD else "09:20"


def compute_iep_signal(iep_price: float, prev_close: float):
    """
    Compute IEP (Indicative Equilibrium Price) gap and classify it.
    IEP is the pre-open auction price visible in Kite as ohlc.open (9:00–9:15 AM).

    Rule: if |IEP gap| < IEP_NOISE_FLOOR (20 pts) → NEUTRAL (noise, ignore).

    Returns:
        (iep_gap: float, signal: str)
        signal ∈ {'BULLISH', 'BEARISH', 'NEUTRAL'}
    """
    iep_gap = round(iep_price - prev_close, 2)
    if abs(iep_gap) < IEP_NOISE_FLOOR:
        signal = "NEUTRAL"
    elif iep_gap > 0:
        signal = "BULLISH"
    else:
        signal = "BEARISH"
    return iep_gap, signal


def get_confidence(gift_direction: str, nikkei_direction: str, iep_signal: str) -> str:
    """
    Assess signal confidence from 3-signal alignment.

    Args:
        gift_direction:   'BULLISH' / 'BEARISH' / 'FLAT'
        nikkei_direction: 'UP' / 'DOWN' / 'NEUTRAL'  (enter manually each morning)
        iep_signal:       'BULLISH' / 'BEARISH' / 'NEUTRAL'

    Returns:
        'HIGH'   — 0 conflicts
        'MEDIUM' — 1+ conflicts (reduce lots or skip borderline gaps)
        'SKIP'   — gift_direction is FLAT
    """
    if gift_direction == "FLAT":
        return "SKIP"

    expected_nikkei = "UP" if gift_direction == "BULLISH" else "DOWN"
    expected_iep    = gift_direction

    conflicts = 0
    if nikkei_direction not in ("NEUTRAL", expected_nikkei):
        conflicts += 1
    if iep_signal not in ("NEUTRAL", expected_iep):
        conflicts += 1

    return "MEDIUM" if conflicts >= 1 else "HIGH"


def compute_lots(capital: float, entry_price: float, lot_size: int) -> int:
    """
    Capital-based lot sizing.

    Lots = floor(capital / (entry_price × lot_size)), minimum 1.

    Example: capital=100000, entry=85, lot_size=65
        → floor(100000 / 5525) = 18 lots
    """
    if entry_price <= 0 or lot_size <= 0:
        return 1
    return max(1, int(capital // (entry_price * lot_size)))


def get_strike(spot: float, direction: str, cfg: dict):
    """
    Compute the option strike and type for a given direction and index config.

    BULLISH → CE  ITM_100:  strike = ATM - 100  (high delta, moves with spot)
    BEARISH → PE  OTM_50:   strike = ATM + pe_offset  (cheaper, more lots)

    Args:
        spot:      current index spot price (from kite.ltp)
        direction: 'BULLISH' or 'BEARISH'
        cfg:       entry from INDEX_CONFIG

    Returns:
        (strike: float, opt_type: str)
    """
    interval = cfg["interval"]
    atm = round(spot / interval) * interval  # round to nearest valid strike

    if direction == "BULLISH":
        return float(atm + cfg["ce_offset"]), "CE"
    else:
        return float(atm + cfg["pe_offset"]), "PE"
