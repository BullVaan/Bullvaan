from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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

# data utils
from utils.yahoo_finance import fetch_history, standardize_ohlcv
import yfinance as yf
import pandas as pd
import numpy as np

app = FastAPI(title="Bullvan Trading API")

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
                avg_vol = df["Volume"].mean()

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
        
        if ts_direction:
            # Rule 1: Trend+Strength agrees (3+) AND Momentum mostly neutral (2+)
            if mom_neutral >= 2:
                consensus = ts_direction
            # Rule 2: Trend+Strength agrees (3+) AND Momentum says opposite (2+)
            elif (ts_direction == "BUY" and mom_sell >= 2) or (ts_direction == "SELL" and mom_buy >= 2):
                consensus = ts_direction
                stop_loss_warning = True
            # Rule 3: Momentum agrees with Trend+Strength
            elif (ts_direction == "BUY" and mom_buy >= 2) or (ts_direction == "SELL" and mom_sell >= 2):
                consensus = ts_direction
            else:
                # Mixed signals
                consensus = ts_direction

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

                await websocket.send_text(json.dumps({
                    "symbol": zerodha_symbol,
                    "expiry": str(nearest_expiry),
                    "atm_strike": strike,
                    "options": options_list,
                    "timestamp": datetime.now().isoformat()
                }))

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