"""
Pre-market global data snapshot — run ONCE each morning, manually, right after
Kite login (before or around market open). Fully DECOUPLED from auto_trader.py's
tick loop — this script does not touch trading logic, does not place orders, and
is not imported by anything else in the app.

Purpose: capture raw overnight/global market context for later analysis (per the
GIFT Nifty / pre-market cues discussion, logged as a backlog idea in
/memories/repo/regime-trading-design.md). NOT used for any trading decision yet —
capture only.

Usage (from backend/, after logging in so .env has a fresh ACCESS_TOKEN):
    source venv/bin/activate && python3 premarket_snapshot.py

Appends one JSON line per day to data/premarket_snapshots.jsonl. Safe to re-run
the same day — it will just append another snapshot (each has its own timestamp).
"""
import os
import json
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from kiteconnect import KiteConnect

OUT_FILE = os.path.join(os.path.dirname(__file__), 'data', 'premarket_snapshots.jsonl')


def _ist_now_str():
    """Current time in IST (UTC+5:30), matching the convention used everywhere else
    in this project (see engine/auto_trader.py's _ist_now())."""
    from datetime import timedelta
    ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    return ist.strftime("%Y-%m-%d %H:%M:%S")

def get_kite():
    api_key = os.getenv("API_KEY")
    access_token = os.getenv("ACCESS_TOKEN")
    if not api_key or not access_token:
        raise RuntimeError("API_KEY / ACCESS_TOKEN not set in .env — log in first.")
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    return kite


def compute_days_since_last_session():
    """Calendar days since the last day the engine actually ran (based on existing
    signal_logs/*.jsonl files) — naturally accounts for weekends AND market holidays,
    since no signal log is written on a day the engine didn't run. Returns None if no
    prior signal log exists (e.g. very first run).

    Purpose: lets the pre-market-vs-actual dataset be filtered/compared by gap size
    later (e.g. Mondays / post-holiday days have a longer overnight information
    window than a normal Tue-Fri single-night gap) without relying on a text note
    that has to be remembered and matched up manually.
    """
    signal_dir = os.path.join(os.path.dirname(__file__), 'data', 'signal_logs')
    if not os.path.isdir(signal_dir):
        return None
    today = datetime.utcnow().date()  # calendar date is the same in UTC/IST for this purpose
    dates = []
    for fname in os.listdir(signal_dir):
        if fname.endswith('.jsonl'):
            try:
                d = datetime.strptime(fname[:-6], "%Y-%m-%d").date()
                if d < today:
                    dates.append(d)
            except ValueError:
                continue
    if not dates:
        return None
    last_session = max(dates)
    return (today - last_session).days


def get_nearest_future(kite, exchange, name_filter, prefer_monthly=False):
    """Return the nearest-expiry FUT instrument dict matching name_filter, or None.

    prefer_monthly=True: NSE currency derivatives (CDS) split liquidity between
    weekly contracts (tradingsymbol like USDINR26717FUT — date-encoded suffix) and
    the standard monthly contract (tradingsymbol like USDINR26JULFUT — 3-letter
    month suffix). The weekly ones are frequently untraded (zero volume, epoch
    last_trade_time) — confirmed live on 16 Jul 2026: USDINR26717FUT had volume=0
    while USDINR26JULFUT (same window) had volume=336,274. When True, restrict to
    tradingsymbols matching the monthly pattern before picking nearest expiry.
    """
    import re
    instruments = kite.instruments(exchange)
    matches = [i for i in instruments
               if name_filter in i.get('tradingsymbol', '').upper()
               and i.get('instrument_type') == 'FUT']
    if prefer_monthly:
        monthly_pattern = re.compile(r'\d{2}[A-Z]{3}FUT$')  # e.g. "26JULFUT"
        monthly_matches = [i for i in matches if monthly_pattern.search(i.get('tradingsymbol', ''))]
        if monthly_matches:
            matches = monthly_matches
    if not matches:
        return None
    matches.sort(key=lambda i: i.get('expiry'))
    return matches[0]


def fetch_kite_data():
    """Fetch GIFT Nifty, crude oil, USD/INR, and previous-day index closes via Kite."""
    result = {}
    kite = get_kite()

    # 1. GIFT Nifty
    try:
        q = kite.quote("NSEIX:GIFT NIFTY")
        result["gift_nifty"] = q.get("NSEIX:GIFT NIFTY")
    except Exception as e:
        result["gift_nifty"] = None
        result["gift_nifty_error"] = f"{type(e).__name__}: {e}"

    # 2. Crude oil (nearest MCX future)
    try:
        crude = get_nearest_future(kite, "MCX", "CRUDEOIL")
        if crude:
            q = kite.quote(f"MCX:{crude['tradingsymbol']}")
            result["crude_oil"] = q.get(f"MCX:{crude['tradingsymbol']}")
            result["crude_oil"]["tradingsymbol"] = crude["tradingsymbol"]
        else:
            result["crude_oil"] = None
    except Exception as e:
        result["crude_oil"] = None
        result["crude_oil_error"] = f"{type(e).__name__}: {e}"

    # 3. USD/INR (nearest LIQUID CDS future — monthly contract, not the illiquid weeklies)
    try:
        usdinr = get_nearest_future(kite, "CDS", "USDINR", prefer_monthly=True)
        if usdinr:
            q = kite.quote(f"CDS:{usdinr['tradingsymbol']}")
            result["usdinr"] = q.get(f"CDS:{usdinr['tradingsymbol']}")
            result["usdinr"]["tradingsymbol"] = usdinr["tradingsymbol"]
        else:
            result["usdinr"] = None
    except Exception as e:
        result["usdinr"] = None
        result["usdinr_error"] = f"{type(e).__name__}: {e}"

    # 4. Previous day's Indian index closes (for gap calc later — raw values only)
    index_spots = {
        "NIFTY": "NSE:NIFTY 50",
        "BANKNIFTY": "NSE:NIFTY BANK",
        "SENSEX": "BSE:SENSEX",
    }
    result["indian_indices"] = {}
    for name, key in index_spots.items():
        try:
            q = kite.quote(key)
            result["indian_indices"][name] = q.get(key)
        except Exception as e:
            result["indian_indices"][name] = None
            result["indian_indices"][f"{name}_error"] = f"{type(e).__name__}: {e}"

    return result


def fetch_global_indices():
    """Fetch global index readings via yfinance. Never blocks the rest of the
    script if it fails — Yahoo Finance is a separate, unofficial data source,
    independent of the Kite session.

    IMPORTANT (per Claude UI review, 16 Jul 2026): at a ~9:05 AM IST snapshot time,
    US markets (S&P/Nasdaq/Dow) are fully closed (closed ~1:30-2:30 AM IST) so their
    daily "close" is correct and final. But Nikkei/Hang Seng/Shanghai are EITHER
    actively mid-session OR right at a session boundary at that hour — fetching
    yfinance's daily "close" for them would silently return YESTERDAY's completed
    close, understating today's actual move by a full day. So:
      - US tickers: fetch daily close via history() — correct, session is over.
      - Asian tickers: fetch fast_info's live lastPrice (current tick, reflects
        today's session-in-progress) instead, plus previousClose for reference.
    """
    close_tickers = {
        "sp500":  "^GSPC",
        "nasdaq": "^IXIC",
        "dow":    "^DJI",
    }
    live_tickers = {
        "nikkei":   "^N225",
        "hangseng": "^HSI",
        "shanghai": "000001.SS",
    }
    result = {}
    try:
        import yfinance as yf
    except ImportError:
        return {"error": "yfinance not installed — US/Asian index data unavailable today"}

    # US indices — closed session, daily close is correct and final
    for name, ticker in close_tickers.items():
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if hist.empty:
                result[name] = None
                continue
            last_row = hist.iloc[-1]
            result[name] = {
                "ticker": ticker,
                "reading_type": "completed_close",
                "close": round(float(last_row["Close"]), 2),
                "as_of": str(hist.index[-1]),
            }
        except Exception as e:
            result[name] = None
            result[f"{name}_error"] = f"{type(e).__name__}: {e}"

    # Asian indices — may be mid-session at snapshot time, use live price not daily close
    for name, ticker in live_tickers.items():
        try:
            fi = yf.Ticker(ticker).fast_info
            last_price = fi.get("lastPrice")
            if last_price is None:
                result[name] = None
                continue
            result[name] = {
                "ticker": ticker,
                "reading_type": "live_intraday",  # NOT a daily close — session may be in progress
                "last_price": round(float(last_price), 2),
                "previous_close": round(float(fi.get("previousClose")), 2) if fi.get("previousClose") else None,
                "exchange_timezone": fi.get("timezone"),
            }
        except Exception as e:
            result[name] = None
            result[f"{name}_error"] = f"{type(e).__name__}: {e}"

    return result


def main():
    snapshot = {
        "snapshot_taken_at": _ist_now_str() + " IST",
        "days_since_last_session": compute_days_since_last_session(),
        "_timezone_note": (
            "snapshot_taken_at is IST (UTC+5:30). All kite.* timestamps/last_trade_time "
            "fields below are also IST (Kite Connect always returns exchange-local time). "
            "global_indices.*.as_of timestamps are each market's OWN local time, with the "
            "UTC offset embedded in the string (e.g. -04:00 = US Eastern, +09:00 = Japan, "
            "+08:00 = Hong Kong/China) — NOT IST, do not compare them directly without "
            "converting first."
        ),
    }
    try:
        snapshot["kite"] = fetch_kite_data()
    except Exception as e:
        snapshot["kite"] = None
        snapshot["kite_error"] = f"{type(e).__name__}: {e}"
        print(f"WARNING: Kite data fetch failed entirely: {e}")

    snapshot["global_indices"] = fetch_global_indices()

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, 'a') as f:
        f.write(json.dumps(snapshot, default=str) + '\n')

    print(f"Snapshot written to {OUT_FILE}")
    print(json.dumps(snapshot, indent=2, default=str))


if __name__ == "__main__":
    main()
