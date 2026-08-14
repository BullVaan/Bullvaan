"""
backend/premarket/executor.py
==============================
Trade execution engine for the premarket directional approach.
Run at 9:15 AM (strong gap) or 9:20 AM (moderate gap) — after run_signal.py confirms direction.

What it does:
  1. Reads today's direction from the latest premarket snapshot
  2. For each index (NIFTY, BANKNIFTY, SENSEX):
       - Resolves the correct option strike and instrument token via Kite
       - Gets live option LTP
       - Sizes lots based on capital
       - Places a PAPER or LIVE buy order
  3. Monitors all positions via live LTP polling (every 2 seconds)
  4. Exits each position when Target or SL is hit
  5. Force-exits all remaining positions at 15:25 (EOD)
  6. Logs final trade results

Usage:
    cd backend && source venv/bin/activate
    python3 -m premarket.executor              # paper mode (default)
    python3 -m premarket.executor --live       # live order placement
    python3 -m premarket.executor --index NIFTY   # single index only

Safety:
    Paper mode is the default. Pass --live explicitly to place real orders.
    The script will print a confirmation prompt before placing live orders.
"""

import os
import sys
import time
import json
import argparse
import logging
from datetime import datetime, timedelta, date

from dotenv import load_dotenv
load_dotenv()

from premarket.signal import (
    compute_gap, get_entry_time, get_strike, compute_lots,
    INDEX_CONFIG, CAPITAL_PER_INDEX,
)

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("premarket.executor")

# ─── Constants ────────────────────────────────────────────────────────────────
SNAPSHOT_FILE   = os.path.join(os.path.dirname(__file__), "..", "data", "premarket_snapshots.jsonl")
SIGNAL_LOG_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "premarket_signals.jsonl")
TRADE_LOG_FILE  = os.path.join(os.path.dirname(__file__), "..", "data", "premarket_trades.jsonl")
POLL_INTERVAL   = 2          # seconds between LTP checks
EOD_EXIT_TIME   = (15, 25)   # (hour, minute) IST — force-exit all positions
RULE_C_MAX_TIME = (11, 30)   # stop waiting for Rule C after 11:30 AM


def _load_pm_trades() -> list:
    if not os.path.exists(TRADE_LOG_FILE):
        return []
    with open(TRADE_LOG_FILE) as f:
        return [json.loads(l) for l in f if l.strip()]


def _save_pm_trades(trades: list):
    with open(TRADE_LOG_FILE, "w") as f:
        for t in trades:
            f.write(json.dumps(t) + "\n")


def write_open_record(trade: dict, direction: str, gap: float):
    date_str = _ist_now().strftime("%Y-%m-%d")
    record = {
        "date":          date_str,
        "direction":     direction,
        "gap":           gap,
        "tradingsymbol": trade.get("tradingsymbol"),
        "index":         trade.get("index"),
        "exchange":      trade.get("exchange"),
        "lots":          trade.get("lots"),
        "lot_size":      trade.get("lot_size"),
        "quantity":      trade.get("quantity"),
        "buy_price":     trade.get("buy_price"),
        "buy_time":      trade.get("buy_time"),
        "exit_price":    None,
        "exit_time":     None,
        "exit_reason":   None,
        "pnl":           None,
        "mode":          "live" if trade.get("live") else "paper",
        "status":        "open",
    }
    all_trades = _load_pm_trades()
    # Replace any existing record for this symbol today
    all_trades = [t for t in all_trades
                  if not (t.get("date") == date_str and t.get("tradingsymbol") == record["tradingsymbol"])]
    all_trades.append(record)
    _save_pm_trades(all_trades)
    log.info(f"Open record written → {record['tradingsymbol']}")


def update_closed_record(trade: dict):
    date_str = _ist_now().strftime("%Y-%m-%d")
    all_trades = _load_pm_trades()
    for i, t in enumerate(all_trades):
        if t.get("date") == date_str and t.get("tradingsymbol") == trade.get("tradingsymbol"):
            all_trades[i].update({
                "buy_price":   trade.get("buy_price"),
                "exit_price":  trade.get("exit_price"),
                "exit_time":   trade.get("exit_time"),
                "exit_reason": trade.get("exit_reason"),
                "pnl":         trade.get("pnl"),
                "status":      "closed",
            })
            break
    _save_pm_trades(all_trades)
    log.info(f"Closed record updated → {trade.get('tradingsymbol')}  reason={trade.get('exit_reason')}  pnl={trade.get('pnl')}")


def _ist_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def _ist_time_str() -> str:
    return _ist_now().strftime("%H:%M:%S")


# ─── Kite connection ──────────────────────────────────────────────────────────

def get_kite():
    from kiteconnect import KiteConnect
    api_key      = os.getenv("API_KEY")
    access_token = os.getenv("ACCESS_TOKEN")
    if not api_key or not access_token:
        raise RuntimeError("API_KEY / ACCESS_TOKEN not set in .env — run generate_access_token.py first.")
    k = KiteConnect(api_key=api_key)
    k.set_access_token(access_token)
    return k


# ─── Instrument lookup ────────────────────────────────────────────────────────

def find_instrument(kite, index: str, strike: float, opt_type: str) -> dict:
    """
    Find the nearest-expiry Kite instrument dict for a given index, strike, and option type.

    Uses kite.instruments(exchange) — cached within the process.
    Returns the instrument dict with keys: instrument_token, tradingsymbol, expiry, strike, etc.
    Raises RuntimeError if no matching instrument is found.
    """
    cfg = INDEX_CONFIG[index]
    exchange = cfg["exchange"]

    # Fetch instruments for this exchange (one network call, result is large — cache it)
    if not hasattr(find_instrument, "_cache"):
        find_instrument._cache = {}
    if exchange not in find_instrument._cache:
        log.info(f"Fetching instruments list for {exchange}...")
        find_instrument._cache[exchange] = kite.instruments(exchange)

    instruments = find_instrument._cache[exchange]
    today = date.today()

    # Filter: correct index name, option type, strike, future expiry
    candidates = [
        i for i in instruments
        if i["name"] == index
        and i["instrument_type"] == opt_type
        and float(i["strike"]) == float(strike)
        and i["expiry"] >= today
    ]

    if not candidates:
        raise RuntimeError(
            f"No {index} {opt_type} {strike:.0f} instrument found "
            f"on {exchange} with expiry >= {today}. "
            f"Check if the strike exists or if expiry has passed."
        )

    # Pick the nearest expiry (first in sorted order)
    candidates.sort(key=lambda i: i["expiry"])
    chosen = candidates[0]
    log.info(
        f"Resolved: {index} {opt_type} {strike:.0f}  "
        f"→ {chosen['tradingsymbol']}  expiry={chosen['expiry']}  "
        f"token={chosen['instrument_token']}"
    )
    return chosen


def get_spot_price(kite, index: str) -> float:
    """Get current spot price for an index via kite.ltp()."""
    cfg = INDEX_CONFIG[index]
    sym = cfg["kite_spot"]
    ltp_data = kite.ltp([sym])
    return float(ltp_data[sym]["last_price"])


def get_option_ltp(kite, exchange: str, tradingsymbol: str) -> float:
    """Get live LTP for an option instrument via kite.ltp()."""
    key = f"{exchange}:{tradingsymbol}"
    ltp_data = kite.ltp([key])
    return float(ltp_data[key]["last_price"])


# ─── Order placement ──────────────────────────────────────────────────────────

def place_buy_order(kite, instrument: dict, index: str, lots: int, lot_size: int, live: bool) -> dict:
    """
    Place a buy order. In paper mode, logs only. In live mode, calls kite.place_order().

    Returns a trade record dict.
    """
    tradingsymbol = instrument["tradingsymbol"]
    exchange      = instrument["exchange"] if "exchange" in instrument else \
                    ("BFO" if "SENSEX" in tradingsymbol else "NFO")
    quantity      = lots * lot_size

    if live:
        from kiteconnect import KiteConnect
        order_id = kite.place_order(
            variety=KiteConnect.VARIETY_REGULAR,
            exchange=exchange,
            tradingsymbol=tradingsymbol,
            transaction_type=KiteConnect.TRANSACTION_TYPE_BUY,
            quantity=quantity,
            order_type=KiteConnect.ORDER_TYPE_MARKET,
            product=KiteConnect.PRODUCT_MIS,
        )
        log.info(f"LIVE ORDER placed — {tradingsymbol} qty={quantity}  order_id={order_id}")
    else:
        log.info(f"PAPER ORDER — {tradingsymbol}  qty={quantity}  (no real order sent)")

    return {
        "tradingsymbol":    tradingsymbol,
        "exchange":         exchange,
        "index":            index,
        "instrument_token": instrument["instrument_token"],
        "lots":             lots,
        "lot_size":         lot_size,
        "quantity":         quantity,
        "buy_price":        None,   # filled after first LTP read
        "buy_time":         _ist_time_str(),
        "exit_price":       None,
        "exit_time":        None,
        "exit_reason":      None,
        "pnl":              None,
        "live":             live,
    }


def exit_position(kite, trade: dict, ltp: float, reason: str, live: bool):
    """
    Exit an open position. In paper mode, logs the exit price. In live mode, places sell order.
    Mutates `trade` in-place with exit details.
    """
    tradingsymbol = trade["tradingsymbol"]
    quantity      = trade["quantity"]

    if live:
        from kiteconnect import KiteConnect
        order_id = kite.place_order(
            variety=KiteConnect.VARIETY_REGULAR,
            exchange=trade["exchange"],
            tradingsymbol=tradingsymbol,
            transaction_type=KiteConnect.TRANSACTION_TYPE_SELL,
            quantity=quantity,
            order_type=KiteConnect.ORDER_TYPE_MARKET,
            product=KiteConnect.PRODUCT_MIS,
        )
        log.info(f"LIVE EXIT — {tradingsymbol}  qty={quantity}  order_id={order_id}  reason={reason}")
    else:
        log.info(f"PAPER EXIT — {tradingsymbol}  ltp={ltp:.2f}  reason={reason}")

    entry = trade["buy_price"] or ltp
    pnl   = (ltp - entry) * trade["quantity"]

    trade["exit_price"]  = ltp
    trade["exit_time"]   = _ist_time_str()
    trade["exit_reason"] = reason
    trade["pnl"]         = round(pnl, 2)
    update_closed_record(trade)


# ─── Signal log ───────────────────────────────────────────────────────────────

def read_today_signal() -> dict:
    """Return today's signal record from premarket_signals.jsonl, or {}."""
    if not os.path.exists(SIGNAL_LOG_FILE):
        return {}
    with open(SIGNAL_LOG_FILE) as f:
        lines = [l for l in f if l.strip()]
    if not lines:
        return {}
    rec = json.loads(lines[-1])
    return rec if rec.get("date") == _ist_now().strftime("%Y-%m-%d") else {}


# ─── Rule C: wait for higher-high green candle ────────────────────────────────

def _fetch_5min_candles(kite, instrument_token: int) -> list:
    """Fetch completed 5-min candles from 9:15 AM today up to now."""
    now     = _ist_now()
    from_dt = now.replace(hour=9, minute=15, second=0, microsecond=0)
    candles = kite.historical_data(instrument_token, from_dt, now, "5minute")
    # Drop the last candle if it's still forming (timestamp < now - 5 min)
    if candles:
        last_ts = candles[-1]["date"]
        if hasattr(last_ts, "timestamp"):
            if (now - last_ts).total_seconds() < 300:
                candles = candles[:-1]
    return candles


def wait_for_rule_c(kite, instrument_token: int, direction: str) -> bool:
    """
    Poll 5-min candles every 30s from 9:20 onward.
    Enter when: candle is confirming colour AND makes a higher high (BULLISH)
                or lower low (BEARISH) vs the previous candle.
    Returns True on trigger, False if 11:30 is reached without trigger.
    """
    is_bull  = direction == "BULLISH"
    seen_bar = set()   # track candle timestamps already evaluated
    log.info(f"[RULE_C] Watching for {'higher-high green' if is_bull else 'lower-low red'} candle...")

    while True:
        now = _ist_now()
        if now.hour > RULE_C_MAX_TIME[0] or (
                now.hour == RULE_C_MAX_TIME[0] and now.minute >= RULE_C_MAX_TIME[1]):
            log.warning("[RULE_C] 11:30 reached — no trigger. Skipping trade today.")
            return False

        try:
            candles = _fetch_5min_candles(kite, instrument_token)
        except Exception as e:
            log.warning(f"[RULE_C] Candle fetch error: {e} — retrying in 30s")
            time.sleep(30)
            continue

        for i in range(1, len(candles)):
            c, pc = candles[i], candles[i - 1]
            ts = str(c["date"])
            if ts in seen_bar:
                continue
            seen_bar.add(ts)

            confirming = (c["close"] > c["open"]) if is_bull else (c["close"] < c["open"])
            breakout   = (c["high"]  > pc["high"]) if is_bull else (c["low"] < pc["low"])

            tag = f"o={c['open']:.1f} h={c['high']:.1f} l={c['low']:.1f} c={c['close']:.1f}"
            if confirming and breakout:
                log.info(f"[RULE_C] ✓ TRIGGERED at {ts[11:16]}  {tag}")
                return True
            else:
                why = ("not green" if not confirming else
                       f"h={c['high']:.1f} not > prev h={pc['high']:.1f}")
                log.info(f"[RULE_C] {ts[11:16]} — not yet ({why})  {tag}")

        time.sleep(30)


# ─── Monitoring loop ──────────────────────────────────────────────────────────

def monitor_positions(kite, positions: list, cfg_map: dict, live: bool, direction: str = "", gap: float = 0.0):
    """
    Poll all open positions every POLL_INTERVAL seconds.
    Exit each when:
      - option LTP >= entry_price + target_pts  (TARGET)
      - option LTP <= entry_price - sl_pts      (SL)
      - IST time  >= EOD_EXIT_TIME              (EOD)

    Args:
        kite:       authenticated KiteConnect
        positions:  list of trade dicts (from place_buy_order)
        cfg_map:    {index: INDEX_CONFIG entry} for each position
        live:       whether to place real exit orders
    """
    open_pos = list(positions)  # copy so we can remove closed ones
    tick_count = 0

    log.info(f"Monitoring {len(open_pos)} position(s). Poll every {POLL_INTERVAL}s.")

    while open_pos:
        now = _ist_now()
        eod = now.hour > EOD_EXIT_TIME[0] or (
            now.hour == EOD_EXIT_TIME[0] and now.minute >= EOD_EXIT_TIME[1]
        )

        closed_this_tick = []

        for trade in open_pos:
            try:
                ltp = get_option_ltp(kite, trade["exchange"], trade["tradingsymbol"])
            except Exception as e:
                log.warning(f"LTP fetch error for {trade['tradingsymbol']}: {e}")
                continue

            # Set entry price on first successful LTP after order (approximation for paper)
            if trade["buy_price"] is None:
                trade["buy_price"] = ltp
                log.info(
                    f"ENTRY confirmed — {trade['tradingsymbol']} @ {ltp:.2f}  "
                    f"qty={trade['quantity']}"
                )
                write_open_record(trade, direction, gap)
                continue  # skip T/SL check on the very first tick

            entry  = trade["buy_price"]
            cfg    = cfg_map[trade["tradingsymbol"]]
            target = cfg["target_pts"]
            sl     = cfg["sl_pts"]

            profit_pts = ltp - entry

            # Log current status every 30 ticks (~60 seconds)
            if tick_count % 30 == 0:
                log.info(
                    f"  {trade['tradingsymbol']}  ltp={ltp:.2f}  "
                    f"entry={entry:.2f}  P&L={profit_pts:+.2f}pts  "
                    f"T={cfg['target_pts']}  SL=-{cfg['sl_pts']}"
                )

            if eod:
                exit_position(kite, trade, ltp, "EOD", live)
                closed_this_tick.append(trade)
            elif profit_pts >= target:
                exit_position(kite, trade, ltp, "TARGET", live)
                closed_this_tick.append(trade)
            elif profit_pts <= -sl:
                exit_position(kite, trade, ltp, "SL", live)
                closed_this_tick.append(trade)

        for t in closed_this_tick:
            open_pos.remove(t)

        tick_count += 1
        if open_pos and not eod:
            time.sleep(POLL_INTERVAL)

    return positions   # all trades now have exit details filled in


# ─── Results summary ──────────────────────────────────────────────────────────

def save_trades(trades: list, direction: str, gap: float):
    """Ensure all today's trades are persisted. Skips symbols already written by update_closed_record."""
    date_str    = _ist_now().strftime("%Y-%m-%d")
    all_records = _load_pm_trades()
    written_syms = {t.get("tradingsymbol") for t in all_records if t.get("date") == date_str}
    new_count = 0
    for t in trades:
        sym = t.get("tradingsymbol")
        if sym in written_syms:
            continue  # already written by write_open_record / update_closed_record
        record = {
            "date":          date_str,
            "direction":     direction,
            "gap":           gap,
            "tradingsymbol": sym,
            "index":         t.get("index"),
            "exchange":      t.get("exchange"),
            "lots":          t.get("lots"),
            "lot_size":      t.get("lot_size"),
            "quantity":      t.get("quantity"),
            "buy_price":     t.get("buy_price"),
            "buy_time":      t.get("buy_time"),
            "exit_price":    t.get("exit_price"),
            "exit_time":     t.get("exit_time"),
            "exit_reason":   t.get("exit_reason"),
            "pnl":           t.get("pnl"),
            "mode":          "live" if t.get("live") else "paper",
            "status":        "closed",
        }
        all_records.append(record)
        new_count += 1
    if new_count:
        _save_pm_trades(all_records)
        log.info(f"save_trades: {new_count} new record(s) written to {TRADE_LOG_FILE}")
    else:
        log.info("save_trades: all records already written — nothing to add")


def print_summary(trades: list, direction: str = "", gap: float = 0.0):
    BAR = "═" * 65
    print()
    print(BAR)
    print("  PREMARKET TRADE SUMMARY")
    print(BAR)
    total_pnl = 0
    for t in trades:
        pnl = t.get("pnl") or 0
        total_pnl += pnl
        reason = t.get("exit_reason", "?")
        print(
            f"  {t['tradingsymbol']:<28}  "
            f"entry={t.get('buy_price', '?'):<8}  "
            f"exit={t.get('exit_price', '?'):<8}  "
            f"P&L={pnl:>+10,.2f}  [{reason}]"
        )
    print(f"  {'─'*61}")
    print(f"  {'TOTAL':>40}  {'Rs.' + f'{total_pnl:+,.2f}':>15}")
    print(BAR)
    print()
    # Always persist to disk
    save_trades(trades, direction, gap)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Premarket directional trade executor")
    parser.add_argument("--live",  action="store_true", help="Place real orders (default: paper)")
    parser.add_argument("--index", nargs="+", default=list(INDEX_CONFIG.keys()),
                        help="Indices to trade (default: all 3)")
    args = parser.parse_args()

    live    = args.live
    indices = [i.upper() for i in args.index]

    # ── Safety prompt for live mode ───────────────────────────────────────────
    if live:
        print("\n⚠  LIVE MODE — real orders will be placed on your Zerodha account.")
        confirm = input("   Type 'YES' to confirm: ").strip()
        if confirm != "YES":
            print("   Aborted.")
            sys.exit(0)

    mode_tag = "LIVE" if live else "PAPER"
    log.info(f"Executor starting — mode={mode_tag}  indices={indices}")

    # ── Load today's signal ───────────────────────────────────────────────────
    with open(SNAPSHOT_FILE) as f:
        entries = [json.loads(l) for l in f if l.strip()]
    if not entries:
        raise RuntimeError("No snapshot found. Run premarket_snapshot.py first.")

    snap         = entries[-1]
    snap_date    = snap["snapshot_taken_at"][:10]
    gift_price   = float(snap["kite"]["gift_nifty"]["last_price"])
    prev_close   = float(snap["kite"]["indian_indices"]["NIFTY"]["ohlc"]["close"])
    gap, direction = compute_gap(gift_price, prev_close)
    entry_time   = get_entry_time(gap)

    log.info(f"Snapshot date={snap_date}  gap={gap:+.1f}  direction={direction}  entry={entry_time}")

    if direction == "FLAT":
        log.info("FLAT day — no trade. Exiting.")
        return

    # ── Entry mode from signal log (IMMEDIATE vs RULE_C) ─────────────────────
    sig_rec         = read_today_signal()
    entry_mode      = sig_rec.get("entry_mode", "IMMEDIATE")
    # trade_direction may differ from gap direction on BN-conflict flip days
    trade_direction = sig_rec.get("trade_direction", direction)
    iep_nifty       = sig_rec.get("iep_signals", {}).get("NIFTY", "N/A")
    log.info(f"IEP NIFTY={iep_nifty}  entry_mode={entry_mode}  trade_direction={trade_direction}")

    # ── Connect Kite ──────────────────────────────────────────────────────────
    kite = get_kite()

    # ── Build positions ───────────────────────────────────────────────────────
    all_trades = []
    cfg_map    = {}

    if entry_mode == "RULE_C":
        # Resolve NIFTY instrument first to get the token for candle polling
        log.info("[RULE_C] Resolving NIFTY instrument for candle monitoring...")
        nifty_cfg    = INDEX_CONFIG["NIFTY"]
        nifty_spot   = get_spot_price(kite, "NIFTY")
        nifty_strike, nifty_opt = get_strike(nifty_spot, trade_direction, nifty_cfg)
        nifty_inst   = find_instrument(kite, "NIFTY", nifty_strike, nifty_opt)
        # Always look for the option going UP (CE up = spot up; PE up = spot down)
        triggered    = wait_for_rule_c(kite, nifty_inst["instrument_token"], "BULLISH")
        if not triggered:
            log.info("Rule C never triggered — no trade today.")
            return

    for index in indices:
        cfg = INDEX_CONFIG[index]
        try:
            # Get spot price to determine strike
            spot = get_spot_price(kite, index)
            strike, opt_type = get_strike(spot, trade_direction, cfg)

            # Resolve the Kite instrument
            instrument = find_instrument(kite, index, strike, opt_type)

            # Get current option LTP for lot sizing
            exchange = cfg["exchange"]
            ltp = get_option_ltp(kite, exchange, instrument["tradingsymbol"])

            # Size lots
            lots = compute_lots(CAPITAL_PER_INDEX, ltp, cfg["lot_size"])
            log.info(
                f"{index}: {opt_type} {strike:.0f}  "
                f"LTP={ltp:.2f}  lots={lots}  "
                f"capital=Rs.{lots * ltp * cfg['lot_size']:,.0f}"
            )

            # Place order
            trade = place_buy_order(kite, instrument, index, lots, cfg["lot_size"], live)
            all_trades.append(trade)
            cfg_map[instrument["tradingsymbol"]] = cfg

        except Exception as e:
            log.error(f"{index}: failed to set up position — {e}")

    if not all_trades:
        log.error("No positions created. Exiting.")
        return

    # ── Monitor until exit ────────────────────────────────────────────────────
    log.info(f"Monitoring {len(all_trades)} position(s) until T/SL/EOD...")
    monitor_positions(kite, all_trades, cfg_map, live, direction, gap)

    # ── Print summary + save ──────────────────────────────────────────────────
    print_summary(all_trades, direction, gap)


if __name__ == "__main__":
    main()
