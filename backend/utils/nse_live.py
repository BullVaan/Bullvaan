"""
NSE Live Index Data Fetcher
Fetches real-time index prices using yfinance (reliable, no cookie issues)
Caches results for 2 seconds to avoid hammering the API
"""

import time
import yfinance as yf

# Map symbols to display names
TICKER_SYMBOLS = {
    "^NSEI": "Nifty 50",
    "^NSEBANK": "Bank Nifty",
    "^BSESN": "Sensex",
}

# Cache
_cache: list[dict] = []
_cache_time: float = 0
CACHE_TTL = 2  # seconds


def fetch_nse_indices() -> list[dict]:
    """
    Fetch real-time index data using yfinance.
    Results are cached for 2 seconds to prevent excessive API calls.
    """
    global _cache, _cache_time

    now = time.time()
    if _cache and (now - _cache_time) < CACHE_TTL:
        return _cache

    results = []

    for symbol, name in TICKER_SYMBOLS.items():
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info

            current_price = getattr(info, "last_price", None)
            prev_close = getattr(info, "previous_close", None)

            if current_price is None:
                # Fallback: use history
                hist = ticker.history(period="2d", interval="1m")
                if hist is not None and not hist.empty:
                    current_price = float(hist["Close"].iloc[-1])

            if prev_close is None:
                hist2d = ticker.history(period="5d")
                if hist2d is not None and len(hist2d) >= 2:
                    prev_close = float(hist2d["Close"].iloc[-2])

            if current_price is not None and prev_close is not None:
                change = current_price - prev_close
                change_pct = (change / prev_close) * 100 if prev_close != 0 else 0

                results.append({
                    "symbol": symbol,
                    "name": name,
                    "price": round(current_price, 2),
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                    "prev_close": round(prev_close, 2),
                })
            else:
                results.append({
                    "symbol": symbol,
                    "name": name,
                    "price": round(current_price, 2) if current_price else None,
                    "change": None,
                    "change_pct": None,
                })

        except Exception:
            results.append({
                "symbol": symbol,
                "name": name,
                "price": None,
                "change": None,
                "change_pct": None,
            })

    _cache = results
    _cache_time = time.time()
    return results
