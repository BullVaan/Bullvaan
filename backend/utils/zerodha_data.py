"""Zerodha historical data fetcher for strategy signals.

Replaces Yahoo Finance for OHLCV data used by trading strategies.
Uses kite.historical_data() which is reliable and consistent with live ticks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

# IST = UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))

import pandas as pd

logger = logging.getLogger(__name__)

# Zerodha interval mapping
INTERVAL_MAP = {
    "1m": "minute",
    "5m": "5minute",
    "15m": "15minute",
    "30m": "30minute",
    "1h": "60minute",
    "1d": "day",
}

# Yahoo symbol -> Zerodha spot key
YAHOO_TO_ZERODHA = {
    "^NSEI": {"spot": "NSE:NIFTY 50", "name": "NIFTY"},
    "^NSEBANK": {"spot": "NSE:NIFTY BANK", "name": "BANKNIFTY"},
    "^BSESN": {"spot": "BSE:SENSEX", "name": "SENSEX"},
}

# India VIX Zerodha key
VIX_KEY = "NSE:INDIA VIX"


def fetch_zerodha_history(
    kite,
    symbol: str,
    interval: str = "5m",
    days: int = 5,
    get_spot_token_fn=None,
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV data from Zerodha for a given symbol.
    
    Args:
        kite: KiteConnect instance
        symbol: Yahoo-style symbol (^NSEI, ^NSEBANK, ^BSESN)
        interval: Candle interval (1m, 5m, 15m, etc.)
        days: Number of days to fetch
        get_spot_token_fn: Function to get instrument_token from zerodha symbol name
    
    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
        None on failure
    """
    try:
        config = YAHOO_TO_ZERODHA.get(symbol)
        if not config:
            logger.error(f"Unknown symbol for Zerodha: {symbol}")
            return None

        zerodha_name = config["name"]
        kite_interval = INTERVAL_MAP.get(interval, "5minute")

        # Get instrument token
        token = None
        if get_spot_token_fn:
            token = get_spot_token_fn(zerodha_name)

        if not token:
            # Fallback: resolve via kite.quote()
            spot_key = config["spot"]
            try:
                quote = kite.quote(spot_key)
                token = quote[spot_key].get("instrument_token")
            except Exception as e:
                logger.error(f"Could not resolve token for {spot_key}: {e}")
                return None

        if not token:
            logger.error(f"No instrument token for {zerodha_name}")
            return None

        # Fetch historical data (use IST — Zerodha expects Indian time)
        to_date = datetime.now(IST)
        from_date = to_date - timedelta(days=days)

        candles = kite.historical_data(token, from_date, to_date, kite_interval)

        if not candles:
            logger.warning(f"No candle data from Zerodha for {zerodha_name} ({kite_interval})")
            return None

        # Convert to DataFrame
        df = pd.DataFrame(candles)
        df = df.rename(columns={
            "date": "timestamp",
        })

        # Ensure numeric types
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if "volume" not in df.columns:
            df["volume"] = 0

        required = ["timestamp", "open", "high", "low", "close", "volume"]
        df = df[required]

        logger.info(f"Zerodha history: {zerodha_name} {kite_interval} → {len(df)} candles")
        return df

    except Exception as e:
        logger.error(f"Zerodha historical fetch failed for {symbol}: {e}")
        return None


def fetch_india_vix_zerodha(kite) -> dict:
    """
    Fetch India VIX from Zerodha quote API.
    
    Returns:
        dict with keys: value, change, change_pct, prev_close
    """
    try:
        quote = kite.quote(VIX_KEY)
        vix_data = quote.get(VIX_KEY, {})

        current_vix = vix_data.get("last_price", 0)
        ohlc = vix_data.get("ohlc", {})
        prev_close = ohlc.get("close", current_vix)  # previous day close

        if current_vix and current_vix > 0:
            change = round(current_vix - prev_close, 2)
            change_pct = round(((current_vix - prev_close) / prev_close) * 100, 2) if prev_close else 0

            return {
                "value": round(current_vix, 2),
                "change": change,
                "change_pct": change_pct,
                "prev_close": round(prev_close, 2),
            }
    except Exception as e:
        logger.error(f"Zerodha VIX fetch failed: {e}")

    return {"value": "-", "change": 0, "change_pct": 0, "prev_close": "-"}
