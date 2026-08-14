"""
backend/premarket/main.py
==========================
Single entry point for the entire premarket approach.
Run once at 9:00 AM — it handles everything automatically.

What it does:
  1. Takes a fresh premarket snapshot (GIFT NIFTY + index data)
  2. Computes gap and direction
  3. Fetches live IEP and prints the signal report
  4. If FLAT → exits early (no trade)
  5. If directional → waits until entry time (09:15 or 09:20)
  6. Places orders for all 3 indices (paper by default)
  7. Monitors positions live — exits on Target / SL / EOD
  8. Prints final trade summary

Usage:
    cd backend && source venv/bin/activate
    python3 -m premarket.main              # paper mode
    python3 -m premarket.main --live       # live orders (will prompt confirmation)
    python3 -m premarket.main --index NIFTY BANKNIFTY   # specific indices only

Typical morning routine:
    09:00 AM → run this file
    09:15/20  → auto-enters trades (no further action needed)
    15:25      → auto-exits any remaining positions
"""

import argparse
import logging
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()

# ─── Sub-modules ──────────────────────────────────────────────────────────────
from premarket.signal import (
    compute_gap, get_entry_time, INDEX_CONFIG,
)
from premarket.run_signal import (
    load_snapshot, get_kite, fetch_live_iep, print_report, retry_sensex_background,
)
from premarket.executor import (
    get_spot_price, get_strike, find_instrument,
    get_option_ltp, compute_lots, place_buy_order,
    monitor_positions, print_summary,
    CAPITAL_PER_INDEX, SNAPSHOT_FILE,
)
import premarket.executor as _executor_mod   # for EOD_EXIT_TIME

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("premarket.main")


def _ist_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def _wait_until(target_hhmm: str):
    """
    Block until IST time reaches target_hhmm (e.g. '09:15').
    Prints a countdown every 30 seconds.
    """
    hour, minute = int(target_hhmm[:2]), int(target_hhmm[3:])
    log.info(f"Waiting until {target_hhmm} IST to enter trade...")
    while True:
        now = _ist_now()
        target_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        remaining = (target_dt - now).total_seconds()
        if remaining <= 0:
            break
        if remaining > 30:
            log.info(f"  → Entry in {int(remaining // 60)}m {int(remaining % 60)}s")
            time.sleep(30)
        else:
            time.sleep(max(0, remaining))
            break
    log.info(f"Entry time {target_hhmm} reached.")


def main():
    parser = argparse.ArgumentParser(description="Premarket directional approach — full run")
    parser.add_argument("--live",    action="store_true",
                        help="Place real orders (default: paper mode)")
    parser.add_argument("--index",   nargs="+", default=list(INDEX_CONFIG.keys()),
                        help="Indices to trade (default: NIFTY BANKNIFTY SENSEX)")
    parser.add_argument("--nikkei",  default="NEUTRAL", choices=["UP", "DOWN", "NEUTRAL"],
                        help="NIKKEI direction for confidence calc (default: NEUTRAL)")
    parser.add_argument("--no-wait", action="store_true",
                        help="Skip the wait and enter immediately (for testing)")
    args = parser.parse_args()

    live    = args.live
    indices = [i.upper() for i in args.index]

    # ── Safety prompt ─────────────────────────────────────────────────────────
    if live:
        print("\n⚠  LIVE MODE — real orders will be placed on your Zerodha account.")
        confirm = input("   Type 'YES' to confirm: ").strip()
        if confirm != "YES":
            print("   Aborted.")
            return

    mode_tag = "LIVE" if live else "PAPER"
    log.info(f"Starting premarket main — mode={mode_tag}  indices={indices}")

    # ── Step 1: Snapshot ──────────────────────────────────────────────────────
    # Import here to avoid circular issues; premarket_snapshot.py is at backend/ level
    import importlib, sys, os, json as _json
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

    # Check if today's snapshot already exists — avoid double-capture on same day
    _today = _ist_now().strftime("%Y-%m-%d")
    _has_today = False
    try:
        with open(SNAPSHOT_FILE) as _f:
            _last = [_l for _l in _f if _l.strip()]
            if _last and _json.loads(_last[-1]).get("snapshot_taken_at", "")[:10] == _today:
                _has_today = True
    except Exception:
        pass

    if _has_today:
        log.info("Today's snapshot already exists — skipping re-capture.")
    else:
        try:
            snap_mod = importlib.import_module("premarket_snapshot")
            log.info("Taking fresh premarket snapshot...")
            snap_mod.main()          # saves to data/premarket_snapshots.jsonl
        except Exception as e:
            log.warning(f"Could not take fresh snapshot ({e}). Using last saved snapshot.")

    # ── Step 2: Signal report ─────────────────────────────────────────────────
    snap = load_snapshot()   # latest entry
    kite = get_kite()

    # Wait until 9:08 IST before fetching IEP — auction price finalizes ~9:08 AM
    if not args.no_wait:
        log.info("Waiting until 09:08 IST for IEP auction price to finalize...")
        _wait_until("09:08")

    log.info("Fetching live IEP prices...")
    iep_data = fetch_live_iep(kite)

    # Retry SENSEX in background if it was missing — doesn't block main flow
    if "SENSEX" not in iep_data:
        retry_sensex_background(kite, snap, iep_data, _ist_now().strftime("%Y-%m-%d"))

    log.info("Printing signal report...")
    direction, entry_time, opt_type = print_report(snap, iep_data, args.nikkei)

    # Compute gap for trade log
    gift_price = float(snap["kite"]["gift_nifty"]["last_price"])
    prev_close = float(snap["kite"]["indian_indices"]["NIFTY"]["ohlc"]["close"])
    gap, _     = compute_gap(gift_price, prev_close)

    if direction == "FLAT" or direction is None:
        log.info("FLAT day — no trade. Done.")
        return

    # ── Step 3: Fetch spot at 9:15 open (always used for strike computation) ──
    if not args.no_wait:
        _wait_until("09:15")

    log.info("Fetching spot prices at 9:15 AM open for strike computation...")
    spot_at_open = {}
    for index in indices:
        try:
            spot_at_open[index] = get_spot_price(kite, index)
            log.info(f"  {index} spot @ 9:15: {spot_at_open[index]}")
        except Exception as e:
            log.warning(f"  {index} spot fetch failed: {e}")

    # ── Step 4: Wait until actual entry time (9:15 already passed or 9:20) ──
    if not args.no_wait and entry_time == "09:20":
        _wait_until("09:20")

    # ── Step 4: Build and place positions ────────────────────────────────────
    if kite is None:
        kite = get_kite()        # re-connect if it failed during IEP fetch

    all_trades = []
    cfg_map    = {}

    for index in indices:
        cfg = INDEX_CONFIG[index]
        try:
            # Use spot captured at 9:15 open — consistent ATM regardless of entry time
            spot               = spot_at_open.get(index) or get_spot_price(kite, index)
            strike, opt_type_i = get_strike(spot, direction, cfg)
            instrument         = find_instrument(kite, index, strike, opt_type_i)
            ltp                = get_option_ltp(kite, cfg["exchange"], instrument["tradingsymbol"])
            lots               = compute_lots(CAPITAL_PER_INDEX, ltp, cfg["lot_size"])

            log.info(
                f"{index}: {opt_type_i} {strike:.0f}  "
                f"LTP={ltp:.2f}  lots={lots}  "
                f"capital=Rs.{lots * ltp * cfg['lot_size']:,.0f}"
            )

            trade = place_buy_order(kite, instrument, index, lots, cfg["lot_size"], live)
            all_trades.append(trade)
            cfg_map[instrument["tradingsymbol"]] = cfg

        except Exception as e:
            log.error(f"{index}: failed to set up position — {e}")

    if not all_trades:
        log.error("No positions created. Exiting.")
        return

    # ── Step 5: Monitor until T / SL / EOD ───────────────────────────────────
    log.info(f"Monitoring {len(all_trades)} position(s)...")
    monitor_positions(kite, all_trades, cfg_map, live, direction, gap)

    # ── Step 6: Summary + save ────────────────────────────────────────────────
    print_summary(all_trades, direction, gap)


if __name__ == "__main__":
    main()
