"""
backtest_premarket_nifty.py
===========================
Backtest the premarket directional strategy using nifty_option_history.json.

Strategy:
  - BULLISH → Buy CE ITM_100 (ATM-100)
  - BEARISH → Buy PE OTM_50  (ATM-50)
  - FLAT    → skip (gap within ±30 pts)
  - Entry   → open of 09:15 candle if |gap|>=150, else 09:20 candle
  - Target  → +60 pts from entry
  - SL      → -50 pts from entry
  - EOD     → exit at close of last candle if T/SL not hit
  - Capital → Rs 1,00,000; lots = floor(100000 / (entry_price * 65))
"""

import json
import math

# ── Config ────────────────────────────────────────────────────────────────────
OPTION_FILE      = "data/nifty_option_history.json"
SNAPSHOT_FILE    = "data/premarket_snapshots.jsonl"
GAP_THRESHOLD    = 30
STRONG_THRESHOLD = 150
TARGET_PTS       = 60
SL_PTS           = 50
LOT_SIZE         = 65
CAPITAL          = 100_000

# Gap per date from snapshots
GAPS = {
    "2026-07-22": -84.7,
    "2026-07-23": -124.8,
    "2026-07-24": -198.1,
    "2026-07-27": +158.5,
    "2026-07-28": -19.0,
    "2026-07-29": +257.2,
    "2026-07-30": +2.8,
    "2026-07-31": +91.3,
    "2026-08-03": +220.4,
}

def simulate_trade(candles, entry_price, entry_ts, target_pts, sl_pts):
    """Walk candles from entry_ts forward. Return (exit_price, exit_ts, reason)."""
    target = entry_price + target_pts
    sl     = entry_price - sl_pts

    in_trade = False
    for c in candles:
        ts = c["ts"]
        if not in_trade:
            if ts >= entry_ts:
                in_trade = True
                # entry candle: use open as entry (already set), check H/L
            else:
                continue

        h, l, close = c["h"], c["l"], c["c"]

        # Within a candle assume SL checked before Target if both hit
        if l <= sl:
            return sl, ts, "SL"
        if h >= target:
            return target, ts, "TARGET"

    # EOD — exit at close of last candle
    last = candles[-1]
    return last["c"], last["ts"], "EOD"


def run():
    with open(OPTION_FILE) as f:
        opt_data = json.load(f)

    print()
    print("=" * 78)
    print("  PREMARKET NIFTY BACKTEST — Strategy: ITM_100 CE / OTM_50 PE")
    print("=" * 78)
    print(f"  {'Date':<12} {'Dir':<8} {'Gap':>7} {'Entry':>6} {'Strike':<22} {'Lots':>4} "
          f"{'Buy':>6} {'Exit':>6} {'Pts':>6} {'P&L':>9} {'Reason'}")
    print(f"  {'-'*12} {'-'*8} {'-'*7} {'-'*6} {'-'*22} {'-'*4} "
          f"{'-'*6} {'-'*6} {'-'*6} {'-'*9} {'-'*8}")

    total_pnl  = 0
    wins = losses = flats = eods = 0
    results = []

    for date in sorted(GAPS.keys()):
        gap = GAPS[date]

        # Direction
        if abs(gap) < GAP_THRESHOLD:
            print(f"  {date:<12} {'FLAT':<8} {gap:>+7.1f}  — skipped (gap within ±{GAP_THRESHOLD})")
            flats += 1
            continue

        direction  = "BULLISH" if gap > 0 else "BEARISH"
        strike_key = "ITM_100" if direction == "BULLISH" else "OTM_50"
        entry_ts   = f"{date} 09:15:00+05:30" if abs(gap) >= STRONG_THRESHOLD else f"{date} 09:20:00+05:30"
        entry_label = "09:15" if abs(gap) >= STRONG_THRESHOLD else "09:20"

        if date not in opt_data:
            print(f"  {date:<12} {'NO DATA':<8}")
            continue

        day    = opt_data[date]
        strike = day["strikes"].get(strike_key)
        if not strike:
            print(f"  {date:<12} {direction:<8}  Strike {strike_key} not found in data")
            continue

        candles    = strike["candles"]
        # Find entry candle
        entry_candle = next((c for c in candles if c["ts"] >= entry_ts), None)
        if not entry_candle:
            print(f"  {date:<12} {direction:<8}  No candle at/after {entry_label}")
            continue

        entry_price = entry_candle["o"]
        lots        = math.floor(CAPITAL / (entry_price * LOT_SIZE))
        if lots < 1:
            lots = 1
        qty         = lots * LOT_SIZE

        exit_price, exit_ts, reason = simulate_trade(
            candles, entry_price, entry_ts, TARGET_PTS, SL_PTS
        )

        pts = exit_price - entry_price
        pnl = pts * qty

        total_pnl += pnl
        if reason == "TARGET":
            wins += 1
        elif reason == "SL":
            losses += 1
        else:
            eods += 1

        results.append({
            "date": date, "direction": direction, "gap": gap,
            "entry": entry_price, "exit": exit_price, "pts": pts,
            "lots": lots, "qty": qty, "pnl": pnl, "reason": reason,
        })

        print(f"  {date:<12} {direction:<8} {gap:>+7.1f} {entry_label:>6} "
              f"{strike['tradingsymbol']:<22} {lots:>4} "
              f"{entry_price:>6.1f} {exit_price:>6.1f} {pts:>+6.1f} "
              f"{pnl:>9,.0f} {reason}")

    # ── Summary ───────────────────────────────────────────────────────────────
    traded = len(results)
    print()
    print("=" * 78)
    print(f"  {'SUMMARY':}")
    print(f"  {'─'*76}")
    print(f"  Total days       : {traded + flats}  ({flats} FLAT skipped, {traded} traded)")
    print(f"  Wins (TARGET)    : {wins}")
    print(f"  Losses (SL)      : {losses}")
    print(f"  EOD exits        : {eods}")
    if traded:
        win_rate = wins / traded * 100
        print(f"  Win rate         : {win_rate:.0f}%  ({wins}/{traded})")
    print(f"  Total P&L        : Rs {total_pnl:,.0f}")
    print("=" * 78)
    print()

    # Per-result P&L
    cum = 0
    print(f"  {'Date':<12}  {'P&L':>10}  {'Cumulative':>12}  Reason")
    print(f"  {'-'*12}  {'-'*10}  {'-'*12}  {'-'*8}")
    for r in results:
        cum += r["pnl"]
        print(f"  {r['date']:<12}  {r['pnl']:>10,.0f}  {cum:>12,.0f}  {r['reason']}")
    print()


if __name__ == "__main__":
    run()
