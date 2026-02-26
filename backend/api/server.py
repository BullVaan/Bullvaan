from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import logging
import os
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
from kiteconnect import KiteConnect, KiteTicker
from utils.nse_live import fetch_nse_indices

# Load environment variables
load_dotenv()

# Initialize Zerodha Kite Connect
api_key = os.getenv("API_KEY")
access_token = os.getenv("ACCESS_TOKEN")
kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

# =========================
# KiteTicker: Real-time tick store
# =========================
# Shared dict: instrument_token -> tick data (updated by KiteTicker thread)
_tick_store = {}
# Map instrument_token -> symbol info for reverse lookup
_token_map = {}
# List of asyncio Events to notify WebSocket consumers on new ticks
_tick_listeners = []
_kws = None

def _on_ticks(ws, ticks):
    """Called by KiteTicker on every tick — runs in Twisted thread"""
    for tick in ticks:
        token = tick["instrument_token"]
        _tick_store[token] = tick
    # Notify all async listeners
    for evt in list(_tick_listeners):
        evt.set()

def _on_connect(ws, response):
    """Called when KiteTicker connects"""
    tokens = list(_token_map.keys())
    if tokens:
        ws.subscribe(tokens)
        ws.set_mode(ws.MODE_QUOTE, tokens)
        logging.getLogger("api.server").info(f"KiteTicker subscribed to {len(tokens)} tokens")

def _on_close(ws, code, reason):
    logging.getLogger("api.server").warning(f"KiteTicker closed: {code} - {reason}")

def _on_error(ws, code, reason):
    logging.getLogger("api.server").error(f"KiteTicker error: {code} - {reason}")

def start_ticker(subscribe_tokens):
    """Start KiteTicker in a background thread. subscribe_tokens = {token: info_dict}"""
    global _kws
    _token_map.update(subscribe_tokens)

    if _kws is not None:
        # Already running — just subscribe new tokens
        new_tokens = list(subscribe_tokens.keys())
        if new_tokens:
            try:
                _kws.subscribe(new_tokens)
                _kws.set_mode(_kws.MODE_QUOTE, new_tokens)
            except Exception:
                pass
        return

    _kws = KiteTicker(api_key, access_token)
    _kws.on_ticks = _on_ticks
    _kws.on_connect = _on_connect
    _kws.on_close = _on_close
    _kws.on_error = _on_error
    _kws.connect(threaded=True)

def get_tick(token):
    """Get latest tick for an instrument token"""
    return _tick_store.get(token)

def _get_spot_token(zerodha_symbol):
    """Get the INDEX_TOKENS instrument_token for a given zerodha symbol"""
    cfg = SYMBOL_CONFIG.get(zerodha_symbol, SYMBOL_CONFIG["NIFTY"])
    spot_key = cfg["spot"]
    for token, info in INDEX_TOKENS.items():
        if info["key"] == spot_key:
            return token
    return None

async def wait_for_tick(timeout=2):
    """Async wait until a new tick arrives (thread-safe)"""
    evt = threading.Event()
    _tick_listeners.append(evt)
    try:
        loop = asyncio.get_event_loop()
        await asyncio.wait_for(loop.run_in_executor(None, evt.wait), timeout=timeout)
    except asyncio.TimeoutError:
        pass
    finally:
        if evt in _tick_listeners:
            _tick_listeners.remove(evt)


# strategies
from strategies.strategy_1_moving_average import MovingAverageStrategy
from strategies.strategy_2_rsi import RSIStrategy
from strategies.strategy_3_macd import MACDStrategy
from strategies.strategy_5_ema_crossover import EMACrossoverStrategy
from strategies.strategy_6_supertrend import SupertrendStrategy
from strategies.strategy_8_stochastic import StochasticStrategy
from strategies.strategy_9_adx import ADXStrategy

# auto-trading engine
from engine.auto_trader import AutoTrader

# data utils
from utils.yahoo_finance import fetch_history, standardize_ohlcv
import yfinance as yf
import pandas as pd
import numpy as np

from api.signup import router as signup_router
from api.login import router as login_router

app = FastAPI(title="Bullvan Trading API")

app.include_router(signup_router, prefix="/api")
app.include_router(login_router, prefix="/api")

# =========================
# Setup Logging
# =========================
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Suppress verbose yfinance warnings
logging.getLogger('yfinance').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)


# =========================
# CORS (Allow frontend)
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for dev. Later replace with frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Index instrument tokens for KiteTicker
# =========================
INDEX_TOKENS = {}  # Will be populated at startup: {token: {name, key}}

@app.on_event("startup")
def startup_init_ticker():
    """Resolve index instrument tokens and start KiteTicker"""
    indices_to_track = [
        {"exchange": "NSE", "tradingsymbol": "NIFTY 50", "name": "Nifty 50"},
        {"exchange": "NSE", "tradingsymbol": "NIFTY BANK", "name": "Bank Nifty"},
        {"exchange": "BSE", "tradingsymbol": "SENSEX", "name": "Sensex"},
    ]
    subscribe = {}
    for idx in indices_to_track:
        try:
            ltp_key = f"{idx['exchange']}:{idx['tradingsymbol']}"
            quote = kite.quote(ltp_key)
            token = quote[ltp_key].get("instrument_token")
            if token:
                subscribe[token] = {"name": idx["name"], "key": ltp_key}
                INDEX_TOKENS[token] = {"name": idx["name"], "key": ltp_key}
                logger.info(f"Index {idx['name']} -> token {token}")
            else:
                logger.warning(f"No instrument_token in quote for {ltp_key}: {quote[ltp_key]}")
        except Exception as e:
            logger.warning(f"Could not resolve token for {idx['tradingsymbol']}: {e}")

    if subscribe:
        start_ticker(subscribe)
        logger.info(f"KiteTicker started with {len(subscribe)} index tokens")



# Supported Indices
# =========================
SUPPORTED_INDICES = {
    "^NSEI": "NIFTY 50",
    "^NSEBANK": "BANK NIFTY",
    "^BSESN": "SENSEX",
}


# =========================
# Initialize Strategies Once (SCALPING OPTIMIZED)
# =========================
strategies = [
    MovingAverageStrategy(5),           # Fast trend (5 candles)
    RSIStrategy(7, 35, 65),             # Fast momentum (7 period)
    MACDStrategy(5, 13, 1),             # Already optimized for scalping
    EMACrossoverStrategy(5, 13),        # Fast EMA crossover
    SupertrendStrategy(7, 2),           # Tight ATR for quick exits
    StochasticStrategy(5, 3, 3),        # Fast overbought/oversold
    ADXStrategy(14, 25),                # Trend strength filter
]

NIFTY50_SYMBOLS = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS",
    "ITC.NS","LT.NS","SBIN.NS","AXISBANK.NS","KOTAKBANK.NS",
    "HINDUNILVR.NS","ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS","TITAN.NS",
    "ULTRACEMCO.NS","NESTLEIND.NS","WIPRO.NS","NTPC.NS","POWERGRID.NS",
    "JSWSTEEL.NS","TATASTEEL.NS","BAJFINANCE.NS","BAJAJFINSV.NS","ONGC.NS",
    "HCLTECH.NS","TECHM.NS","COALINDIA.NS","INDUSINDBK.NS","ADANIENT.NS",
    "ADANIPORTS.NS","BHARTIARTL.NS","BRITANNIA.NS","CIPLA.NS","DIVISLAB.NS",
    "DRREDDY.NS","EICHERMOT.NS","GRASIM.NS","HEROMOTOCO.NS","HINDALCO.NS",
    "BPCL.NS","IOC.NS","M&M.NS","SHREECEM.NS","SBILIFE.NS",
    "TATACONSUM.NS","UPL.NS","APOLLOHOSP.NS","BAJAJ-AUTO.NS","PIDILITIND.NS"
]

SECTOR_MAP = {
    "TCS":"IT","INFY":"IT","WIPRO":"IT","HCLTECH":"IT","TECHM":"IT",
    "RELIANCE":"Energy","ONGC":"Energy","IOC":"Energy","BPCL":"Energy",
    "HDFCBANK":"Bank","ICICIBANK":"Bank","SBIN":"Bank","AXISBANK":"Bank","KOTAKBANK":"Bank",
    "LT":"Infra","ULTRACEMCO":"Infra","GRASIM":"Infra",
    "ITC":"FMCG","HINDUNILVR":"FMCG","NESTLEIND":"FMCG","BRITANNIA":"FMCG",
}

# =========================
# Strategy Roles (Group by Purpose) - SCALPING CONFIG
# =========================
STRATEGY_ROLES = {
    "Trend": ["MA(5)", "EMA(5,13)"],
    "Momentum": ["RSI(7)", "MACD(5,13,1)", "Stoch(5,3,3)"],
    "Strength": ["Supertrend(7,2)", "ADX(14)"]
}

# =========================
# Timeframe Configuration
# =========================
TIMEFRAME_CONFIG = {
    "5m": {"description": "5-minute scalping", "data_points": 100},
    "15m": {"description": "15-minute scalping", "data_points": 50},
    "30m": {"description": "30-minute swing-scalp", "data_points": 30},
}

ACTIVE_TIMEFRAME = "5m"


# =========================
# Helper Functions
# =========================
def fetch_india_vix():
    """Fetch live India VIX (volatility index) with real day change"""
    try:
        # Fetch both today and yesterday to get proper previous close
        vix_data = yf.download("^INDIAVIX", period="5d", interval="1d", progress=False, threads=False, auto_adjust=False)
        
        if vix_data is not None and not vix_data.empty:
            # Current price = today's latest close
            current_vix = float(vix_data['Close'].iloc[-1].item())
            
            # Previous close = yesterday's close
            if len(vix_data) > 1:
                prev_close_vix = float(vix_data['Close'].iloc[-2].item())
            else:
                prev_close_vix = current_vix
            
            # Calculate actual day change
            change = round(current_vix - prev_close_vix, 2)
            change_pct = round(((current_vix - prev_close_vix) / prev_close_vix) * 100, 2) if prev_close_vix != 0 else 0
            
            return {
                "value": round(current_vix, 2),
                "change": change,
                "change_pct": change_pct,
                "prev_close": round(prev_close_vix, 2)
            }
    except Exception as e:
        logger.error(f"Failed to fetch India VIX: {str(e)}")
    return {"value": "-", "change": 0, "change_pct": 0, "prev_close": "-"}

def detect_breakout(df):
    if len(df) < 2:
        return "NONE"

    prev_high = df["High"].iloc[-2]
    prev_low = df["Low"].iloc[-2]
    current = df["Close"].iloc[-1]

    if current > prev_high:
        return "BREAKOUT"
    elif current < prev_low:
        return "BREAKDOWN"
    return "NONE"

def momentum_score(change_pct, volume, avg_volume):
    vol_score = min(volume / avg_volume, 2) * 50
    price_score = min(abs(change_pct), 5) * 10
    return round(vol_score + price_score)

def volume_label(ratio):
    if ratio > 2:
        return "EXPLOSION"
    elif ratio > 1.2:
        return "SPIKE"
    elif ratio >= 0.8:
        return "NORMAL"
    return "LOW"   

def volume_trend(df):
    try:
        vols = df["Volume"].tail(3).tolist()

        if len(vols) < 3:
            return "→"

        v1, v2, v3 = vols

        # tolerance factor (10%)
        tol = 0.9

        # Mostly increasing
        if v3 > v2 * tol and v2 > v1 * tol:
            return "↑"

        # Mostly decreasing
        if v3 < v2 / tol and v2 < v1 / tol:
            return "↓"

        return "→"

    except:
        return "→"    

# =========================
# ATM Strike Finder
# =========================
def nearest_strike(price):
    return round(price / 50) * 50

def calculate_atr(df, period=14):
    """Calculate Average True Range (ATR)"""
    try:
        if len(df) < period:
            return "-"
        
        df_copy = df.copy()
        df_copy['prev_close'] = df_copy['close'].shift(1)
        df_copy['high_low'] = df_copy['high'] - df_copy['low']
        df_copy['high_pc'] = abs(df_copy['high'] - df_copy['prev_close'])
        df_copy['low_pc'] = abs(df_copy['low'] - df_copy['prev_close'])
        
        df_copy['tr'] = df_copy[['high_low', 'high_pc', 'low_pc']].max(axis=1)
        df_copy['atr'] = df_copy['tr'].rolling(window=period).mean()
        
        current_atr = float(df_copy['atr'].iloc[-1])
        return round(current_atr, 2)
    except Exception as e:
        logger.error(f"Failed to calculate ATR: {str(e)}")
        return "-"

def fetch_nifty50_movers():
    try:
        data = yf.download(
            tickers=" ".join(NIFTY50_SYMBOLS),
            period="2d",
            interval="1d",
            group_by="ticker",
            progress=False,
            threads=True
        )

        movers = []

        for symbol in NIFTY50_SYMBOLS:
            try:
                df = data[symbol].dropna()

                if len(df) < 2:
                    continue

                prev_close = df["Close"].iloc[-2]
                current = df["Close"].iloc[-1]
                volume = int(df["Volume"].iloc[-1])
                avg_vol = df["Volume"].tail(5).mean()
                volume_ratio = volume / avg_vol if avg_vol else 1

                change_pct = ((current - prev_close) / prev_close) * 100
                price_change = current - prev_close

                stock = symbol.replace(".NS", "")

                # breakout detection
                breakout = detect_breakout(df)

                # momentum score
                score = momentum_score(change_pct, volume, avg_vol)

                movers.append({
                "symbol": stock,
                "price": round(float(current), 2),
                "percentChange": round(float(change_pct), 2),
                "priceChange": round(float(price_change), 2),   # ← ADD THIS
                "volume": volume,
                "avgVolume": int(avg_vol),
                "volumeRatio": round(volume_ratio,2),
                "volumeSignal": volume_label(volume_ratio),
                "volumeTrend": volume_trend(df),
                "sector": SECTOR_MAP.get(stock, "Other"),
                "breakout": breakout,
                "momentum": score,
                "optionStrike": nearest_strike(current)
            })

            except Exception as e:
                logger.warning(f"Skipping {symbol}: {e}")
                continue

        # ===== strongest sector calculation =====
        sector_perf = {}
        for s in movers:
            sector_perf.setdefault(s["sector"], []).append(s["percentChange"])

        strongest_sector = "Unknown"

        if sector_perf:
            strongest_sector = max(
                sector_perf.items(),
                key=lambda x: sum(x[1]) / len(x[1])
            )[0]

        return movers, strongest_sector

    except Exception as e:
        logger.error(f"Nifty50 fetch error: {e}", exc_info=True)
        return [], "Unknown"
# =========================
# Health Check Route
# =========================
@app.get("/")
def home():
    return {"status": "Bullvan API running"}


# =========================
# Get Signals Route
# =========================
@app.get("/signals")
def get_signals(symbol: str = "^NSEI", timeframe: str = "5m"):
    """
    Returns signals for selected index
    
    Args:
        symbol: Index symbol (^NSEI, ^NSEBANK, ^BSESN)
        timeframe: Trading timeframe (5m, 15m, 30m)
    
    Default = NIFTY, 5-minute
    """

    # validate symbol
    if symbol not in SUPPORTED_INDICES:
        return {
            "error": "Invalid symbol",
            "supported": list(SUPPORTED_INDICES.keys())
        }

    # validate timeframe
    if timeframe not in TIMEFRAME_CONFIG:
        return {
            "error": "Invalid timeframe",
            "supported": list(TIMEFRAME_CONFIG.keys())
        }

    try:
        # fetch market data
        fetched = fetch_history(symbol)
        if fetched is None or fetched.df is None:
            return {"error": f"No data available for {symbol}"}
        
        df = standardize_ohlcv(fetched.df)

        if df.empty:
            return {"error": "No market data received"}

        # current price
        current_price = float(df["close"].iloc[-1])
        
        # fetch india vix (live volatility)
        india_vix = fetch_india_vix()
        
        # calculate atr
        atr = calculate_atr(df, period=14)

        all_signals = []
        votes = []
        signals_by_role = {}

        # run strategies
        for strat in strategies:
            signal = strat.calculate(df)

            all_signals.append({
                "name": strat.name,
                "signal": signal
            })

            votes.append(signal)

        # organize signals by role
        for role, indicator_names in STRATEGY_ROLES.items():
            signals_by_role[role] = [
                sig for sig in all_signals 
                if sig["name"] in indicator_names
            ]

        # vote counts (overall)
        buy = votes.count("BUY")
        sell = votes.count("SELL")
        neutral = votes.count("NEUTRAL")

        # NEW CONSENSUS LOGIC: Trend + Strength vs Momentum
        # Trend (2) + Strength (2) = 4 indicators
        # Momentum = 3 indicators
        
        trend_signals = [s["signal"] for s in signals_by_role.get("Trend", [])]
        strength_signals = [s["signal"] for s in signals_by_role.get("Strength", [])]
        momentum_signals = [s["signal"] for s in signals_by_role.get("Momentum", [])]
        
        # Combine Trend + Strength
        trend_strength = trend_signals + strength_signals
        ts_buy = trend_strength.count("BUY")
        ts_sell = trend_strength.count("SELL")
        
        # Momentum counts
        mom_buy = momentum_signals.count("BUY")
        mom_sell = momentum_signals.count("SELL")
        mom_neutral = momentum_signals.count("NEUTRAL")
        
        # Determine Trend+Strength direction (need 3+ of 4)
        ts_direction = None
        if ts_buy >= 3:
            ts_direction = "BUY"
        elif ts_sell >= 3:
            ts_direction = "SELL"
        
        # Apply new rules
        consensus = "NEUTRAL"
        stop_loss_warning = False
        signal_strength = "NONE"  # STRONG, MEDIUM, WEAK, NONE
        
        if ts_direction:
            # All Trend agree?
            trend_all = all(s == ts_direction for s in trend_signals) if trend_signals else False
            # All Strength agree?
            strength_all = all(s == ts_direction for s in strength_signals) if strength_signals else False
            # Momentum agreement
            mom_agree = (mom_buy >= 2 if ts_direction == "BUY" else mom_sell >= 2)
            
            # STRONG: Trend ALL + Momentum 2/3 + Strength ALL
            if trend_all and strength_all and mom_agree:
                consensus = ts_direction
                signal_strength = "STRONG"
            # MEDIUM: Trend ALL + Strength ALL + Momentum mostly neutral
            elif trend_all and strength_all and mom_neutral >= 2:
                consensus = ts_direction
                signal_strength = "MEDIUM"
            # WEAK: Trend+Strength overrides opposing Momentum
            elif (ts_direction == "BUY" and mom_sell >= 2) or (ts_direction == "SELL" and mom_buy >= 2):
                consensus = ts_direction
                stop_loss_warning = True
                signal_strength = "WEAK"
            # Fallback: Trend+Strength direction holds
            else:
                consensus = ts_direction
                signal_strength = "MEDIUM"

        # response
        return {
            "symbol": symbol,
            "index_name": SUPPORTED_INDICES[symbol],
            "timeframe": timeframe,
            "timeframe_info": TIMEFRAME_CONFIG[timeframe],
            "price": round(current_price, 2),
            "india_vix": india_vix,
            "atr": atr,
            "consensus": consensus,
            "signal_strength": signal_strength,
            "stop_loss_warning": stop_loss_warning,
            "buy_votes": buy,
            "sell_votes": sell,
            "neutral_votes": neutral,
            "total_strategies": len(strategies),
            "signals": all_signals,
            "signals_by_role": signals_by_role
        }

    except RuntimeError as e:
        # Handle fetch failures gracefully
        logger.error(f"Data fetch failed for {symbol}: {str(e)}")
        return {
            "error": "Data fetch failed",
            "message": str(e),
            "symbol": symbol
        }
    except ValueError as e:
        # Handle standardization errors
        logger.error(f"Data standardization failed for {symbol}: {str(e)}")
        return {
            "error": "Data standardization failed",
            "message": str(e),
            "symbol": symbol
        }
    except Exception as e:
        logger.error(f"Unexpected error for {symbol}: {str(e)}", exc_info=True)
        return {
            "error": "Server error",
            "message": str(e),
            "symbol": symbol
        }


# =========================
# Zerodha Options Chain - February Expiry
# =========================
@app.get("/options")
def get_options(symbol: str = "NIFTY", strike: int = None):
    """
    Fetch live option prices from Zerodha for current month expiry
    symbol: NIFTY or BANKNIFTY
    strike: ATM strike price (optional, will calculate if not provided)
    """
    try:
        # Map symbols
        zerodha_symbol = SYMBOL_MAP.get(symbol, "NIFTY")
        
        # Use cached near-expiry options
        feb_options, nearest_expiry = get_near_expiry_options(zerodha_symbol)
        
        if not feb_options:
            return {"error": "No options found", "symbol": zerodha_symbol}
        
        expiry_date = str(nearest_expiry)
        cfg = SYMBOL_CONFIG.get(zerodha_symbol, SYMBOL_CONFIG["NIFTY"])
        
        # If no strike provided, calculate ATM from current price
        if strike is None:
            ltp_data = kite.ltp(cfg["spot"])
            spot_price = ltp_data[cfg["spot"]]["last_price"]
            
            interval = cfg["interval"]
            strike = round(spot_price / interval) * interval
        
        # Find ATM, OTM CE and PE options
        atm_ce = next((i for i in feb_options if i['strike'] == strike and i['instrument_type'] == 'CE'), None)
        atm_pe = next((i for i in feb_options if i['strike'] == strike and i['instrument_type'] == 'PE'), None)
        otm_ce = next((i for i in feb_options if i['strike'] == strike + cfg["interval"] and i['instrument_type'] == 'CE'), None)
        otm_pe = next((i for i in feb_options if i['strike'] == strike - cfg["interval"] and i['instrument_type'] == 'PE'), None)
        
        # Get live prices for these options
        exchange_prefix = cfg["exchange"]
        option_tokens = []
        option_map = {}
        
        for opt, label in [(atm_ce, 'atm_ce'), (atm_pe, 'atm_pe'), (otm_ce, 'otm_ce'), (otm_pe, 'otm_pe')]:
            if opt:
                token = f"{exchange_prefix}:{opt['tradingsymbol']}"
                option_tokens.append(token)
                option_map[token] = {
                    "label": label,
                    "strike": opt['strike'],
                    "type": opt['instrument_type'],
                    "symbol": opt['tradingsymbol']
                }
        
        # Fetch LTP for all options
        if option_tokens:
            ltp_data = kite.ltp(option_tokens)
        else:
            ltp_data = {}
        
        # Build response
        options_data = []
        for token, info in option_map.items():
            price_info = ltp_data.get(token, {})
            options_data.append({
                "label": info["label"],
                "strike": info["strike"],
                "type": info["type"],
                "symbol": info["symbol"],
                "ltp": price_info.get("last_price", 0),
                "token": token
            })
        
        return {
            "symbol": zerodha_symbol,
            "expiry": expiry_date,
            "atm_strike": strike,
            "options": options_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Options fetch error: {e}", exc_info=True)
        return {
            "error": str(e),
            "symbol": symbol
        }


# =========================
# Available Indices Route
# =========================
@app.get("/indices")
def get_indices():
    return SUPPORTED_INDICES


# =========================
# Available Timeframes Route
# =========================
@app.get("/timeframes")
def get_timeframes():
    """Returns available timeframe configurations"""
    return TIMEFRAME_CONFIG


# =========================
# NSE Ticker (HTTP fallback)
# =========================
@app.get("/ticker")
def get_ticker():
    """HTTP fallback — returns latest NSE index prices with error handling"""
    try:
        data = fetch_nse_indices()
        if data and isinstance(data, list) and len(data) > 0:
            return data
        else:
            logger.warning("fetch_nse_indices returned empty data")
            return {
                "error": "No ticker data available",
                "indices": list(SUPPORTED_INDICES.keys())
            }
    except Exception as e:
        logger.error(f"Ticker fetch failed: {str(e)}", exc_info=True)
        return {
            "error": "Failed to fetch ticker data",
            "message": str(e),
            "indices": list(SUPPORTED_INDICES.keys())
        }


# =========================
# Near-expiry options cache (per symbol, loaded once per day)
# =========================
# Symbol config: zerodha name, exchange, spot key, strike interval
SYMBOL_CONFIG = {
    "NIFTY": {"exchange": "NFO", "spot": "NSE:NIFTY 50", "interval": 50},
    "BANKNIFTY": {"exchange": "NFO", "spot": "NSE:NIFTY BANK", "interval": 100},
    "SENSEX": {"exchange": "BFO", "spot": "BSE:SENSEX", "interval": 100},
}

SYMBOL_MAP = {
    "^NSEI": "NIFTY", "NIFTY": "NIFTY",
    "^NSEBANK": "BANKNIFTY", "BANKNIFTY": "BANKNIFTY",
    "^BSESN": "SENSEX", "SENSEX": "SENSEX",
}

# =========================
# Auto-Trader Helpers
# =========================
def _auto_get_signal(symbol):
    """Wrapper: call get_signals() for the auto-trader"""
    return get_signals(symbol=symbol, timeframe="5m")

def _auto_get_option_ltp(prefix, opt_type, strike=None):
    """
    Get live option LTP from KiteTicker tick store.
    If strike is given, look up that exact instrument.
    If not, look up the current ATM.
    """
    try:
        zerodha_symbol = prefix  # already "NIFTY", "BANKNIFTY", etc.
        expiry_options, _ = get_near_expiry_options(zerodha_symbol)
        cfg = SYMBOL_CONFIG.get(zerodha_symbol, SYMBOL_CONFIG["NIFTY"])

        if strike is None:
            # Calculate ATM from spot
            spot_token = _get_spot_token(zerodha_symbol)
            if not spot_token:
                return None
            spot_tick = get_tick(spot_token)
            if not spot_tick:
                return None
            spot = spot_tick["last_price"]
            interval = cfg["interval"]
            strike = round(spot / interval) * interval

        # Find the instrument
        opt = next(
            (i for i in expiry_options
             if i['strike'] == strike and i['instrument_type'] == opt_type),
            None
        )
        if not opt:
            return None

        tok = opt['instrument_token']
        # Check tick store first
        tick = get_tick(tok)
        if tick:
            return tick["last_price"]

        # Not subscribed yet — subscribe and fetch via API
        start_ticker({tok: {
            "name": opt['tradingsymbol'],
            "key": f"{cfg['exchange']}:{opt['tradingsymbol']}"
        }})
        # Try API fallback
        try:
            ltp_key = f"{cfg['exchange']}:{opt['tradingsymbol']}"
            ltp_data = kite.ltp(ltp_key)
            return ltp_data.get(ltp_key, {}).get("last_price")
        except Exception:
            return None
    except Exception as e:
        logger.error(f"Auto-trader LTP fetch error: {e}")
        return None

# Initialize auto-trader (singleton)
auto_trader = AutoTrader(
    get_signal_fn=_auto_get_signal,
    get_option_ltp_fn=_auto_get_option_ltp,
)

_near_expiry_cache = {}

def get_near_expiry_options(zerodha_symbol):
    """Return cached near-expiry options for a symbol, refresh once per day"""
    today = datetime.now().date()
    cached = _near_expiry_cache.get(zerodha_symbol)
    if cached and cached["date"] == today:
        return cached["options"], cached["expiry"]

    cfg = SYMBOL_CONFIG.get(zerodha_symbol, SYMBOL_CONFIG["NIFTY"])
    instruments = kite.instruments(cfg["exchange"])
    all_opts = [
        i for i in instruments
        if i['name'] == zerodha_symbol
        and i['instrument_type'] in ['CE', 'PE']
        and i['expiry'] >= today
    ]
    expiries = sorted(set(i['expiry'] for i in all_opts))
    if not expiries:
        return [], None
    nearest = expiries[0]
    near_opts = [i for i in all_opts if i['expiry'] == nearest]
    _near_expiry_cache[zerodha_symbol] = {"options": near_opts, "expiry": nearest, "date": today}
    logger.info(f"Cached {len(near_opts)} near-expiry options for {zerodha_symbol} (exp: {nearest})")
    return near_opts, nearest

# =========================
# WebSocket: Live Options Prices
# =========================
@app.websocket("/ws/options")
async def ws_options(websocket: WebSocket):
    """
    Streams live option prices (ATM/OTM CE & PE) via KiteTicker — real-time.
    Client sends: {"symbol": "^NSEI"} to subscribe
    """
    await websocket.accept()
    try:
        # Wait for client to send symbol
        msg = await websocket.receive_text()
        params = json.loads(msg)
        symbol = params.get("symbol", "^NSEI")

        zerodha_symbol = SYMBOL_MAP.get(symbol, "NIFTY")
        expiry_options, nearest_expiry = get_near_expiry_options(zerodha_symbol)
        cfg = SYMBOL_CONFIG.get(zerodha_symbol, SYMBOL_CONFIG["NIFTY"])

        # Track option tokens currently subscribed to KiteTicker
        option_tokens = {}  # {instrument_token: {label, strike, type}}
        last_strike = None

        while True:
            try:
                # Check if client sent a new symbol (non-blocking)
                try:
                    new_msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                    new_params = json.loads(new_msg)
                    new_symbol = new_params.get("symbol", symbol)
                    if new_symbol != symbol:
                        symbol = new_symbol
                        zerodha_symbol = SYMBOL_MAP.get(symbol, "NIFTY")
                        expiry_options, nearest_expiry = get_near_expiry_options(zerodha_symbol)
                        cfg = SYMBOL_CONFIG.get(zerodha_symbol, SYMBOL_CONFIG["NIFTY"])
                        option_tokens = {}
                        last_strike = None
                except asyncio.TimeoutError:
                    pass

                if not expiry_options:
                    await websocket.send_text(json.dumps({"error": "No options found"}))
                    await wait_for_tick(timeout=1)
                    continue

                # Get spot price from KiteTicker tick store
                spot_token = _get_spot_token(zerodha_symbol)
                if not spot_token:
                    await websocket.send_text(json.dumps({"error": "Spot token not resolved"}))
                    await wait_for_tick(timeout=1)
                    continue

                spot_tick = get_tick(spot_token)
                if not spot_tick:
                    await websocket.send_text(json.dumps({"error": "Waiting for spot price..."}))
                    await wait_for_tick(timeout=1)
                    continue

                spot = spot_tick["last_price"]
                interval = cfg["interval"]
                strike = round(spot / interval) * interval

                # If ATM strike changed, subscribe new option instrument tokens
                if strike != last_strike:
                    last_strike = strike
                    option_tokens = {}

                    atm_ce = next((i for i in expiry_options if i['strike'] == strike and i['instrument_type'] == 'CE'), None)
                    atm_pe = next((i for i in expiry_options if i['strike'] == strike and i['instrument_type'] == 'PE'), None)
                    otm_ce = next((i for i in expiry_options if i['strike'] == strike + interval and i['instrument_type'] == 'CE'), None)
                    otm_pe = next((i for i in expiry_options if i['strike'] == strike - interval and i['instrument_type'] == 'PE'), None)

                    subscribe = {}
                    for opt, label in [(atm_ce, 'atm_ce'), (atm_pe, 'atm_pe'), (otm_ce, 'otm_ce'), (otm_pe, 'otm_pe')]:
                        if opt:
                            tok = opt['instrument_token']
                            option_tokens[tok] = {"label": label, "strike": opt['strike'], "type": opt['instrument_type']}
                            subscribe[tok] = {"name": opt['tradingsymbol'], "key": f"{cfg['exchange']}:{opt['tradingsymbol']}"}

                    if subscribe:
                        start_ticker(subscribe)
                        logger.info(f"Subscribed {len(subscribe)} option tokens for {zerodha_symbol} strike {strike}")

                # ── Track open trade instrument for live LTP ──
                open_trade_ltp_val = None
                try:
                    trades = _load_trades()
                    active_trade = next(
                        (t for t in trades
                         if t.get('status') == 'open'
                         and t['name'].upper().startswith(zerodha_symbol)),
                        None
                    )
                    if active_trade:
                        parts = active_trade['name'].split()
                        trade_strike = float(parts[1])
                        trade_type = parts[2]  # CE or PE
                        # Check if already in current ATM/OTM set
                        existing_tok = next(
                            (tok for tok, info in option_tokens.items()
                             if info['strike'] == trade_strike and info['type'] == trade_type),
                            None
                        )
                        if existing_tok:
                            tick = get_tick(existing_tok)
                            open_trade_ltp_val = tick["last_price"] if tick and tick.get("last_price") else None
                        else:
                            # Subscribe to the bought instrument
                            trade_opt = next(
                                (i for i in expiry_options
                                 if i['strike'] == trade_strike
                                 and i['instrument_type'] == trade_type),
                                None
                            )
                            if trade_opt:
                                tok = trade_opt['instrument_token']
                                if tok not in option_tokens:
                                    option_tokens[tok] = {
                                        "label": "open_trade",
                                        "strike": trade_opt['strike'],
                                        "type": trade_opt['instrument_type']
                                    }
                                    start_ticker({tok: {
                                        "name": trade_opt['tradingsymbol'],
                                        "key": f"{cfg['exchange']}:{trade_opt['tradingsymbol']}"
                                    }})
                                tick = get_tick(tok)
                                open_trade_ltp_val = tick["last_price"] if tick and tick.get("last_price") else None
                except Exception as e:
                    logger.error(f"Open trade LTP tracking error: {e}")

                # Build response from tick store
                options_list = []
                for tok, info in option_tokens.items():
                    tick = get_tick(tok)
                    ltp = tick["last_price"] if tick else 0
                    options_list.append({
                        "label": info["label"],
                        "strike": info["strike"],
                        "type": info["type"],
                        "ltp": ltp
                    })

                resp = {
                    "symbol": zerodha_symbol,
                    "expiry": str(nearest_expiry),
                    "atm_strike": strike,
                    "options": options_list,
                    "timestamp": datetime.now().isoformat()
                }
                if open_trade_ltp_val is not None:
                    resp["open_trade_ltp"] = open_trade_ltp_val

                await websocket.send_text(json.dumps(resp))

            except (WebSocketDisconnect, asyncio.CancelledError):
                break
            except Exception as e:
                if 'close' in str(e).lower() or any(c in str(e) for c in ['1001', '1005', '1012']):
                    break
                logger.error(f"Options WS tick error: {e}")

            # Wait for next tick (real-time, no polling delay)
            await wait_for_tick(timeout=1)

    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as e:
        logger.error(f"Options WS error: {e}", exc_info=True)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

# =========================
# WebSocket: Real-time Trade LTP (open positions)
# =========================
@app.websocket("/ws/trades")
async def ws_trades(websocket: WebSocket):
    """
    Streams live LTP for all open trade instruments via KiteTicker — real-time.
    Automatically detects open trades, subscribes to their instrument tokens,
    and pushes price updates on every tick.
    """
    await websocket.accept()
    try:
        subscribed_tokens = {}  # { instrument_token: trade_name }

        while True:
            try:
                # Load open trades
                trades = _load_trades()
                open_trades = [t for t in trades if t.get('status') == 'open']

                if not open_trades:
                    await websocket.send_text(json.dumps({}))
                    await wait_for_tick(timeout=2)
                    continue

                # Parse each open trade name and ensure we're subscribed
                needed = {}  # { trade_name: { prefix, strike, type, token } }
                for t in open_trades:
                    name = t['name']
                    parts = name.split()
                    if len(parts) < 3:
                        continue
                    prefix = parts[0]
                    try:
                        strike = float(parts[1])
                    except ValueError:
                        continue
                    opt_type = parts[2]

                    # Check if already subscribed
                    existing = next(
                        (tok for tok, meta in subscribed_tokens.items() if meta.get("name") == name),
                        None
                    )
                    if existing:
                        needed[name] = subscribed_tokens[existing]
                        needed[name]["token"] = existing
                        continue

                    # Find instrument and subscribe
                    zerodha_symbol = prefix
                    cfg = SYMBOL_CONFIG.get(zerodha_symbol, SYMBOL_CONFIG.get("NIFTY"))
                    expiry_options, _ = get_near_expiry_options(zerodha_symbol)
                    if not expiry_options:
                        continue

                    opt = next(
                        (i for i in expiry_options
                         if i['strike'] == strike and i['instrument_type'] == opt_type),
                        None
                    )
                    if not opt:
                        continue

                    tok = opt['instrument_token']
                    ltp_key = f"{cfg['exchange']}:{opt['tradingsymbol']}"
                    subscribed_tokens[tok] = {"name": name, "ltp_key": ltp_key}
                    needed[name] = {"token": tok, "ltp_key": ltp_key}
                    start_ticker({tok: {
                        "name": opt['tradingsymbol'],
                        "key": ltp_key
                    }})

                # Build LTP response from tick store (with Kite API fallback)
                ltp_map = {}
                for name, info in needed.items():
                    tok = info["token"] if isinstance(info, dict) else info
                    tick = get_tick(tok)
                    if tick:
                        ltp_map[name] = tick["last_price"]
                    elif isinstance(info, dict) and info.get("ltp_key"):
                        # Tick store empty (market closed?) — try Kite API
                        try:
                            ltp_data = kite.ltp(info["ltp_key"])
                            price = ltp_data.get(info["ltp_key"], {}).get("last_price")
                            if price:
                                ltp_map[name] = price
                        except Exception:
                            pass

                await websocket.send_text(json.dumps(ltp_map))

            except (WebSocketDisconnect, asyncio.CancelledError):
                break
            except Exception as e:
                if 'close' in str(e).lower() or any(c in str(e) for c in ['1001', '1005', '1006', '1012']):
                    break
                logger.error(f"Trades WS error: {e}")

            await wait_for_tick(timeout=1)

    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as e:
        if 'close' in str(e).lower() or any(c in str(e) for c in ['1001', '1005', '1006', '1012']):
            pass
        else:
            logger.error(f"Trades WS error: {e}", exc_info=True)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

# =========================
# WebSocket: Real-time Ticker (KiteTicker)
# =========================
TICKER_INSTRUMENTS = [
    {"key": "NSE:NIFTY 50", "name": "Nifty 50"},
    {"key": "NSE:NIFTY BANK", "name": "Bank Nifty"},
    {"key": "BSE:SENSEX", "name": "Sensex"},
]

@app.websocket("/ws/ticker")
async def ws_ticker(websocket: WebSocket):
    """
    Streams live index prices from KiteTicker tick store — real-time, no polling.
    """
    await websocket.accept()
    try:
        while True:
            result = []
            for token, info in INDEX_TOKENS.items():
                tick = get_tick(token)
                if tick:
                    price = tick.get("last_price")
                    prev = tick.get("ohlc", {}).get("close")
                    if price and prev:
                        change = round(price - prev, 2)
                        change_pct = round((change / prev) * 100, 2)
                    else:
                        change = None
                        change_pct = None
                    result.append({
                        "symbol": info["key"],
                        "name": info["name"],
                        "price": round(price, 2) if price else None,
                        "change": change,
                        "change_pct": change_pct,
                    })
            if result:
                await websocket.send_text(json.dumps(result))
            # Wait for next tick (real-time, no polling delay)
            await wait_for_tick(timeout=2)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception as e:
        if not ('close' in str(e).lower() or any(c in str(e) for c in ['1001', '1005', '1012'])):
            logger.error(f"Ticker WS error: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
  
@app.websocket("/ws/nifty50")
async def ws_nifty50(websocket: WebSocket):

    await websocket.accept()

    try:
        while True:
            movers, sector = fetch_nifty50_movers()

            movers.sort(
                key=lambda x: abs(x["percentChange"]),
                reverse=True
            )

            await websocket.send_text(json.dumps({
                "data": movers,
                "sector": sector
            }))

            await asyncio.sleep(10)

    except WebSocketDisconnect:
        logger.info("Client disconnected from Nifty50 stream")

    except Exception as e:
        logger.error(f"Nifty50 WS error: {e}", exc_info=True)

@app.get("/nifty50-movers")
def nifty50_movers():
    data, sector = fetch_nifty50_movers()

    if not data:
        return {"error":"Failed to fetch market data"}

    data.sort(key=lambda x: abs(x["percentChange"]), reverse=True)

    return {
        "sector": sector,
        "data": data
    }

@app.get("/history")
def get_history(symbol: str):
    import yfinance as yf

    df = yf.download(symbol + ".NS", period="1d", interval="5m")

    return [
        {"time": str(i.time()), "price": float(row["Close"])}
        for i, row in df.iterrows()
    ] 

@app.get("/candles")
def get_candles(symbol: str, interval: str = "5m"):
    import yfinance as yf

    df = yf.download(
        symbol + ".NS",
        period="2d",
        interval=interval
    )

    return [
        {
            "time": int((i + timedelta(hours=5, minutes=30)).timestamp()),
            "open": float(r["Open"]),
            "high": float(r["High"]),
            "low": float(r["Low"]),
            "close": float(r["Close"])
        }
        for i, r in df.iterrows()
    ]    

@app.websocket("/ws/candles/{symbol}/{interval}")
async def ws_candles(websocket: WebSocket, symbol: str, interval: str):
    await websocket.accept()
    try:
        while True:
            candles = get_latest_candle(symbol, interval)  # your logic
            await websocket.send_json(candles)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        print("candle client disconnected")


# =========================
# Trades: Manual Trade Log
# =========================
TRADES_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'trades.json')

def _ensure_trades_file():
    """Create trades file and directory if they don't exist"""
    os.makedirs(os.path.dirname(TRADES_FILE), exist_ok=True)
    if not os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, 'w') as f:
            json.dump([], f)

def _load_trades():
    _ensure_trades_file()
    with open(TRADES_FILE, 'r') as f:
        return json.load(f)

def _save_trades(trades):
    _ensure_trades_file()
    with open(TRADES_FILE, 'w') as f:
        json.dump(trades, f, indent=2)

@app.get("/trades/active")
def get_active_trades():
    """Get all open (bought but not yet sold) trades"""
    trades = _load_trades()
    open_trades = [t for t in trades if t.get('status') == 'open']
    return {"trades": open_trades}

@app.post("/trades/live-ltp")
def get_trades_live_ltp(body: dict = Body(...)):
    """
    Get live LTP for open trade instruments.
    body: { "names": ["NIFTY 25400 CE", "BANKNIFTY 61000 CE"] }
    Returns: { "NIFTY 25400 CE": 128.50, ... }
    """
    names = body.get("names", [])
    result = {}
    for name in names:
        try:
            parts = name.split()
            if len(parts) < 3:
                continue
            prefix = parts[0]                    # "NIFTY"
            strike = float(parts[1])             # 25400
            opt_type = parts[2]                  # "CE" or "PE"
            ltp = _auto_get_option_ltp(prefix, opt_type, strike=strike)
            if ltp is not None:
                result[name] = ltp
        except Exception:
            continue
    return result

@app.get("/trades")
def get_trades(date: str = None):
    """
    Get trades. If date is provided (YYYY-MM-DD), filter by that date.
    Defaults to today (IST).
    """
    trades = _load_trades()
    if date is None:
        # Default to today IST
        date = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d')
    filtered = [t for t in trades if t.get('date') == date]
    # Calculate day P&L
    total_pnl = sum(t.get('pnl', 0) for t in filtered)
    return {
        "date": date,
        "total_pnl": round(total_pnl, 2),
        "trade_count": len(filtered),
        "trades": filtered
    }

@app.post("/trades")
def add_trade(trade: dict = Body(...)):
    """
    Add a new trade. Expected fields:
    - name: str (option name e.g. "NIFTY 25700 CE")
    - lot: int
    - buy_price: float
    - sell_price: float (optional, 0 if still open)
    - buy_time: str (HH:MM IST)
    - sell_time: str (HH:MM IST, optional)
    """
    trades = _load_trades()
    ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)

    buy_price = float(trade.get('buy_price', 0))
    sell_price = float(trade.get('sell_price', 0))
    lot = int(trade.get('lot', 1))
    quantity = int(trade.get('quantity', lot))

    new_trade = {
        "id": int(ist_now.timestamp() * 1000),
        "date": ist_now.strftime('%Y-%m-%d'),
        "name": trade.get('name', ''),
        "lot": lot,
        "quantity": quantity,
        "buy_price": buy_price,
        "sell_price": sell_price,
        "buy_time": trade.get('buy_time') or ist_now.strftime('%H:%M'),
        "sell_time": trade.get('sell_time', ''),
        "pnl": round((sell_price - buy_price) * quantity, 2) if sell_price else 0,
        "status": "closed" if sell_price else "open"
    }
    trades.append(new_trade)
    _save_trades(trades)
    return new_trade

@app.put("/trades/{trade_id}")
def update_trade(trade_id: int, trade: dict = Body(...)):
    """Update a trade (e.g. close it with sell_price and sell_time)"""
    trades = _load_trades()
    for t in trades:
        if t['id'] == trade_id:
            for key, val in trade.items():
                t[key] = val
            # Recalculate P&L
            if t.get('sell_price'):
                qty = int(t.get('quantity', t['lot']))
                t['pnl'] = round((float(t['sell_price']) - float(t['buy_price'])) * qty, 2)
                t['status'] = 'closed'
            _save_trades(trades)
            return t
    return {"error": "Trade not found"}

@app.delete("/trades/{trade_id}")
def delete_trade(trade_id: int):
    """Delete a trade by ID"""
    trades = _load_trades()
    trades = [t for t in trades if t['id'] != trade_id]
    _save_trades(trades)
    return {"status": "deleted"}


# =========================
# Auto-Trader API Endpoints
# =========================
@app.get("/auto-trader/status")
def auto_trader_status():
    """Get auto-trader engine status"""
    return auto_trader.get_status()

@app.post("/auto-trader/start")
async def auto_trader_start():
    """Start the auto-trading engine"""
    if auto_trader.enabled:
        return {"status": "already_running"}
    loop = asyncio.get_running_loop()
    auto_trader.start(loop=loop)
    return {"status": "started", "mode": "paper"}

@app.post("/auto-trader/stop")
async def auto_trader_stop():
    """Stop the auto-trading engine"""
    if not auto_trader.enabled:
        return {"status": "already_stopped"}
    # Close all open positions before stopping
    auto_trader.stop()
    return {"status": "stopped"}

@app.post("/auto-trader/test-mode")
async def auto_trader_test_mode(body: dict = Body(...)):
    """Toggle test mode (bypasses market hours check)"""
    import engine.auto_trader as at_module
    at_module.TEST_MODE = body.get("enabled", False)
    return {"test_mode": at_module.TEST_MODE}