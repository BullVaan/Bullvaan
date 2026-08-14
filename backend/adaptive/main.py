"""
backend/adaptive/main.py
=========================
Adaptive Approach — enters ATM NIFTY option at 10:00 AM IST.
Direction is filtered by today's GIFT NIFTY gap (from premarket snapshot).

Flow:
  1. Read today's premarket snapshot → compute gap + direction
  2. If FLAT → exit (no trade)
  3. Wait until 10:00 AM IST
  4. Fetch live NIFTY spot → compute ATM strike
  5. Find ATM CE or PE instrument on Kite
  6. Buy order (paper or live)
  7. Monitor → exit on T=20 / SL=30 / EOD 15:25
  8. Save trade record to data/adaptive_trades.jsonl

Usage:
    cd backend && source venv/bin/activate
    python3 -m adaptive.main                     # paper, Rs 20k capital
    python3 -m adaptive.main --live              # live orders
    python3 -m adaptive.main --capital 30000     # override capital
    python3 -m adaptive.main --no-wait           # skip timers (testing)
"""

import argparse
import json
import logging
import math
import os
import sys
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()

from adaptive.signal import (
    GAP_THRESHOLD, TARGET_PTS, SL_PTS, CAPITAL as DEFAULT_CAPITAL,
    LOT_SIZE, EXCHANGE, KITE_SPOT, ENTRY_TIME, EOD_EXIT,
    get_atm_strike, get_direction, get_opt_type,
)
from premarket.run_signal import load_snapshot
from premarket.executor import (
    get_kite, get_spot_price, find_instrument, get_option_ltp,
    place_buy_order, exit_position, _ist_now, _ist_time_str, read_today_signal,
)
from premarket.signal import compute_gap

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("adaptive.main")

TRADE_LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "adaptive_trades.jsonl")
POLL_INTERVAL  = 2    # seconds between LTP polls
BAR = "=" * 65


def _wait_until(hhmm: str):
    h, m = int(hhmm[:2]), int(hhmm[3:])
    log.info(f"Waiting until {hhmm} IST...")
    while True:
        now    = _ist_now()
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        secs   = (target - now).total_seconds()
        if secs <= 0:
            break
        if secs > 30:
            log.info(f"  → {int(secs//60)}m {int(secs%60)}s remaining")
            time.sleep(30)
        else:
            time.sleep(max(0, secs))
            break
    log.info(f"Reached {hhmm} IST.")


def _save_trade(trade: dict, direction: str, gap: float):
    record = {
        "date":          _ist_now().strftime("%Y-%m-%d"),
        "direction":     direction,
        "gap":           round(gap, 2),
        "tradingsymbol": trade.get("tradingsymbol"),
        "lots":          trade.get("lots"),
        "lot_size":      LOT_SIZE,
        "quantity":      trade.get("quantity"),
        "buy_price":     trade.get("buy_price"),
        "buy_time":      trade.get("buy_time"),
        "exit_price":    trade.get("exit_price"),
        "exit_time":     trade.get("exit_time"),
        "exit_reason":   trade.get("exit_reason"),
        "pnl":           trade.get("pnl"),
        "mode":          "live" if trade.get("live") else "paper",
    }
    with open(TRADE_LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")
    log.info(f"Trade saved → {TRADE_LOG_FILE}")


def monitor(kite, trade: dict, live: bool):
    """Poll LTP every POLL_INTERVAL seconds; exit on T/SL/EOD."""
    sym      = trade["tradingsymbol"]
    tick_cnt = 0

    log.info(f"Monitoring {sym} | T=+{TARGET_PTS}  SL=-{SL_PTS}  EOD={EOD_EXIT[0]}:{EOD_EXIT[1]:02d}")

    while True:
        now = _ist_now()
        eod = now.hour > EOD_EXIT[0] or (now.hour == EOD_EXIT[0] and now.minute >= EOD_EXIT[1])

        try:
            ltp = get_option_ltp(kite, EXCHANGE, sym)
        except Exception as e:
            log.warning(f"LTP fetch error: {e}")
            time.sleep(POLL_INTERVAL)
            continue

        # Set buy_price on first tick
        if trade["buy_price"] is None:
            trade["buy_price"] = ltp
            log.info(f"ENTRY confirmed — {sym} @ {ltp:.2f}  qty={trade['quantity']}")
            time.sleep(POLL_INTERVAL)
            continue

        entry      = trade["buy_price"]
        profit_pts = ltp - entry

        # Log status every 30 ticks (~60 seconds)
        if tick_cnt % 30 == 0:
            log.info(f"  {sym}  ltp={ltp:.2f}  entry={entry:.2f}  P&L={profit_pts:+.2f}pts  T={TARGET_PTS}  SL=-{SL_PTS}")

        if eod:
            exit_position(kite, trade, ltp, "EOD", live)
            break
        elif profit_pts >= TARGET_PTS:
            exit_position(kite, trade, ltp, "TARGET", live)
            break
        elif profit_pts <= -SL_PTS:
            exit_position(kite, trade, ltp, "SL", live)
            break

        tick_cnt += 1
        time.sleep(POLL_INTERVAL)


def _print_summary(trade: dict, direction: str, gap: float):
    pnl    = trade.get("pnl") or 0
    reason = trade.get("exit_reason", "?")
    print()
    print(BAR)
    print("  ADAPTIVE APPROACH — TRADE SUMMARY")
    print(BAR)
    print(f"  Direction : {direction}  (gap={gap:+.1f})")
    print(f"  Symbol    : {trade['tradingsymbol']}")
    print(f"  Entry     : Rs {trade.get('buy_price', '?')}  @ {trade.get('buy_time', '?')}")
    print(f"  Exit      : Rs {trade.get('exit_price', '?')}  @ {trade.get('exit_time', '?')}  [{reason}]")
    print(f"  Lots      : {trade.get('lots')}  qty={trade.get('quantity')}")
    print(f"  P&L       : Rs {pnl:+,.2f}")
    print(BAR)
    print()


def main():
    parser = argparse.ArgumentParser(description="Adaptive Approach — ATM entry at 10:00 AM")
    parser.add_argument("--live",     action="store_true",  help="Place real orders (default: paper)")
    parser.add_argument("--capital",  type=int, default=DEFAULT_CAPITAL, help=f"Capital in Rs (default: {DEFAULT_CAPITAL})")
    parser.add_argument("--no-wait",  action="store_true",  help="Skip timers (for testing)")
    args = parser.parse_args()

    live    = args.live
    capital = args.capital

    if live:
        print("\n⚠  LIVE MODE — real orders on your Zerodha account.")
        confirm = input("   Type 'YES' to confirm: ").strip()
        if confirm != "YES":
            print("   Aborted.")
            return

    log.info(f"Adaptive Approach starting — mode={'LIVE' if live else 'PAPER'}  capital=Rs {capital:,}")

    # ── Step 1: Read today's gap from premarket snapshot ──────────────────────
    snap       = load_snapshot()
    gift_price = float(snap["kite"]["gift_nifty"]["last_price"])
    prev_close = float(snap["kite"]["indian_indices"]["NIFTY"]["ohlc"]["close"])
    gap, _     = compute_gap(gift_price, prev_close)
    direction  = get_direction(gap)

    log.info(f"Gap={gap:+.1f}  Direction={direction}")

    if direction == "FLAT":
        log.info(f"Gap {gap:+.1f} is within ±{GAP_THRESHOLD} pts — FLAT day, no trade.")
        return


    opt_type = get_opt_type(direction)
    trade_direction = direction

    # BN conflict flip: BN IEP bearish by >50 pts on BULLISH day → take PE ATM instead
    sig_rec    = read_today_signal()
    bn_iep_gap = sig_rec.get("iep_prices", {}).get("BANKNIFTY", {}).get("gap")
    if direction == "BULLISH" and bn_iep_gap is not None and bn_iep_gap < -50:
        log.info(f"BN IEP conflict (gap={bn_iep_gap:+.1f}) — flipping from CE to PE")
        opt_type        = "PE"
        trade_direction = "BEARISH"

    log.info(f"Will enter {opt_type} option at 10:00 AM  (trade_direction={trade_direction})")

    # ── Step 2: Wait until 10:00 AM ──────────────────────────────────────────
    if not args.no_wait:
        _wait_until(ENTRY_TIME)

    # ── Step 3: Kite + spot + ATM strike ─────────────────────────────────────
    kite  = get_kite()
    spot  = get_spot_price(kite, "NIFTY")
    strike = get_atm_strike(spot)
    log.info(f"Spot={spot:.2f}  ATM strike={strike:.0f}  opt_type={opt_type}")

    # ── Step 4: Find instrument ───────────────────────────────────────────────
    instrument = find_instrument(kite, "NIFTY", strike, opt_type)
    ltp        = get_option_ltp(kite, EXCHANGE, instrument["tradingsymbol"])
    lots       = max(1, math.floor(capital / (ltp * LOT_SIZE)))
    log.info(f"Symbol={instrument['tradingsymbol']}  LTP={ltp:.2f}  lots={lots}  qty={lots*LOT_SIZE}")

    # ── Step 5: Place order ───────────────────────────────────────────────────
    trade = place_buy_order(kite, instrument, "NIFTY", lots, LOT_SIZE, live)

    # ── Step 6: Monitor ───────────────────────────────────────────────────────
    monitor(kite, trade, live)

    # ── Step 7: Summary + save ────────────────────────────────────────────────
    _print_summary(trade, trade_direction, gap)
    _save_trade(trade, trade_direction, gap)


if __name__ == "__main__":
    main()
