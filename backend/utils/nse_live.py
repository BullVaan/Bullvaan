"""
NSE Live Index Data Fetcher
Fetches real-time index prices via Zerodha KiteTicker
Uses live tick store populated by KiteTicker for NIFTY, Bank Nifty, Sensex
"""

import time
import logging

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
CACHE_TTL = 1  # seconds


def fetch_nse_indices(tick_store=None, index_tokens=None) -> list[dict]:
    """
    Fetch index prices from Zerodha KiteTicker live tick store.
    
    Args:
        tick_store: Dict of {token: tick_data} from KiteTicker
        index_tokens: Dict of {token: {name, key}} mapping
    
    Returns:
        List of index price dicts cached for 1 second
    """
    global _cache, _cache_time

    now = time.time()
    if _cache and (now - _cache_time) < CACHE_TTL:
        return _cache

    results = []
    
    # If no tick store provided, return cached or empty
    if not tick_store or not index_tokens:
        logger.warning("tick_store or index_tokens not provided to fetch_nse_indices")
        return []

    # Map token to symbol info
    # Index tokens like: {256265: {name: "Nifty 50", key: "NSE:NIFTY 50"}, ...}
    token_to_symbol = {}
    for token, info in index_tokens.items():
        name = info.get("name", "Unknown")
        key = info.get("key", "")
        
        # Map to our TICKER_SYMBOLS keys
        if "NIFTY 50" in name.upper() or "NIFTY" in key.upper():
            token_to_symbol[token] = ("^NSEI", "Nifty 50")
        elif "BANK" in name.upper() or "NIFTY BANK" in key.upper():
            token_to_symbol[token] = ("^NSEBANK", "Bank Nifty")
        elif "SENSEX" in name.upper() or "SENSEX" in key.upper():
            token_to_symbol[token] = ("^BSESN", "Sensex")

    # Query tick store for each index
    for token, (symbol, display_name) in token_to_symbol.items():
        try:
            tick = tick_store.get(token)
            
            if tick and tick.get("last_price"):
                last_price = tick.get("last_price")
                ohlc = tick.get("ohlc", {})
                prev_close = ohlc.get("close", last_price)
                
                if prev_close:
                    change = last_price - prev_close
                    change_pct = (change / prev_close) * 100
                else:
                    change = 0
                    change_pct = 0
                
                results.append({
                    "symbol": symbol,
                    "name": display_name,
                    "price": round(last_price, 2),
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                    "prev_close": round(prev_close, 2),
                })
            else:
                results.append({
                    "symbol": symbol,
                    "name": display_name,
                    "price": None,
                    "change": None,
                    "change_pct": None,
                })
                
        except Exception as e:
            logger.warning(f"Failed to fetch tick data for {display_name}: {str(e)}")
            results.append({
                "symbol": symbol,
                "name": display_name,
                "price": None,
                "change": None,
                "change_pct": None,
            })

    _cache = results
    _cache_time = time.time()
    return results

