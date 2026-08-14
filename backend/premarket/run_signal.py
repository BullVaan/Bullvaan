"""
backend/premarket/run_signal.py
================================
Morning terminal script — run once between 9:00 and 9:10 AM IST.

Steps it performs:
  1. Reads latest GIFT NIFTY snapshot (data/premarket_snapshots.jsonl)
  2. Computes gap + direction
  3. Connects to Kite to fetch live IEP (pre-open auction prices)
  4. Prints a clean decision report: direction, confidence, entry time, action

Usage:
    cd backend && source venv/bin/activate
    python3 -m premarket.run_signal              # today's snapshot
    python3 -m premarket.run_signal 2026-07-24   # historical date
"""

import os
import sys
import json
import threading
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()

from premarket.signal import (
    compute_gap, compute_iep_signal, get_confidence, get_entry_time,
    get_strike, INDEX_CONFIG, GAP_THRESHOLD, STRONG_THRESHOLD, CAPITAL_PER_INDEX,
)

SNAPSHOT_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "premarket_snapshots.jsonl")
SIGNAL_LOG    = os.path.join(os.path.dirname(__file__), "..", "data", "premarket_signals.jsonl")
BAR = "═" * 65


def _ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


# ─── Data loading ─────────────────────────────────────────────────────────────

def load_snapshot(target_date: str = None) -> dict:
    """Load the latest (or date-matching) entry from premarket_snapshots.jsonl."""
    with open(SNAPSHOT_FILE) as f:
        entries = [json.loads(l) for l in f if l.strip()]
    if not entries:
        raise RuntimeError("No snapshots in premarket_snapshots.jsonl — run premarket_snapshot.py first.")
    if target_date:
        entries = [e for e in entries if e["snapshot_taken_at"][:10] == target_date]
        if not entries:
            raise RuntimeError(f"No snapshot found for date {target_date}.")
    return entries[-1]


def get_kite():
    """Return authenticated KiteConnect instance, or None if credentials missing."""
    try:
        from kiteconnect import KiteConnect
        api_key = os.getenv("API_KEY")
        access_token = os.getenv("ACCESS_TOKEN")
        if not api_key or not access_token:
            return None
        k = KiteConnect(api_key=api_key)
        k.set_access_token(access_token)
        return k
    except Exception:
        return None


import time

# Indices required before main flow proceeds (SENSEX retried in background)
_IEP_REQUIRED = {"NIFTY", "BANKNIFTY"}


def fetch_live_iep(kite) -> dict:
    """
    Fetch IEP (pre-open auction price) for all 3 indices via Kite.
    Returns as soon as NIFTY+BANKNIFTY are available (or 9:12 deadline).
    SENSEX is retried separately via retry_sensex_background().
    Returns: {'NIFTY': price, 'BANKNIFTY': price}  (SENSEX added later if available)
    """
    if not kite:
        return {}
    symbols = {idx: cfg["kite_spot"] for idx, cfg in INDEX_CONFIG.items()}

    def _fetch_once():
        quotes = kite.quote(list(symbols.values()))
        result = {}
        for idx, sym in symbols.items():
            iep = quotes.get(sym, {}).get("ohlc", {}).get("open")
            if iep is not None and iep > 0:
                result[idx] = float(iep)
        return result

    while True:
        try:
            result = _fetch_once()
        except Exception as e:
            print(f"  [warn] IEP fetch error: {e}")
            result = {}

        now = _ist_now()
        deadline_passed = now.hour > 9 or (now.hour == 9 and now.minute >= 12)

        if _IEP_REQUIRED.issubset(result) or deadline_passed:
            if not result:
                print("  [warn] IEP not available — proceeding without it.")
            missing = set(symbols) - set(result)
            if missing:
                print(f"  [iep] {', '.join(missing)} not yet available — will retry in background.")
            return result

        remaining = _IEP_REQUIRED - set(result)
        print(f"  [iep] Waiting for {', '.join(remaining)} — retry in 30s...")
        time.sleep(30)


def retry_sensex_background(kite, snap: dict, iep_data: dict, trade_date: str):
    """
    Spawn a daemon thread that retries fetching SENSEX IEP every 15s until 9:15 AM.
    On success: updates iep_data in-place and patches the saved signal record.
    """
    sensex_sym = INDEX_CONFIG.get("SENSEX", {}).get("kite_spot")
    sensex_prev = float(
        snap.get("kite", {}).get("indian_indices", {}).get("SENSEX", {})
        .get("ohlc", {}).get("close") or 0
    )
    if not sensex_sym or not kite:
        return

    def _bg():
        for attempt in range(6):   # up to 6 retries × 15s = 90s window
            time.sleep(15)
            now = _ist_now()
            if now.hour > 9 or (now.hour == 9 and now.minute >= 15):
                print("  [iep-bg] Reached 9:15 — stopping SENSEX retry.")
                break
            try:
                quotes = kite.quote([sensex_sym])
                iep = quotes.get(sensex_sym, {}).get("ohlc", {}).get("open")
                if iep and float(iep) > 0:
                    price = float(iep)
                    iep_data["SENSEX"] = price
                    gap, sig = compute_iep_signal(price, sensex_prev) if sensex_prev else (None, "NEUTRAL")
                    print(f"  [iep-bg] SENSEX IEP obtained: {price}  gap={gap:+.1f}  signal={sig}")
                    _patch_sensex_in_signal_log(trade_date, price, sensex_prev, gap, sig)
                    return
            except Exception as e:
                print(f"  [iep-bg] Attempt {attempt + 1} error: {e}")
        print("  [iep-bg] SENSEX IEP not obtained before 9:15.")

    threading.Thread(target=_bg, daemon=True, name="iep-sensex-retry").start()


def _patch_sensex_in_signal_log(trade_date: str, price: float, prev_close: float, gap, sig: str):
    """Update today's saved signal record with the late-arriving SENSEX IEP."""
    try:
        with open(SIGNAL_LOG) as f:
            records = [json.loads(l) for l in f if l.strip()]
        for r in records:
            if r.get("date") == trade_date:
                r.setdefault("iep_signals", {})["SENSEX"] = sig
                r.setdefault("iep_prices", {})["SENSEX"] = {
                    "price":      price,
                    "prev_close": prev_close,
                    "gap":        round(gap, 2) if gap is not None else None,
                    "signal":     sig,
                }
        with open(SIGNAL_LOG, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        print(f"  [iep-bg] Signal record patched with SENSEX IEP.")
    except Exception as e:
        print(f"  [iep-bg] Failed to patch signal record: {e}")


# ─── Report printing ──────────────────────────────────────────────────────────

def print_report(snap: dict, iep_data: dict, nikkei_dir: str = "NEUTRAL"):
    kite_data = snap["kite"]
    gift = kite_data["gift_nifty"]
    nifty_info = kite_data["indian_indices"]["NIFTY"]

    gift_price       = float(gift["last_price"])
    nifty_prev_close = float(nifty_info["ohlc"]["close"])
    gap, direction   = compute_gap(gift_price, nifty_prev_close)
    entry_time       = get_entry_time(gap)
    snap_date        = snap["snapshot_taken_at"][:10]

    print()
    print(BAR)
    print(f"  PREMARKET SIGNAL REPORT — {snap_date}")
    print(f"  Run at  : {_ist_now().strftime('%H:%M:%S')} IST")
    print(BAR)

    # ── Gap & direction ───────────────────────────────────────────────────────
    arrow = "▲" if gap > 0 else "▼"
    strength_tag = ""
    if abs(gap) >= STRONG_THRESHOLD:
        strength_tag = "  [STRONG — enter at 09:15 AM]"
    elif abs(gap) > GAP_THRESHOLD:
        strength_tag = "  [enter at 09:20 AM]"

    print(f"\n  GIFT NIFTY  : {gift_price}")
    print(f"  NIFTY prev  : {nifty_prev_close}")
    print(f"  Gap         : {gap:+.1f} pts  {arrow}{strength_tag}")
    print(f"  Direction   : {direction}")
    print(f"  Entry time  : {entry_time} AM")

    opt_type = "CE" if direction == "BULLISH" else "PE"

    # ── IEP alignment (always run, even on FLAT days, for data collection) ────
    print(f"\n  IEP Alignment (pre-open auction, 9:00–9:15 AM):")
    print(f"  {'─'*61}")
    print(f"  {'Index':<12}  {'IEP':>8}  {'Gap':>9}  {'Signal':<10}  Aligns?")
    print(f"  {'─'*61}")

    iep_signals = {}
    iep_prices  = {}   # actual prices + gaps, not just classification strings
    for idx in ["NIFTY", "BANKNIFTY", "SENSEX"]:
        prev_close_val = kite_data["indian_indices"].get(idx, {}).get("ohlc", {}).get("close")
        iep_price = iep_data.get(idx)
        if iep_price and prev_close_val:
            iep_gap, iep_sig = compute_iep_signal(float(iep_price), float(prev_close_val))
            agrees = "✓ agrees" if iep_sig in ("NEUTRAL", direction) else "✗ CONFLICT"
            print(f"  {idx:<12}  {iep_price:>8.1f}  {iep_gap:>+9.1f}  {iep_sig:<10}  {agrees}")
            iep_prices[idx] = {"price": float(iep_price), "prev_close": float(prev_close_val), "gap": round(iep_gap, 2), "signal": iep_sig}
        else:
            iep_sig = "NEUTRAL"
            print(f"  {idx:<12}  {'N/A':>8}  {'N/A':>9}  {'N/A':<10}  (not available)")
            iep_prices[idx] = {"price": None, "prev_close": float(prev_close_val) if prev_close_val else None, "gap": None, "signal": "NEUTRAL"}
        iep_signals[idx] = iep_sig

    # Confidence uses NIFTY IEP as representative
    iep_sig_nifty = iep_signals.get("NIFTY", "NEUTRAL")

    if direction == "FLAT":
        print(f"\n  ⚠  FLAT — Gap within ±{GAP_THRESHOLD} pts. Skip today, no trade.\n")
        print(BAR)
        print()
        record = {
            "date": snap_date, "time": _ist_now().strftime("%H:%M:%S"),
            "gift_price": gift_price, "nifty_prev": nifty_prev_close,
            "gap": round(gap, 2), "direction": "FLAT",
            "entry_time": None, "opt_type": None, "confidence": "SKIP",
            "nikkei": nikkei_dir, "iep_signals": iep_signals, "iep_prices": iep_prices,
        }
        with open(SIGNAL_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")
        return direction, None, None

    confidence = get_confidence(direction, nikkei_dir, iep_sig_nifty)

    # ── Confidence ────────────────────────────────────────────────────────────
    conf_note = {
        "HIGH":   "✓ All signals agree — full lot size",
        "MEDIUM": "⚠ Conflict detected — consider reducing lots ~30%",
        "SKIP":   "✗ FLAT — no trade",
    }.get(confidence, "")
    print(f"\n  NIKKEI      : {nikkei_dir}  (enter manually — check your broker dashboard)")
    print(f"  Confidence  : {confidence}  — {conf_note}")

    # ── Lot sizing preview (strike known at 9:00 AM; price known only at entry) ──
    print(f"\n  Lot Sizing Preview (price unknown until {entry_time} — shown at entry):")
    print(f"  {'─'*61}")
    print(f"  {'Index':<12}  {'Type':>4}  {'Strike':<16}  {'Lot size':>9}  {'Capital':>10}")
    print(f"  {'─'*61}")
    for idx, cfg in INDEX_CONFIG.items():
        offset = cfg["ce_offset"] if direction == "BULLISH" else cfg["pe_offset"]
        strike_label = f"ATM {offset:+d} pts"
        print(f"  {idx:<12}  {opt_type:>4}  {strike_label:<16}  {cfg['lot_size']:>9}  {'Rs.1L':>10}")

    # ── BN conflict flip: BN IEP bearish by >50 pts on a BULLISH gap → take PE ─
    bn_iep_gap = iep_prices.get("BANKNIFTY", {}).get("gap")
    bn_conflict_flip = (
        direction == "BULLISH"
        and bn_iep_gap is not None
        and bn_iep_gap < -50
    )
    if bn_conflict_flip:
        trade_direction = "BEARISH"
        opt_type        = "PE"
        entry_mode      = "RULE_C"
        mode_note       = (f"BN IEP gap={bn_iep_gap:+.1f} — CONFLICT: flip to PE, "
                           f"wait for lower-low red candle after {entry_time}")
    elif iep_sig_nifty == direction or entry_time == "09:15":
        trade_direction = direction
        entry_mode      = "IMMEDIATE"
        mode_note       = "enter at " + entry_time
    else:
        trade_direction = direction
        entry_mode      = "RULE_C"
        mode_note       = "wait for higher-high green candle after " + entry_time

    # ── Final action ──────────────────────────────────────────────────────────
    action = f"Buy {opt_type} — entry_mode={entry_mode} ({mode_note}) — run executor.py at {entry_time}."
    print(f"\n  ENTRY MODE  : {entry_mode}  — {mode_note}")
    print(f"  ACTION: {action}")
    print()
    print(BAR)
    print()

    # ── Save signal record ────────────────────────────────────────────────────
    record = {
        "date":        snap_date,
        "time":        _ist_now().strftime("%H:%M:%S"),
        "gift_price":  gift_price,
        "nifty_prev":  nifty_prev_close,
        "gap":         round(gap, 2),
        "direction":   direction,
        "entry_time":  entry_time,
        "opt_type":       opt_type,
        "trade_direction": trade_direction,
        "entry_mode":     entry_mode,
        "confidence":     confidence,
        "nikkei":      nikkei_dir,
        "iep_signals": iep_signals,
        "iep_prices":  iep_prices,
    }
    with open(SIGNAL_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")

    return direction, entry_time, opt_type


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    target_date = sys.argv[1] if len(sys.argv) > 1 else None
    nikkei_dir  = sys.argv[2].upper() if len(sys.argv) > 2 else "NEUTRAL"  # UP / DOWN / NEUTRAL

    snap     = load_snapshot(target_date)
    kite     = get_kite()
    iep_data = fetch_live_iep(kite)

    print_report(snap, iep_data, nikkei_dir)


if __name__ == "__main__":
    main()
