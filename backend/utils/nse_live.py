"""
NSE Live Index Data Fetcher
Fetches near real-time index prices via yfinance fast_info
Uses parallel fetching for lower latency (~0.5-1s total instead of 3-4s sequential)
Cached for 1 second to balance freshness vs API load
"""

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf

logger = logging.getLogger(__name__)

# Symbols to track
TICKER_SYMBOLS = {
    "^NSEI": "Nifty 50",
    "^NSEBANK": "Bank Nifty",
    "^BSESN": "Sensex",
}

# Cache
_cache: list[dict] = []
_cache_time: float = 0
CACHE_TTL = 1  # seconds (reduced from 2)


def _fetch_single_ticker(symbol: str, name: str) -> dict:
    """Fetch a single ticker's data (runs in thread)."""
    try:
        ticker = yf.Ticker(symbol)
        
        # Try fast_info first
        try:
            info = ticker.fast_info
            
            # fast_info returns a dict-like object, handle both dict and object access
            if info and isinstance(info, dict):
                price = info.get("last_price")
                prev = info.get("previous_close")
            elif info:
                # Try object attribute access
                price = getattr(info, "last_price", None)
                prev = getattr(info, "previous_close", None)
            else:
                price = None
                prev = None
                
            if price and prev:
                change = price - prev
                change_pct = (change / prev) * 100
                return {
                    "symbol": symbol,
                    "name": name,
                    "price": round(price, 2),
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                    "prev_close": round(prev, 2),
                }
            else:
                return {
                    "symbol": symbol,
                    "name": name,
                    "price": round(price, 2) if price else None,
                    "change": None,
                    "change_pct": None,
                }
        except (AttributeError, TypeError, KeyError) as e:
            logger.debug(f"fast_info failed for {symbol}, trying info()...")
            
            # Fallback to info()
            try:
                all_info = ticker.info
                if all_info:
                    price = all_info.get("currentPrice")
                    prev = all_info.get("previousClose")
                    
                    if price and prev:
                        change = price - prev
                        change_pct = (change / prev) * 100
                        return {
                            "symbol": symbol,
                            "name": name,
                            "price": round(price, 2),
                            "change": round(change, 2),
                            "change_pct": round(change_pct, 2),
                            "prev_close": round(prev, 2),
                        }
            except Exception as info_err:
                logger.debug(f"info() also failed for {symbol}: {info_err}")
            
            # Return None data if both methods fail
            return {
                "symbol": symbol,
                "name": name,
                "price": None,
                "change": None,
                "change_pct": None,
            }
            
    except Exception as e:
        logger.warning(f"Failed to fetch {symbol}: {str(e)}")
        return {
            "symbol": symbol,
            "name": name,
            "price": None,
            "change": None,
            "change_pct": None,
        }


def fetch_nse_indices() -> list[dict]:
    """
    Fetch index prices using yfinance fast_info with parallel requests.
    Results cached for 1 second.
    """
    global _cache, _cache_time

    now = time.time()
    if _cache and (now - _cache_time) < CACHE_TTL:
        return _cache

    results = []
    
    # Parallel fetch all tickers
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_fetch_single_ticker, symbol, name): symbol
            for symbol, name in TICKER_SYMBOLS.items()
        }
        
        for future in as_completed(futures):
            results.append(future.result())
    
    # Sort to maintain consistent order (Nifty, Bank Nifty, Sensex)
    symbol_order = list(TICKER_SYMBOLS.keys())
    results.sort(key=lambda x: symbol_order.index(x["symbol"]))

    _cache = results
    _cache_time = time.time()
    return results
