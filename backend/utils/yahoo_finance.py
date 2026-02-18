"""Yahoo Finance helpers (yfinance-based).

This module exists to make yfinance fetching more resilient:
- Retries transient failures
- Falls back across intervals when intraday data isn't available
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Optional

import pandas as pd
import yfinance as yf


@dataclass(frozen=True)
class YahooFetchResult:
    df: pd.DataFrame
    symbol: str
    period: str
    interval: str


def fetch_history(
    symbol: str,
    *,
    attempts: int = 3,
    sleep_seconds: float = 2.0,
    period_interval_fallback: Optional[list[tuple[str, str]]] = None,
) -> YahooFetchResult:
    """Fetch OHLCV history for `symbol` with retries and interval fallback.

    Returns raw yfinance dataframe (index is Date/Datetime).
    """

    if period_interval_fallback is None:
        period_interval_fallback = [
            ("5d", "5m"),
            ("5d", "15m"),
            ("1mo", "30m"),
            ("1mo", "1h"),
            ("6mo", "1d"),
        ]

    last_err: Optional[Exception] = None

    for attempt in range(1, attempts + 1):
        for period, interval in period_interval_fallback:
            try:
                # Let yfinance manage its own session (uses curl_cffi internally).
                df = yf.download(
                    symbol,
                    period=period,
                    interval=interval,
                    progress=False,
                    threads=False,
                    auto_adjust=False,
                    actions=False,
                    timeout=10,
                )

                # Check if df is None or empty before processing
                if df is None:
                    continue

                # yf.download can return a MultiIndex for columns in some cases.
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                if not df.empty:
                    return YahooFetchResult(df=df, symbol=symbol, period=period, interval=interval)

                # Fallback: try Ticker.history() for the same params.
                ticker = yf.Ticker(symbol)
                df2 = ticker.history(period=period, interval=interval, actions=False, auto_adjust=False)
                
                if df2 is None:
                    continue
                    
                if isinstance(df2.columns, pd.MultiIndex):
                    df2.columns = df2.columns.get_level_values(0)

                if not df2.empty:
                    return YahooFetchResult(df=df2, symbol=symbol, period=period, interval=interval)

            except TypeError as e:
                # Handle 'NoneType' subscripting errors
                last_err = e
                continue
            except AttributeError as e:
                # Handle attribute errors
                last_err = e
                continue
            except Exception as e:
                last_err = e
                continue

        # Backoff between attempts
        if attempt < attempts:
            time.sleep(sleep_seconds * attempt)

    raise RuntimeError(
        f"Yahoo fetch failed for {symbol} after {attempts} attempts"
        + (f": {last_err}" if last_err else "")
    )


def standardize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Convert a yfinance dataframe to columns: timestamp, open, high, low, close, volume."""

    if df is None or df.empty:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    out = df.copy()
    out = out.reset_index()

    out = out.rename(
        columns={
            "Date": "timestamp",
            "Datetime": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )

    # Some symbols/intervals may not provide volume.
    if "volume" not in out.columns:
        out["volume"] = 0

    required = ["timestamp", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in out.columns]
    if missing:
        raise ValueError(f"Missing columns from Yahoo data: {missing}. Available: {list(out.columns)}")

    return out[required]
