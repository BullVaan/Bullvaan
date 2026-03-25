from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body, Depends
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional
from dotenv import load_dotenv
from kiteconnect import KiteConnect, KiteTicker
from utils.nse_live import fetch_nse_indices
from utils.auth import get_current_user
from utils.trades_db import (save_trade, get_user_trades, get_user_trades_by_date, 
                             get_active_trades, update_trade_sell, delete_trade as db_delete_trade)
from engine import AutoTrader, _invalidate_trades_cache
import engine.auto_trader as auto_trader_module
from utils.auto_trader_db import set_auto_trader_user_id, clear_auto_trader_user_id
from engine.premarket_signals import PremarketSignalEngine

# Load trading rules config
_CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'trading_rules.json')
with open(_CONFIG_FILE, 'r') as f:
    _config = json.load(f)
from engine.premarket_alerts import PremarketAlertManager, AlertSeverity
from utils.nifty50_stocks import get_nifty50_symbols

# Load environment variables
load_dotenv()

# ========== MULTI-SESSION AUTO-TRADER TRACKING ==========
# Each session (user/browser/device) gets its own independent AutoTrader instance
# Format: {session_id: (AutoTrader_instance, user_id, timestamp), ...}
# This allows multiple concurrent traders to run simultaneously
_auto_traders_by_session = {}
_auto_traders_lock = threading.Lock()  # Protect dict during concurrent access

# Get references to load_trades and save_trades
_load_trades = auto_trader_module._load_trades
_save_trades = auto_trader_module._save_trades

# Initialize Zerodha Kite Connect
api_key = os.getenv("API_KEY")
access_token = os.getenv("ACCESS_TOKEN")
kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

# =========================
# KiteTicker: Real-time tick store
import time as _time
import datetime as _dt
# =========================
# Shared dict: instrument_token -> tick data (updated by KiteTicker thread)
_tick_store = {}
# Map instrument_token -> symbol info for reverse lookup
_token_map = {}
# Dashboard-computed ATM options: {"NIFTY": {"atm_strike": 22500, "CE": {"ltp": 150, "token": 123, "tradingsymbol": "..."}, "PE": {...}}, ...}
_dashboard_options = {}
# List of asyncio Events to notify WebSocket consumers on new ticks
_tick_listeners = []
_kws = None

def _on_ticks(ws, ticks):
    """Called by KiteTicker on every tick — runs in Twisted thread"""
    for tick in ticks:
        token = tick["instrument_token"]
        tick["_received_at"] = _time.time()  # when we received the packet

        # ── TRUE freshness: when the last trade ACTUALLY happened on the exchange ──
        # MODE_FULL provides two timestamps:
        #   exchange_timestamp = when exchange SENT this packet (always recent, useless)
        #   last_trade_time    = when last ACTUAL TRADE executed (THIS is real freshness)
        # _received_at is useless — KiteTicker pushes stale last_price every ~1s
        # even if no new trade happened.
        last_trade_time = tick.get("last_trade_time")  # datetime from MODE_FULL
        if last_trade_time:
            if hasattr(last_trade_time, 'timestamp'):
                tick["_last_trade_at"] = last_trade_time.timestamp()
            else:
                tick["_last_trade_at"] = tick["_received_at"]  # fallback
        else:
            # Fallback: Track price changes (MODE_QUOTE/LTP don't have last_trade_time)
            old_tick = _tick_store.get(token)
            if old_tick and old_tick.get("last_price") == tick.get("last_price"):
                # Price unchanged — keep old _last_trade_at (stale)
                tick["_last_trade_at"] = old_tick.get("_last_trade_at", 0)
            else:
                # Price changed — new trade must have happened
                tick["_last_trade_at"] = tick["_received_at"]

        _tick_store[token] = tick
    # Notify all async listeners
    for evt in list(_tick_listeners):
        evt.set()

def _on_connect(ws, response):
    """Called when KiteTicker connects"""
    tokens = list(_token_map.keys())
    if tokens:
        ws.subscribe(tokens)
        ws.set_mode(ws.MODE_FULL, tokens)  # MODE_FULL gives exchange_timestamp for real trade freshness
        logging.getLogger("api.server").info(f"KiteTicker subscribed to {len(tokens)} tokens in MODE_FULL")

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
                _kws.set_mode(_kws.MODE_FULL, new_tokens)
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
from strategies import (
    MovingAverageStrategy, RSIStrategy, MACDStrategy,
    EMACrossoverStrategy, SupertrendStrategy, StochasticStrategy, ADXStrategy
)

# data utils — Zerodha for strategies (replaced Yahoo Finance)
from utils import fetch_zerodha_history, fetch_india_vix_zerodha

# Import Auth routers (login/signup)
from api.login import router as login_router
from api.signup import router as signup_router

app = FastAPI(title="Bullvan Trading API")

# Register auth routers
app.include_router(login_router, prefix="/api", tags=["auth"])
app.include_router(signup_router, prefix="/api", tags=["auth"])

# =========================
# Setup Logging
# =========================
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Suppress verbose library warnings
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
NIFTY50_TOKENS = {}  # Will be populated at startup: {symbol: {token, name}}

@app.on_event("startup")
def startup_init_ticker():
    """Resolve index instrument tokens and NIFTY50 stock tokens, then start KiteTicker"""
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
                # Seed tick store with quote so ticker bar works before first live tick
                q = quote[ltp_key]
                _tick_store[token] = {
                    "instrument_token": token,
                    "last_price": q.get("last_price"),
                    "ohlc": q.get("ohlc", {}),
                    "_received_at": _time.time(),
                    "_last_trade_at": _time.time(),
                }
                logger.info(f"Index {idx['name']} -> token {token}")
            else:
                logger.warning(f"No instrument_token in quote for {ltp_key}: {quote[ltp_key]}")
        except Exception as e:
            logger.warning(f"Could not resolve token for {idx['tradingsymbol']}: {e}")

    # ===== Subscribe NIFTY50 stocks for live data =====
    try:
        instruments = kite.instruments("NSE")
        nifty50_symbols = get_nifty50_symbols(format_type="nse")
        
        for symbol in nifty50_symbols:
            try:
                # Find matching instrument
                inst = next((i for i in instruments if i.get("tradingsymbol") == symbol and i.get("segment") == "NSE"), None)
                if inst:
                    token = inst.get("instrument_token")
                    if token:
                        NIFTY50_TOKENS[symbol] = {"token": token, "name": symbol}
                        subscribe[token] = {"name": symbol, "key": f"NSE:{symbol}"}
                        logger.info(f"NIFTY50 {symbol} -> token {token}")
            except Exception as e:
                logger.warning(f"Could not resolve token for NIFTY50 stock {symbol}: {e}")
        
        logger.info(f"Resolved {len(NIFTY50_TOKENS)} NIFTY50 stock tokens")
    except Exception as e:
        logger.error(f"Error fetching NIFTY50 instruments: {e}")

    if subscribe:
        start_ticker(subscribe)
        logger.info(f"KiteTicker started with {len(subscribe)} tokens (indices + stocks)")


async def _subscribe_all_index_options():
    """Keep _dashboard_options populated for ALL indices so auto-trader can trade any index"""
    await asyncio.sleep(5)
    while True:
        for zerodha_symbol, cfg in SYMBOL_CONFIG.items():
            try:
                spot_token = _get_spot_token(zerodha_symbol)
                if not spot_token:
                    continue
                spot_tick = get_tick(spot_token)
                if not spot_tick or not spot_tick.get("last_price"):
                    continue

                spot = spot_tick["last_price"]
                strike = round(spot / cfg["interval"]) * cfg["interval"]

                expiry_options, _ = get_near_expiry_options(zerodha_symbol)
                if not expiry_options:
                    continue

                for opt_type in ["CE", "PE"]:
                    opt = next((i for i in expiry_options if i['strike'] == strike and i['instrument_type'] == opt_type), None)
                    if not opt:
                        continue
                    tok = opt['instrument_token']
                    if tok not in _tick_store:
                        start_ticker({tok: {"name": opt['tradingsymbol'], "key": f"{cfg['exchange']}:{opt['tradingsymbol']}"}})

                    tick = get_tick(tok)
                    if tick and tick.get("last_price"):
                        if zerodha_symbol not in _dashboard_options:
                            _dashboard_options[zerodha_symbol] = {}
                        _dashboard_options[zerodha_symbol]["atm_strike"] = strike
                        _dashboard_options[zerodha_symbol][opt_type] = {
                            "ltp": tick["last_price"],
                            "token": tok,
                            "_updated_at": tick.get("_last_trade_at", 0),
                        }
            except Exception as e:
                logger.error(f"BG option subscriber error for {zerodha_symbol}: {e}")
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_option_subscriber():
    asyncio.create_task(_subscribe_all_index_options())


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
    """Fetch live India VIX from Zerodha"""
    return fetch_india_vix_zerodha(kite)

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
    # Prevent division by zero
    if avg_volume <= 0 or volume <= 0:
        price_score = min(abs(change_pct), 5) * 10
        return round(price_score)
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

# Cache for NIFTY50 movers to reduce recalculation
_nifty50_movers_cache = {"movers": [], "sector": "Unknown", "timestamp": 0}
NIFTY50_CACHE_TTL = 2  # Cache for 2 seconds

def fetch_nifty50_movers():
    """
    Fetch NIFTY50 movers using live Kite tick data instead of Yahoo Finance.
    Returns real-time prices, volumes, and calculated metrics.
    Uses 2-second cache to reduce recalculation overhead.
    """
    global _nifty50_movers_cache
    
    # Return cached data if fresh
    now = _time.time()
    if _nifty50_movers_cache["timestamp"] and (now - _nifty50_movers_cache["timestamp"]) < NIFTY50_CACHE_TTL:
        return _nifty50_movers_cache["movers"], _nifty50_movers_cache["sector"]
    
    try:
        movers = []
        nifty50_symbols = get_nifty50_symbols(format_type="nse")

        for symbol in nifty50_symbols:
            try:
                # Get instrument token from mapping
                token_info = NIFTY50_TOKENS.get(symbol)
                if not token_info:
                    continue  # Skip silently if no token mapping

                token = token_info.get("token")
                
                # Get latest tick data
                tick = get_tick(token)
                if not tick or not tick.get("last_price"):
                    continue  # Skip silently if no tick data yet

                # Extract data from tick
                current = tick.get("last_price", 0)
                volume = tick.get("volume", 0)
                
                if current <= 0:
                    continue  # Skip invalid price data
                
                # Get OHLC info for calculations
                ohlc = tick.get("ohlc", {})
                prev_close = ohlc.get("close", 0)
                
                # Validate prev close data
                if prev_close <= 0:
                    prev_close = current  # Use current price if prev_close not available
                
                # Calculate percentage change
                change_pct = ((current - prev_close) / prev_close * 100) if prev_close > 0 else 0
                price_change = current - prev_close

                # For volume metrics, use bid-ask volume as proxy
                bid_volume = tick.get("bid_qty", 0)
                ask_volume = tick.get("ask_qty", 0)
                current_volume = (bid_volume + ask_volume) if (bid_volume and ask_volume) else (volume or 1)
                
                # Average volume estimation - use a conservative estimate
                avg_vol = tick.get("average_traded_quantity", current_volume)
                if avg_vol <= 0:
                    avg_vol = current_volume if current_volume > 0 else 1
                
                # Prevent division by zero
                volume_ratio = (current_volume / avg_vol) if (avg_vol and current_volume) else 1.0

                # Calculate momentum score with safety checks
                score = momentum_score(abs(change_pct), current_volume, avg_vol)

                # Prepare mover data
                movers.append({
                    "symbol": symbol,
                    "price": round(float(current), 2),
                    "percentChange": round(float(change_pct), 2),
                    "priceChange": round(float(price_change), 2),
                    "volume": int(current_volume),
                    "avgVolume": int(avg_vol),
                    "volumeRatio": round(volume_ratio, 2),
                    "volumeSignal": volume_label(volume_ratio),
                    "volumeTrend": "→",  # Static for real-time data
                    "sector": SECTOR_MAP.get(symbol, "Other"),
                    "breakout": "NONE",  # Would need candle data
                    "momentum": score,
                    "optionStrike": nearest_strike(current),
                    "lastUpdate": _time.time()
                })

            except Exception as e:
                logger.debug(f"Skipping {symbol}: {e}")
                continue

        # ===== Calculate strongest sector =====
        sector_perf = {}
        for s in movers:
            sector_perf.setdefault(s["sector"], []).append(s["percentChange"])

        strongest_sector = "Unknown"
        if sector_perf:
            strongest_sector = max(
                sector_perf.items(),
                key=lambda x: sum(x[1]) / len(x[1])
            )[0]

        # Update cache
        _nifty50_movers_cache["movers"] = movers
        _nifty50_movers_cache["sector"] = strongest_sector
        _nifty50_movers_cache["timestamp"] = now

        return movers, strongest_sector

    except Exception as e:
        logger.error(f"Nifty50 movers fetch error: {e}", exc_info=True)
        # Return from cache if available, otherwise return empty
        if _nifty50_movers_cache["movers"]:
            return _nifty50_movers_cache["movers"], _nifty50_movers_cache["sector"]
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
_signal_cache = {}  # {symbol: {"result": dict, "timestamp": float}}
SIGNAL_CACHE_TTL = 300  # 5 minutes — matches the 5m candle timeframe; no point recalculating on incomplete candles

@app.get("/signals")
def get_signals(symbol: str = "^NSEI", timeframe: str = "5m", current_user: dict = Depends(get_current_user)):
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
        # Return cached signal if fresh (avoids hammering Zerodha API)
        cache_key = f"{symbol}_{timeframe}"
        cached = _signal_cache.get(cache_key)
        if cached and (_time.time() - cached["timestamp"]) < SIGNAL_CACHE_TTL:
            return cached["result"]

        # fetch market data from Zerodha
        df = fetch_zerodha_history(
            kite, symbol, interval="5m", days=5,
            get_spot_token_fn=_get_spot_token
        )
        if df is None or df.empty:
            return {"error": f"No data available for {symbol}"}

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

        # ═══════════════════════════════════════════════════════
        # CATEGORY-LEVEL CONSENSUS
        # Each category decides its own direction first,
        # then overall signal needs 2+ categories agreeing.
        # ═══════════════════════════════════════════════════════
        
        trend_signals = [s["signal"] for s in signals_by_role.get("Trend", [])]
        strength_signals = [s["signal"] for s in signals_by_role.get("Strength", [])]
        momentum_signals = [s["signal"] for s in signals_by_role.get("Momentum", [])]

        def category_consensus(signals):
            """
            2 indicators: both must agree, BUY+NEUTRAL=BUY, conflict=NEUTRAL
            3 indicators: 2+ neutral=NEUTRAL, any conflict=NEUTRAL, else active direction
            """
            if not signals:
                return "NEUTRAL"
            buy_c = signals.count("BUY")
            sell_c = signals.count("SELL")
            neutral_c = signals.count("NEUTRAL")
            # Conflict: BUY and SELL both present
            if buy_c > 0 and sell_c > 0:
                return "NEUTRAL"
            # For 3+ indicators: 2+ neutral = NEUTRAL
            if len(signals) >= 3 and neutral_c >= 2:
                return "NEUTRAL"
            if buy_c > 0:
                return "BUY"
            if sell_c > 0:
                return "SELL"
            return "NEUTRAL"

        trend_dir = category_consensus(trend_signals)
        momentum_dir = category_consensus(momentum_signals)
        strength_dir = category_consensus(strength_signals)

        # ═══════════════════════════════════════════════════════
        # OVERALL CONSENSUS: Trend & Strength must agree
        # Momentum must be NEUTRAL or same direction.
        # Anything else → NEUTRAL.
        # ═══════════════════════════════════════════════════════

        consensus = "NEUTRAL"
        signal_strength = "NONE"

        # Trend and Strength must both have the same active direction
        if trend_dir in ("BUY", "SELL") and trend_dir == strength_dir:
            # Momentum must agree or stay neutral
            if momentum_dir == trend_dir:
                # All 3 agree → STRONG
                consensus = trend_dir
                signal_strength = "STRONG"
            elif momentum_dir == "NEUTRAL":
                # Trend + Strength agree, Momentum neutral → MEDIUM
                consensus = trend_dir
                signal_strength = "MEDIUM"
            # else: Momentum opposes → NEUTRAL

        result = {
            "symbol": symbol,
            "service": SYMBOL_MAP.get(symbol, symbol),
            "timeframe": timeframe,
            "timeframe_info": TIMEFRAME_CONFIG[timeframe],
            "price": round(current_price, 2),
            "india_vix": india_vix,
            "atr": atr,
            "consensus": consensus,
            "signal_strength": signal_strength,
            "buy_votes": buy,
            "sell_votes": sell,
            "neutral_votes": neutral,
            "total_strategies": len(strategies),
            "signals": all_signals,
            "signals_by_role": signals_by_role
        }
        _signal_cache[cache_key] = {"result": result, "timestamp": _time.time()}
        return result

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
# Zerodha Options Chain - Near Expiry
# =========================
@app.get("/options")
def get_options(symbol: str = "NIFTY", strike: int = None, current_user: dict = Depends(get_current_user)):
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
    """HTTP fallback — returns latest NSE index prices from KiteTicker"""
    try:
        # Pass live tick store and index tokens to fetch function
        data = fetch_nse_indices(_tick_store, INDEX_TOKENS)
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
    Get option LTP for auto-trader.
    For NEW trades (strike=None): reads from dashboard's live ATM options — same price you see on screen.
    For EXISTING trades (strike given): uses tick store then kite.quote() API for that specific instrument.

    IMPORTANT: For entries (strike=None), we NEVER use kite.quote() API.
    kite.quote() returns last_traded_price which can be seconds old — enough for
    options to move 30-40% in a volatile market. Only live tick data is trusted for entries.
    """
    try:
        zerodha_symbol = prefix  # already "NIFTY", "BANKNIFTY", etc.
        cfg = SYMBOL_CONFIG.get(zerodha_symbol, SYMBOL_CONFIG["NIFTY"])
        is_entry = (strike is None)  # True if this is a NEW entry, False if monitoring existing trade

        # ── NEW TRADE: Use dashboard's live ATM price (must be fresh) ──
        if strike is None:
            dash = _dashboard_options.get(zerodha_symbol)
            if dash and dash.get(opt_type) and dash[opt_type].get("ltp"):
                updated_at = dash[opt_type].get("_updated_at", 0)
                age = _time.time() - updated_at
                price = dash[opt_type]["ltp"]
                if age <= 5:  # only trust if last ACTUAL TRADE on exchange was < 5 seconds ago
                    logger.info(f"Auto-trader LTP SOURCE=DASHBOARD_CACHE: {zerodha_symbol} ATM {opt_type} = ₹{price} (trade_age={age:.1f}s) → FRESH")
                    return price
                else:
                    logger.warning(f"Auto-trader LTP SOURCE=DASHBOARD_CACHE: {zerodha_symbol} {opt_type} = ₹{price} (trade_age={age:.1f}s) → STALE, falling back")
            else:
                # Dashboard not populated yet — fall back
                logger.warning(f"Auto-trader LTP SOURCE=DASHBOARD_CACHE: {zerodha_symbol} {opt_type} → NO DATA, falling back")

        # ── EXISTING TRADE or FALLBACK: specific strike ──
        expiry_options, _ = get_near_expiry_options(zerodha_symbol)

        if strike is None:
            # Calculate ATM from spot (fallback when dashboard not connected)
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
        ltp_key = f"{cfg['exchange']}:{opt['tradingsymbol']}"

        # 1st priority: KiteTicker live tick — must have RECENT ACTUAL TRADE on exchange
        tick = get_tick(tok)
        if tick and tick.get("_last_trade_at") and tick.get("last_price"):
            trade_age = _time.time() - tick["_last_trade_at"]
            # Entries: strict 5s. Exits: allow 10s (missing SL is worse than slightly stale price)
            max_age = 5 if is_entry else 10
            if trade_age <= max_age:
                logger.info(f"Auto-trader LTP SOURCE=TICK_STORE: {opt['tradingsymbol']} = ₹{tick['last_price']} (trade_age={trade_age:.1f}s, max={max_age}s) → FRESH")
                return tick["last_price"]
            else:
                logger.warning(f"Auto-trader LTP SOURCE=TICK_STORE: {opt['tradingsymbol']} = ₹{tick['last_price']} (trade_age={trade_age:.1f}s, max={max_age}s) → STALE")

        # ── ENTRY: STOP HERE — never use API for entries ──
        # kite.quote() returns last_traded_price which can be from seconds ago.
        # In volatile markets, options can move 30-40% in 10-30 seconds.
        # Subscribe to ticker so we get fresh data on next cycle, then skip.
        if is_entry:
            if tok not in _tick_store:
                start_ticker({tok: {"name": opt['tradingsymbol'], "key": ltp_key}})
                logger.info(f"Auto-trader ENTRY SKIP: {opt['tradingsymbol']} — no live tick, subscribed for next cycle")
            else:
                logger.info(f"Auto-trader ENTRY SKIP: {opt['tradingsymbol']} — tick stale, waiting for fresh tick")
            return None

        # ── EXIT ONLY: Kite API quote (last resort for monitoring open positions) ──
        # For exits, slightly stale price is acceptable — missing an exit is worse.
        # Window tightened to 10 seconds (was 30s).
        try:
            quote_data = kite.quote(ltp_key)
            quote = quote_data.get(ltp_key, {})
            fresh_price = quote.get("last_price")
            last_trade_time = quote.get("last_trade_time")  # datetime object from Zerodha

            if fresh_price and fresh_price > 0:
                if last_trade_time:
                    now_ist = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=5, minutes=30)))
                    if hasattr(last_trade_time, 'tzinfo') and last_trade_time.tzinfo is None:
                        last_trade_time = last_trade_time.replace(tzinfo=_dt.timezone(_dt.timedelta(hours=5, minutes=30)))
                    trade_age = (now_ist - last_trade_time).total_seconds()

                    if trade_age <= 10:
                        logger.info(f"Auto-trader LTP SOURCE=KITE_QUOTE (EXIT): {opt['tradingsymbol']} = ₹{fresh_price} (last_trade={trade_age:.0f}s ago) → FRESH")
                        if tok not in _tick_store:
                            start_ticker({tok: {"name": opt['tradingsymbol'], "key": ltp_key}})
                        return fresh_price
                    else:
                        logger.warning(f"Auto-trader LTP SOURCE=KITE_QUOTE (EXIT): {opt['tradingsymbol']} = ₹{fresh_price} (last_trade={trade_age:.0f}s ago) → STALE, skipping")
                else:
                    # No last_trade_time — NEVER blindly trust. Skip.
                    logger.warning(f"Auto-trader LTP SOURCE=KITE_QUOTE (EXIT): {opt['tradingsymbol']} = ₹{fresh_price} (no trade_time) → UNTRUSTED, skipping")
        except Exception as e:
            logger.warning(f"Kite API quote failed for {ltp_key}: {e}")

        # Neither available — ensure subscribed for next tick
        if tok not in _tick_store:
            start_ticker({tok: {
                "name": opt['tradingsymbol'],
                "key": ltp_key
            }})
        return None
    except Exception as e:
        logger.error(f"Auto-trader LTP fetch error: {e}")
        return None


def _auto_get_entry_snapshot(prefix, opt_type):
    """
    Atomic snapshot: reads ATM strike + LTP from the SAME _dashboard_options state.
    Returns (atm_strike, ltp) or (None, None) if stale/unavailable.
    Prevents race condition where ATM shifts between reading price and strike.
    """
    dash = _dashboard_options.get(prefix)
    if not dash:
        logger.warning(f"Entry snapshot: no dashboard data for {prefix}")
        return None, None

    atm_strike = dash.get("atm_strike")
    opt_data = dash.get(opt_type)
    if not atm_strike or not opt_data or not opt_data.get("ltp"):
        logger.warning(f"Entry snapshot: incomplete data for {prefix} {opt_type}")
        return None, None

    # Freshness check — uses ACTUAL TRADE TIME on exchange, not packet delivery time
    updated_at = opt_data.get("_updated_at", 0)
    age = _time.time() - updated_at
    ltp = opt_data["ltp"]
    if age > 15:
        logger.warning(f"Entry snapshot STALE: {prefix} {atm_strike} {opt_type} = ₹{ltp} (trade_age={age:.1f}s) → SKIPPED, waiting for fresh tick")
        return None, None

    logger.info(f"Entry snapshot FRESH: {prefix} {atm_strike} {opt_type} = ₹{ltp} (trade_age={age:.1f}s) → USING THIS PRICE")
    return atm_strike, ltp

# Initialize auto-trader (singleton)
auto_trader = AutoTrader(
    get_signal_fn=_auto_get_signal,
    get_option_ltp_fn=_auto_get_option_ltp,
    get_entry_snapshot_fn=_auto_get_entry_snapshot,
    kite=kite,  # Pass Kite connection for real trading
)

# Initialize premarket signal engine
premarket_engine = PremarketSignalEngine(kite=kite)

# Initialize premarket alert manager
premarket_alerts = PremarketAlertManager()

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
                            subscribe[tok] = {"name": opt['tradingsymbol'], "key": f"{cfg['exchange']}:{opt['tradingsymbol']}"
                        }

                    if subscribe:
                        start_ticker(subscribe)
                        logger.info(f"Subscribed {len(subscribe)} option tokens for {zerodha_symbol} strike {strike}")

                # ── Update shared dashboard options store for auto-trader ──
                for tok, info in option_tokens.items():
                    if info["label"] in ("atm_ce", "atm_pe"):
                        tick = get_tick(tok)
                        opt_type = info["type"]  # CE or PE
                        if zerodha_symbol not in _dashboard_options:
                            _dashboard_options[zerodha_symbol] = {}
                        _dashboard_options[zerodha_symbol]["atm_strike"] = strike
                        # Use the tick's ACTUAL TRADE TIME on exchange (from MODE_FULL)
                        last_trade_at = tick.get("_last_trade_at", 0) if tick else 0
                        _dashboard_options[zerodha_symbol][opt_type] = {
                            "ltp": tick["last_price"] if tick and tick.get("last_price") else None,
                            "token": tok,
                            "_updated_at": last_trade_at,  # when last ACTUAL TRADE happened on the exchange
                        }

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
def get_history(symbol: str, current_user: dict = Depends(get_current_user)):
    """Get intraday price history for a stock using Kite API"""
    import pandas as pd
    try:
        stock_symbol = symbol.upper()
        stock_token = NIFTY50_TOKENS.get(stock_symbol)
        
        if not stock_token:
            # Try to fetch from NSE instruments if not in pre-mapped list
            instruments = kite.instruments("NSE")
            inst = next((i for i in instruments if i.get("tradingsymbol") == stock_symbol and i.get("segment") == "NSE"), None)
            if not inst:
                return {"error": f"Stock {stock_symbol} not found"}
            token = inst.get("instrument_token")
        else:
            token = stock_token.get("token")
        
        if not token:
            return {"error": "Invalid stock token"}
        
        # Fetch intraday data (today's 5-minute bars)
        to_date = datetime.now()
        from_date = to_date - timedelta(hours=2)
        
        candles = kite.historical_data(token, from_date, to_date, "5minute")
        
        return [
            {
                "time": int(pd.Timestamp(c["date"]).timestamp()),
                "price": float(c["close"]),
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "volume": int(c.get("volume", 0))
            }
            for c in candles
        ]
    except Exception as e:
        logger.error(f"Error fetching history for {symbol}: {e}")
        return {"error": str(e)}


@app.get("/candles")
def get_candles(symbol: str, interval: str = "5m", current_user: dict = Depends(get_current_user)):
    """
    Return OHLC candles for indices (NIFTY, BANKNIFTY, SENSEX) and stocks using Zerodha API.
    All data sourced from Kite API for consistency and reliability. Supports 1, 5, 15 minute intervals.
    During market hours, includes TODAY's partial candles. After hours, includes yesterday's closed candles.
    """
    import logging
    from datetime import datetime, timedelta, timezone
    import pandas as pd
    try:
        # IST timezone (Kite API expects IST, not UTC)
        IST = timezone(timedelta(hours=5, minutes=30))
        
        zerodha_indices = ["NIFTY", "BANKNIFTY", "SENSEX"]
        interval_map = {"1m": "minute", "5m": "5minute", "15m": "15minute"}
        # Accept both "1m" and "1minute" etc.
        interval_key = interval.lower().replace("minute", "m")
        if interval_key not in ["1m", "5m", "15m"]:
            return {"error": "Supported intervals: 1m, 5m, 15m"}
        kite_interval = interval_map[interval_key]
        symbol_up = symbol.upper()
        
        # Use IST for all date calculations (Kite API expects IST)
        now_ist = datetime.now(IST)
        
        if symbol_up in zerodha_indices:
            cfg = SYMBOL_CONFIG.get(symbol_up, SYMBOL_CONFIG["NIFTY"])
            spot_key = cfg["spot"]
            # Find instrument_token for index
            token = _get_spot_token(symbol_up)
            if not token:
                return {"error": f"Instrument token not found for {symbol_up}"}
            
            to_date = now_ist
            # Fetch last 3 days of candles + today's live candles
            from_date = now_ist - timedelta(days=3)
            
            candles = kite.historical_data(token, from_date, to_date, kite_interval)
            # Format for frontend
            out = []
            for c in candles:
                # Zerodha returns time in UTC
                ts = int(pd.Timestamp(c["date"]).timestamp())
                out.append({
                    "time": ts,
                    "open": float(c["open"]),
                    "high": float(c["high"]),
                    "low": float(c["low"]),
                    "close": float(c["close"]),
                    "volume": int(c.get("volume", 0))
                })
            return out
        else:
            # For stocks, use Kite historical data
            try:
                stock_symbol = symbol.upper()
                stock_token = NIFTY50_TOKENS.get(stock_symbol)
                
                if not stock_token:
                    # Try to fetch from NSE instruments if not in pre-mapped list
                    instruments = kite.instruments("NSE")
                    inst = next((i for i in instruments if i.get("tradingsymbol") == stock_symbol and i.get("segment") == "NSE"), None)
                    if not inst:
                        logging.warning(f"Stock {stock_symbol} not found in NSE instruments")
                        return []
                    token = inst.get("instrument_token")
                else:
                    token = stock_token.get("token")
                
                if not token:
                    return []
                
                # Fetch historical data from Kite using requested interval (IST for Kite API)
                to_date = now_ist
                # Fetch last 3 days of candles + today's live candles
                from_date = now_ist - timedelta(days=3)
                
                candles = kite.historical_data(token, from_date, to_date, kite_interval)
                
                if not candles:
                    logging.warning(f"No candle data from Kite for {symbol}")
                    return []
                
                # Format for frontend
                out = []
                for c in candles:
                    ts = int(pd.Timestamp(c["date"]).timestamp())
                    out.append({
                        "time": ts,
                        "open": float(c["open"]),
                        "high": float(c["high"]),
                        "low": float(c["low"]),
                        "close": float(c["close"]),
                        "volume": int(c.get("volume", 0))
                    })
                
                return out
                
            except Exception as e:
                logging.error(f"Error fetching stock candles from Kite for {symbol}: {e}")
                return []
    except Exception as e:
        logging.error(f"Error fetching candles for {symbol}: {e}")
        return {"error": str(e)}


# --- Live Candle Aggregator ---
from collections import defaultdict, deque

# { (symbol, interval): deque([candle_dict, ...], maxlen=500) }
_live_candles = defaultdict(lambda: deque(maxlen=500))
_last_candle_time = {}  # (symbol, interval): last_candle_epoch

def _aggregate_tick_to_candle(symbol, tick, interval='1m'):
    """Aggregate a tick into the current candle for symbol/interval."""
    from datetime import datetime, timezone
    # Only for indices
    if symbol not in ["NIFTY", "BANKNIFTY", "SENSEX"]:
        return
    # Get current time rounded to interval
    now = datetime.now(timezone.utc)
    if interval == '1m':
        candle_time = now.replace(second=0, microsecond=0)
    elif interval == '5m':
        minute = (now.minute // 5) * 5
        candle_time = now.replace(minute=minute, second=0, microsecond=0)
    elif interval == '15m':
        minute = (now.minute // 15) * 15
        candle_time = now.replace(minute=minute, second=0, microsecond=0)
    else:
        return
    ts = int(candle_time.timestamp())
    key = (symbol, interval)
    price = tick.get('last_price') or tick.get('close')
    if not price:
        return
    # If new candle, append
    if _last_candle_time.get(key) != ts:
        _live_candles[key].append({
            'time': ts,
            'open': price,
            'high': price,
            'low': price,
            'close': price
        })
        _last_candle_time[key] = ts
    else:
        # Update current candle
        c = _live_candles[key][-1]
        c['close'] = price
        c['high'] = max(c['high'], price)
        c['low'] = min(c['low'], price)

# Patch _on_ticks to aggregate live candles
_orig_on_ticks = _on_ticks
def _on_ticks(ws, ticks):
    _orig_on_ticks(ws, ticks)
    for tick in ticks:
        token = tick.get('instrument_token')
        # Map token to symbol
        for sym, cfg in SYMBOL_CONFIG.items():
            spot_key = cfg['spot']
            for t, info in INDEX_TOKENS.items():
                if t == token and info['key'] == spot_key:
                    # Aggregate for all intervals
                    for interval in ['1m', '5m', '15m']:
                        _aggregate_tick_to_candle(sym, tick, interval)


@app.websocket("/ws/candles/{symbol}/{interval}")
async def ws_candles(websocket: WebSocket, symbol: str, interval: str):
    await websocket.accept()
    try:
        symbol = symbol.upper()
        interval = interval.lower()
        key = (symbol, interval)
        from fastapi.encoders import jsonable_encoder
        import logging
        from datetime import datetime, timedelta, timezone
        
        while True:
            candles = list(_live_candles[key])
            
            # Fallback: if no live candles, fetch historical
            if not candles:
                try:
                    from datetime import datetime, timedelta
                    import pandas as pd
                    interval_map = {"1m": "minute", "5m": "5minute", "15m": "15minute"}
                    kite_interval = interval_map.get(interval, "5minute")
                    token = _get_spot_token(symbol)
                    
                    # Check if market is open (9:15 AM - 3:30 PM IST)
                    utc_now = datetime.utcnow()
                    ist_now = utc_now + timedelta(hours=5, minutes=30)
                    ist_hour = ist_now.hour
                    ist_minute = ist_now.minute
                    is_market_open = (9 <= ist_hour < 15) or (ist_hour == 15 and ist_minute <= 30)
                    
                    if token:
                        # If market is open, fetch from today morning; otherwise fetch last 2 days
                        to_date = datetime.now()
                        if is_market_open:
                            # Fetch from today's market open (9:15) to now
                            from_date = to_date.replace(hour=9, minute=15, second=0, microsecond=0)
                        else:
                            # Market closed, fetch last 2 days
                            from_date = to_date - timedelta(days=2)
                        
                        hist = kite.historical_data(token, from_date, to_date, kite_interval)
                        candles = [
                            {
                                "time": int(pd.Timestamp(c["date"]).timestamp()),
                                "open": float(c["open"]),
                                "high": float(c["high"]),
                                "low": float(c["low"]),
                                "close": float(c["close"])
                            }
                            for c in hist
                        ]
                        
                        if is_market_open and not candles:
                            logging.info(f"No historical candles yet for {symbol} during market hours (too early)")
                except Exception as e:
                    logging.error(f"WS fallback candle error: {e}")
            
            await websocket.send_json(jsonable_encoder(candles))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        print("candle client disconnected")

@app.get("/trades/active")
def get_active_trades_endpoint(date: str = None, current_user: dict = Depends(get_current_user)):
    """Get trades for a specific date (or today if not provided). Shows both open and closed trades.
    Uses database backend for scalability.
    """
    try:
        user_id = current_user.get('user_id')
        
        if date is None:
            ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
            date = ist_now.strftime('%Y-%m-%d')
        
        # Get active trades from database
        result = get_active_trades(user_id, date)
        return result
    except Exception as e:
        logger.error(f"Error in get_active_trades: {e}", exc_info=True)
        return {"error": str(e)}

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
def get_trades_endpoint(date: str = None, current_user: dict = Depends(get_current_user)):
    """
    Get trades from database. If date is provided (YYYY-MM-DD), filter by that date.
    Defaults to today (IST).
    """
    try:
        user_id = current_user.get('user_id')
        
        if date is None:
            # Default to today IST
            date = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime('%Y-%m-%d')
        
        # Get trades from database
        result = get_user_trades_by_date(user_id, date)
        return result
    except Exception as e:
        logger.error(f"Error in get_trades: {e}", exc_info=True)
        return {"error": str(e)}

@app.post("/trades")
def add_trade(trade: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """
    Add a new trade to database. Expected fields:
    - name: str (option name e.g. "NIFTY 25700 CE")
    - lot: int
    - buy_price: float
    - sell_price: float (optional, 0 if still open)
    - buy_time: str (HH:MM IST)
    - sell_time: str (HH:MM IST, optional)
    
    If in REAL mode, places actual Kite order
    """
    try:
        ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        user_id = current_user.get('user_id')

        buy_price = float(trade.get('buy_price', 0))
        sell_price = float(trade.get('sell_price', 0))
        lot = int(trade.get('lot', 1))
        quantity = int(trade.get('quantity', lot * 65))  # Default 65 qty per lot for options
        option_name = trade.get('name', '')

        new_trade = {
            "id": str(int(ist_now.timestamp() * 1000)),
            "user_id": user_id,
            "date": ist_now.strftime('%Y-%m-%d'),
            "name": option_name,
            "lot": lot,
            "quantity": quantity,
            "buy_price": buy_price,
            "sell_price": sell_price,
            "buy_time": trade.get('buy_time') or ist_now.strftime('%H:%M'),
            "sell_time": trade.get('sell_time', ''),
            "pnl": round((sell_price - buy_price) * quantity, 2) if sell_price else 0,
            "status": "closed" if sell_price else "open",
            "auto": False,
            "mode": auto_trader.trading_mode
        }

        # Real trading: place BUY order via Kite
        if auto_trader.trading_mode == "real" and auto_trader.kite and not sell_price:
            try:
                parts = option_name.split()
                if len(parts) >= 3:
                    prefix = parts[0]
                    strike = float(parts[1])
                    opt_type = parts[2]
                    
                    tradingsymbol = auto_trader._get_option_tradingsymbol(prefix, strike, opt_type)
                    if tradingsymbol:
                        signal_strength = trade.get('signal_strength', 'STRONG')
                        
                        if prefix in _config.get('signal_rules', {}) and signal_strength in _config['signal_rules'][prefix]:
                            rule = _config['signal_rules'][prefix][signal_strength]
                        elif "NIFTY" in _config.get('signal_rules', {}) and signal_strength in _config['signal_rules']["NIFTY"]:
                            rule = _config['signal_rules']["NIFTY"][signal_strength]
                        else:
                            rule = {"target_pts": 20, "sl_pts": 25}
                        
                        sl_pts = rule.get('sl_pts', 25)
                        tp_pts = rule.get('target_pts', 20)
                        
                        order_id = auto_trader.kite.place_order(
                            variety=auto_trader.kite.VARIETY_BO,
                            exchange="NFO" if prefix != "SENSEX" else "BFO",
                            tradingsymbol=tradingsymbol,
                            transaction_type=auto_trader.kite.TRANSACTION_TYPE_BUY,
                            quantity=quantity,
                            order_type=auto_trader.kite.ORDER_TYPE_MARKET,
                            product=auto_trader.kite.PRODUCT_BO,
                            stoploss=sl_pts,
                            squareoff=tp_pts,
                            trailing_stoploss=0,
                            tag=f"manual_buy_{new_trade['id']}"
                        )
                        
                        new_trade["order_id"] = order_id
                        new_trade["kite_tradingsymbol"] = tradingsymbol
                        new_trade["is_bo_trade"] = True
                        logger.info(f"MANUAL REAL BUY (BO): {option_name} | {quantity}qty | ₹{buy_price} | OrderID={order_id}")
                    else:
                        logger.error(f"Could not get tradingsymbol for {option_name}")
                        new_trade["error"] = "Could not resolve trading symbol"
            except Exception as e:
                logger.error(f"Failed to place manual real buy order: {e}", exc_info=True)
                new_trade["error"] = str(e)

        # Save to database
        saved_trade = save_trade(new_trade)
        _invalidate_trades_cache()
        return saved_trade
    except Exception as e:
        logger.error(f"Error in add_trade: {e}", exc_info=True)
        return {"error": str(e)}

@app.put("/trades/{trade_id}")
def update_trade(trade_id: str, trade: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Update a trade (e.g. close it with sell_price and sell_time)
    
    If in REAL mode and closing a trade, places actual Kite sell order
    """
    try:
        user_id = current_user.get('user_id')
        
        # Check if this is a SELL action (close trade) - get existing trade first
        from utils.trades_db import get_trade
        existing_trade = get_trade(trade_id)
        if not existing_trade:
            return {"error": "Trade not found"}
        
        # Verify user ownership
        if existing_trade.get('user_id') != user_id:
            return {"error": "Unauthorized"}
        
        new_sell_price = trade.get('sell_price')
        is_closing = new_sell_price and not existing_trade.get('sell_price')
        
        # Real trading: place SELL order via Kite before updating
        if auto_trader.trading_mode == "real" and auto_trader.kite and is_closing:
            try:
                tradingsymbol = existing_trade.get("kite_tradingsymbol")
                if tradingsymbol:
                    qty = int(existing_trade.get('quantity', existing_trade.get('lot', 1)))
                    exchange = "NFO" if "SENSEX" not in tradingsymbol else "BFO"
                    
                    sell_order_id = auto_trader.kite.place_order(
                        variety=auto_trader.kite.VARIETY_REGULAR,
                        exchange=exchange,
                        tradingsymbol=tradingsymbol,
                        transaction_type=auto_trader.kite.TRANSACTION_TYPE_SELL,
                        quantity=qty,
                        order_type=auto_trader.kite.ORDER_TYPE_MARKET,
                        product=auto_trader.kite.PRODUCT_MIS,
                        tag=f"manual_sell_{trade_id}"
                    )
                    
                    trade["sell_order_id"] = sell_order_id
                    logger.info(f"MANUAL REAL SELL: {existing_trade['name']} | {qty}qty | ₹{new_sell_price} | OrderID={sell_order_id}")
                else:
                    logger.warning(f"No tradingsymbol found for manual sell of trade {trade_id}")
            except Exception as e:
                logger.error(f"Failed to place manual real sell order: {e}", exc_info=True)
                trade["sell_error"] = str(e)
        
        # Update trade in database
        updated_trade = update_trade_sell(trade_id, user_id, 
                                         trade.get('sell_price', existing_trade.get('sell_price')),
                                         trade.get('sell_time', existing_trade.get('sell_time')))
        _invalidate_trades_cache()
        return updated_trade
    except Exception as e:
        logger.error(f"Error in update_trade: {e}", exc_info=True)
        return {"error": str(e)}

@app.delete("/trades/{trade_id}")
def delete_trade_endpoint(trade_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a trade by ID from database"""
    try:
        user_id = current_user.get('user_id')
        
        # Delete from database with user verification
        result = db_delete_trade(trade_id, user_id)
        if result.get('error'):
            return result
        
        _invalidate_trades_cache()
        return {"status": "deleted"}
    except Exception as e:
        logger.error(f"Error in delete_trade: {e}", exc_info=True)
        return {"error": str(e)}


# =========================
# Auto-Trader API Endpoints
# =========================
@app.get("/auto-trader/status")
def auto_trader_status(current_user: dict = Depends(get_current_user)):
    """Get auto-trader engine status for this session
    
    Returns status for THIS session's trader specifically.
    """
    user_id = current_user.get('user_id')
    session_id = current_user.get('session_id')
    
    with _auto_traders_lock:
        # Check if this session has a running trader
        if session_id in _auto_traders_by_session:
            trader, stored_user_id, ts = _auto_traders_by_session[session_id]
            if stored_user_id == user_id:
                # Get status from this session's trader
                status = trader.get_status()
                status['enabled_for_session'] = trader.enabled
                status['session_id'] = session_id
                status['user_id'] = user_id
                status['active_sessions'] = len(_auto_traders_by_session)
                return status
        
        # No trader running for this session
        return {
            "enabled": False,
            "running": False,
            "enabled_for_session": False,
            "session_id": session_id,
            "user_id": user_id,
            "active_sessions": len(_auto_traders_by_session),
            "open_positions": 0,
            "daily_pnl": 0.0
        }

@app.post("/auto-trader/start")
async def auto_trader_start(current_user: dict = Depends(get_current_user)):
    """Start the auto-trading engine for this session
    
    Each session (browser tab/device) gets independent trader instance.
    Multiple sessions can run simultaneously.
    """
    logger = logging.getLogger("api.server")
    user_id = current_user.get('user_id')
    session_id = current_user.get('session_id')
    
    try:
        with _auto_traders_lock:
            # Check if this session already has a running auto-trader
            if session_id in _auto_traders_by_session:
                existing_trader, existing_uid, ts = _auto_traders_by_session[session_id]
                if existing_trader.enabled:
                    return {"status": "already_running_for_session", "session_id": session_id, "user_id": user_id}
            
            # Create new AutoTrader instance for this session
            logger.info(f"Creating auto-trader instance for session {session_id} (user {user_id})")
            
            # Create fresh trader with required callback functions and user context
            new_trader = AutoTrader(
                get_signal_fn=auto_trader.get_signal,
                get_option_ltp_fn=auto_trader.get_option_ltp,
                get_entry_snapshot_fn=auto_trader.get_entry_snapshot,
                kite=auto_trader.kite,
                user_id=user_id  # Pass user_id for multi-session support
            )
            
            # Store this session's trader
            import time
            _auto_traders_by_session[session_id] = (new_trader, user_id, time.time())
            
            # Set user context for database operations (trades will be tagged with user_id)
            set_auto_trader_user_id(user_id)
            
            # Start the trader
            loop = asyncio.get_running_loop()
            new_trader.start(loop=loop)
            logger.info(f"Auto-trader started for session {session_id} (user {user_id})")
            
            return {
                "status": "started",
                "session_id": session_id,
                "user_id": user_id,
                "mode": "paper",
                "active_sessions": len(_auto_traders_by_session)
            }
    except Exception as e:
        logger.error(f"Error starting auto-trader for session {session_id}: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}

@app.post("/auto-trader/stop")
async def auto_trader_stop(current_user: dict = Depends(get_current_user)):
    """Stop the auto-trading engine for this session
    
    Only stops the trader for THIS session.
    Other sessions' traders continue running independently.
    """
    logger = logging.getLogger("api.server")
    user_id = current_user.get('user_id')
    session_id = current_user.get('session_id')
    
    try:
        with _auto_traders_lock:
            # Check if this session has a running trader
            if session_id not in _auto_traders_by_session:
                return {"status": "not_running_for_session", "session_id": session_id}
            
            trader, stored_user_id, ts = _auto_traders_by_session[session_id]
            
            # Verify the user matches (security check)
            if stored_user_id != user_id:
                logger.warning(f"User {user_id} tried to stop trader for different user {stored_user_id}")
                return {"status": "error", "detail": "Session not owned by this user"}
            
            # Stop only this session's trader
            if trader.enabled:
                trader.stop()
                logger.info(f"Auto-trader stopped for session {session_id}")
            
            # Remove from tracking
            del _auto_traders_by_session[session_id]
            clear_auto_trader_user_id()  # clear user context
            
            return {
                "status": "stopped",
                "session_id": session_id,
                "user_id": user_id,
                "active_sessions": len(_auto_traders_by_session)
            }
    except Exception as e:
        logger.error(f"Error stopping auto-trader for session {session_id}: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}

@app.post("/auto-trader/test-mode")
async def auto_trader_test_mode(body: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Toggle test mode (bypasses market hours check)"""
    import engine.auto_trader as at_module
    at_module.TEST_MODE = body.get("enabled", False)
    return {"test_mode": at_module.TEST_MODE}


@app.post("/auto-trader/trading-mode")
async def auto_trader_set_mode(body: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Switch trading mode between paper and real
    
    Request body: {"mode": "paper" | "real"}
    
    Returns:
    - status: "ok" or "error"
    - trading_mode: current mode after the request
    - account_balance: available balance (real mode only)
    """
    try:
        mode = body.get("mode", "paper")
        result = auto_trader.set_trading_mode(mode)
        return result
    except Exception as e:
        logger.error(f"Error in trading mode switch: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Internal server error: {str(e)}",
            "trading_mode": auto_trader.trading_mode
        }


@app.get("/auto-trader/account-balance")
def auto_trader_account_balance(current_user: dict = Depends(get_current_user)):
    """Get real account balance (Kite API)
    
    Returns:
    - balance: available cash margin (None if not in real mode)
    - trading_mode: current trading mode
    """
    if auto_trader.trading_mode != "real":
        return {
            "balance": None,
            "trading_mode": auto_trader.trading_mode,
            "message": f"Not in real mode. Current mode: {auto_trader.trading_mode}"
        }
    
    balance = auto_trader._get_kite_account_balance()
    return {
        "balance": round(balance, 2) if balance else None,
        "trading_mode": auto_trader.trading_mode,
        "error": "Cannot fetch balance" if balance is None else None
    }


# =========================
# User Kite Credentials API
# =========================

@app.post("/user/kite-credentials/save")
def save_kite_credentials(body: dict = Body(...), current_user: dict = Depends(get_current_user)):
    """Save user's Kite API credentials (encrypted in database)
    
    Request body:
    {
        "api_key": "your_zerodha_api_key",
        "access_token": "your_zerodha_access_token"
    }
    
    These credentials are used for paper/real trading orders.
    Chart data and market signals continue using admin credentials.
    
    Returns:
    - status: "ok" or "error"
    """
    from utils.user_credentials import save_user_credentials
    
    logger = logging.getLogger("api.server")
    user_id = current_user.get('user_id')
    
    try:
        api_key = body.get('api_key', '').strip()
        access_token = body.get('access_token', '').strip()
        
        if not api_key or not access_token:
            return {"status": "error", "detail": "API key and access token are required"}
        
        save_user_credentials(user_id, api_key, access_token)
        logger.info(f"User {user_id} saved Kite credentials")
        return {"status": "ok", "detail": "Credentials saved and encrypted"}
    except Exception as e:
        logger.error(f"Error saving credentials for user {user_id}: {e}")
        return {"status": "error", "detail": str(e)}


@app.get("/user/kite-credentials/status")
def get_kite_credentials_status(current_user: dict = Depends(get_current_user)):
    """Check if user has saved Kite credentials
    
    Returns:
    - has_credentials: true/false
    - message: helpful message
    """
    from utils.user_credentials import user_has_credentials
    
    user_id = current_user.get('user_id')
    has_creds = user_has_credentials(user_id)
    
    return {
        "has_credentials": has_creds,
        "message": "Credentials saved" if has_creds else "No credentials saved - needed for trading"
    }


@app.delete("/user/kite-credentials")
def delete_kite_credentials(current_user: dict = Depends(get_current_user)):
    """Delete user's saved Kite credentials
    
    Returns:
    - status: "ok" or "error"
    """
    from utils.user_credentials import delete_user_credentials
    
    logger = logging.getLogger("api.server")
    user_id = current_user.get('user_id')
    
    try:
        delete_user_credentials(user_id)
        logger.info(f"User {user_id} deleted Kite credentials")
        return {"status": "ok", "detail": "Credentials deleted"}
    except Exception as e:
        logger.error(f"Error deleting credentials for user {user_id}: {e}")
        return {"status": "error", "detail": str(e)}


# =========================
# Admin User Approval API
# =========================

@app.get("/admin/pending-users")
def get_pending_users():
    """Get list of pending users awaiting approval
    
    Returns:
    - users: List of {id, email, created_at}
    """
    logger = logging.getLogger("api.server")
    try:
        result = supabase.table('users').select('id, email, created_at').eq('is_approved', False).execute()
        logger.info(f"Retrieved {len(result.data)} pending users")
        return {"users": result.data or [], "count": len(result.data or [])}
    except Exception as e:
        logger.error(f"Error fetching pending users: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch pending users: {str(e)}")


@app.post("/admin/approve-user/{email}")
def approve_user(email: str):
    """Approve a pending user by email
    
    Args:
    - email: Email of user to approve
    
    Returns:
    - status: "ok" or "error"
    - message: Approval status
    """
    logger = logging.getLogger("api.server")
    try:
        # Check if user exists
        result = supabase.table('users').select('id, email, is_approved').eq('email', email).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail=f"User {email} not found")
        
        user = result.data[0]
        if user.get('is_approved'):
            return {"status": "ok", "message": f"User {email} is already approved"}
        
        # Update is_approved to True
        update_result = supabase.table('users').update({'is_approved': True}).eq('email', email).execute()
        logger.info(f"Admin approved user: {email}")
        
        return {"status": "ok", "message": f"User {email} has been approved successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving user {email}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to approve user: {str(e)}")


@app.post("/admin/reject-user/{email}")
def reject_user(email: str):
    """Reject/delete a pending user
    
    Args:
    - email: Email of user to reject
    
    Returns:
    - status: "ok" or "error"
    """
    logger = logging.getLogger("api.server")
    try:
        # Check if user exists
        result = supabase.table('users').select('id').eq('email', email).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail=f"User {email} not found")
        
        # Delete user
        delete_result = supabase.table('users').delete().eq('email', email).execute()
        logger.info(f"Admin rejected user: {email}")
        
        return {"status": "ok", "message": f"User {email} has been rejected"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting user {email}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reject user: {str(e)}")


# =========================
# Premarket Signals API
# =========================
@app.get("/premarket/signals")
def get_premarket_signals(symbol: str = "^NSEI", current_user: dict = Depends(get_current_user)):
    """
    Get premarket signals for a symbol before market opens.
    Can be called anytime - returns prediction based on historical patterns.
    
    Signals based on:
    - Gap analysis (today's open vs yesterday's close)
    - Volume patterns
    - Support/Resistance levels
    - Price action reversal patterns
    """
    return premarket_engine.get_premarket_signals(symbol)


@app.get("/premarket/signals/batch")
def get_premarket_signals_batch(symbols: str = "^NSEI,^NSEBANK", current_user: dict = Depends(get_current_user)):
    """
    Get premarket signals for multiple symbols.
    comma-separated symbol list
    """
    symbol_list = [s.strip() for s in symbols.split(',')]
    return premarket_engine.get_premarket_signals_batch(symbol_list)


@app.get("/premarket/stocks")
def get_premarket_stocks_signals(current_user: dict = Depends(get_current_user)):
    """
    Get premarket signals for all NIFTY 50 stocks.
    Returns list of stocks ranked by signal strength.
    """
    try:
        # Get all NIFTY50 stocks in NSE format
        nifty50_list = get_nifty50_symbols("nse")
        logger = logging.getLogger("api.server")
        logger.info(f"Fetching premarket signals for {len(nifty50_list)} NIFTY50 stocks")
        
        # Get signals for all stocks (batched)
        signals = premarket_engine.get_premarket_signals_batch(nifty50_list)
        
        # Process alerts
        premarket_alerts.process_signals(signals)
        
        # Sort by signal strength: BUY > SELL > NEUTRAL, then STRONG > MEDIUM > WEAK
        strength_order = {'STRONG': 0, 'MEDIUM': 1, 'WEAK': 2}
        signal_order = {'BUY': 0, 'SELL': 1, 'NEUTRAL': 2}
        
        sorted_signals = sorted(signals, key=lambda x: (
            signal_order.get(x['signal'], 3),
            strength_order.get(x['strength'], 3),
            -abs(x['gap_percent'])  # Sort by gap size (highest first)
        ))
        
        # Separate into categories for easier client-side rendering
        buy_strong = [s for s in sorted_signals if s['signal'] == 'BUY' and s['strength'] == 'STRONG']
        buy_medium = [s for s in sorted_signals if s['signal'] == 'BUY' and s['strength'] == 'MEDIUM']
        sell_strong = [s for s in sorted_signals if s['signal'] == 'SELL' and s['strength'] == 'STRONG']
        sell_medium = [s for s in sorted_signals if s['signal'] == 'SELL' and s['strength'] == 'MEDIUM']
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_stocks": len(sorted_signals),
            "summary": {
                "buy_strong": len(buy_strong),
                "buy_medium": len(buy_medium),
                "sell_strong": len(sell_strong),
                "sell_medium": len(sell_medium),
                "neutral": len([s for s in sorted_signals if s['signal'] == 'NEUTRAL'])
            },
            "buy_strong": buy_strong,
            "buy_medium": buy_medium,
            "sell_strong": sell_strong,
            "sell_medium": sell_medium,
            "all_signals": sorted_signals
        }
    except Exception as e:
        logger = logging.getLogger("api.server")
        logger.error(f"Error fetching premarket stocks: {e}", exc_info=True)
        return {"error": str(e)}


# =========================
# Premarket Alerts API
# =========================
@app.get("/premarket/alerts")
def get_premarket_alerts():
    """Get all active premarket alerts"""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "alerts": premarket_alerts.get_active_alerts(),
        "summary": premarket_alerts.get_summary()
    }


@app.get("/premarket/alerts/critical")
def get_critical_alerts():
    """Get only critical priority alerts"""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "critical_alerts": premarket_alerts.get_critical_alerts(),
        "count": len(premarket_alerts.get_critical_alerts())
    }


@app.post("/premarket/alerts/acknowledge")
async def acknowledge_premarket_alert(body: dict = Body(...)):
    """
    Acknowledge an alert to mark it as reviewed
    
    Body:
    {
        "symbol": "INFY",
        "alert_type": "STRONG_BUY"
    }
    """
    symbol = body.get("symbol")
    alert_type = body.get("alert_type")
    
    success = premarket_alerts.acknowledge_alert(symbol, alert_type)
    
    return {
        "success": success,
        "message": f"Alert acknowledged" if success else "Alert not found"
    }


@app.delete("/premarket/alerts")
def clear_premarket_alerts(symbol: Optional[str] = None):
    """
    Clear alerts for a specific symbol or all alerts
    
    Query params:
    - symbol: optional, clear alerts only for this symbol
    """
    premarket_alerts.clear_alerts(symbol)
    return {
        "success": True,
        "message": f"Alerts cleared for {symbol}" if symbol else "All alerts cleared"
    }


# =========================
# Debug/Testing Endpoints
# =========================
@app.get("/debug/premarket-test")
def debug_premarket_test(symbol: str = "INFY", limit: int = 5):
    """
    Test endpoint to verify premarket signals are working.
    Tests a single stock signal generation.
    
    Usage:
        GET /debug/premarket-test?symbol=TCS
        GET /debug/premarket-test?symbol=RELIANCE
    """
    try:
        logger = logging.getLogger("api.server")
        logger.info(f"[DEBUG] Testing premarket signal for {symbol}")
        
        result = premarket_engine.get_premarket_signals(symbol)
        
        if 'reason' in result and 'Insufficient' in result['reason']:
            return {
                "status": "warning",
                "message": "No historical data available for this symbol",
                "symbol": symbol,
                "suggestion": "Ensure symbol is correct and Zerodha API is connected"
            }
        
        return {
            "status": "success",
            "symbol": symbol,
            "signal": result,
            "test_info": {
                "engine_initialized": premarket_engine is not None,
                "kite_connected": premarket_engine.kite is not None
            }
        }
    except Exception as e:
        logger = logging.getLogger("api.server")
        logger.error(f"Premarket test failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "symbol": symbol
        }


@app.get("/debug/premarket-batch-test")
def debug_premarket_batch_test(symbols: str = "INFY,TCS,RELIANCE", limit: int = 3):
    """
    Test endpoint for batch premarket signals.
    Tests signal generation for multiple stocks.
    
    Usage:
        GET /debug/premarket-batch-test?symbols=INFY,TCS,RELIANCE
    """
    try:
        logger = logging.getLogger("api.server")
        symbol_list = [s.strip() for s in symbols.split(',')][:limit]
        logger.info(f"[DEBUG] Testing batch premarket signals for {len(symbol_list)} symbols")
        
        results = premarket_engine.get_premarket_signals_batch(symbol_list)
        
        # Calculate stats
        buy_count = len([r for r in results if r['signal'] == 'BUY'])
        sell_count = len([r for r in results if r['signal'] == 'SELL'])
        neutral_count = len([r for r in results if r['signal'] == 'NEUTRAL'])
        
        return {
            "status": "success",
            "tested_symbols": len(symbol_list),
            "stats": {
                "buy_signals": buy_count,
                "sell_signals": sell_count,
                "neutral_signals": neutral_count
            },
            "signals": results
        }
    except Exception as e:
        logger = logging.getLogger("api.server")
        logger.error(f"Batch premarket test failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/debug/nifty50-list")
def debug_nifty50_list():
    """
    Get list of all NIFTY50 stocks available for premarket analysis.
    Useful for testing and verification.
    """
    try:
        logger = logging.getLogger("api.server")
        nifty50_symbols = get_nifty50_symbols("nse")
        logger.info(f"[DEBUG] NIFTY50 list requested - {len(nifty50_symbols)} stocks")
        
        return {
            "status": "success",
            "total_stocks": len(nifty50_symbols),
            "symbols": nifty50_symbols
        }
    except Exception as e:
        logger = logging.getLogger("api.server")
        logger.error(f"Error getting NIFTY50 list: {e}", exc_info=True)
        return {"error": str(e)}


@app.get("/debug/premarket-health")
def debug_premarket_health():
    """
    Check premarket engine health and dependencies.
    Returns status of all required components.
    """
    try:
        logger = logging.getLogger("api.server")
        
        engine_ok = premarket_engine is not None
        kite_connected = premarket_engine.kite is not None if engine_ok else False
        
        # Try to fetch nifty50 list
        try:
            nifty50_symbols = get_nifty50_symbols("nse")
            nifty50_ok = len(nifty50_symbols) == 50
        except:
            nifty50_ok = False
        
        status = "healthy" if all([engine_ok, kite_connected, nifty50_ok]) else "degraded"
        
        return {
            "status": status,
            "components": {
                "premarket_engine": engine_ok,
                "kite_connection": kite_connected,
                "nifty50_list": nifty50_ok
            },
            "recommendations": [
                "Engine initialized successfully" if engine_ok else "ERROR: Engine not initialized",
                "Zerodha connection active" if kite_connected else "WARNING: Zerodha not connected",
                "NIFTY50 list loaded" if nifty50_ok else "ERROR: NIFTY50 list not available"
            ]
        }
    except Exception as e:
        logger = logging.getLogger("api.server")


@app.get("/next-move")
def get_next_move():
    """
    NEXT DAY OPENING PREDICTION - End-of-day analysis for overnight positions
    - Only after 15:20 IST: Analyzes FULL-DAY data
    - Predicts: Tomorrow's opening direction (CE HOLD vs PE HOLD)
    - Uses: PCR ratio, closing strength, volume momentum, gap expectations
    """
    import pandas as pd
    from datetime import datetime, timedelta
    
    logger = logging.getLogger("api.server")
    
    try:
        # ====== CHECK MARKET HOURS IN IST ======
        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)  # IST = UTC + 5:30
        ist_hour = ist_now.hour
        ist_minute = ist_now.minute
        
        # Only show predictions after 15:20 (3:20 PM) - when market is closing
        is_prediction_time = ist_hour >= 15 and ist_minute >= 20
        analysis_type = "next_day_prediction" if is_prediction_time else "waiting_for_close"
        
        logger.info(f"Market check: UTC={utc_now.strftime('%H:%M:%S')}, IST={ist_now.strftime('%H:%M:%S')}, PredictionTime={is_prediction_time}")
        
        # Early return if market still open
        if not is_prediction_time:
            return {
                "timestamp": datetime.now().isoformat(),
                "market_status": "🕐 Market Open - Check after 15:20 IST (3:20 PM)",
                "data": {},
                "note": "Next day opening predictions available after market close (15:20 IST)"
            }
        
        # Map indices to their tokens stored in INDEX_TOKENS
        index_mapping = {
            "NIFTY": "NIFTY 50",
            "BANKNIFTY": "NIFTY BANK",
            "SENSEX": "SENSEX"
        }
        
        predictions = {}
        
        for index_name, nse_symbol in index_mapping.items():
            signals = {
                "intraday_range": {"high": 0, "low": 0},
                "closing_strength": 0,
                "intraday_momentum": 0,
                "volume_profile": "N/A",
                "pcr_ratio": "N/A",
                "gap_expectation": 0,
                "next_day_probability": 0,
                "recommendation": "NEUTRAL",
                "hold_ce_pe": "⚪ WAIT",
                "signals": [],
                "analysis_type": "next_day_prediction"
            }
            
            
            try:
                # Find token from INDEX_TOKENS (already populated by startup routine)
                token = None
                for tok, info in INDEX_TOKENS.items():
                    if nse_symbol in info.get("key", ""):
                        token = tok
                        break
                
                if not token:
                    logger.error(f"Index token not found for {index_name} ({nse_symbol})")
                    signals["signals"].append(f"❌ Index token not resolved")
                    predictions[index_name] = signals
                    continue
                
                logger.info(f"Fetching FULL-DAY data for {index_name} (token {token})")
                
                # ========== FETCH FULL DAY CANDLES (9:15 AM - 3:30 PM) ==========
                to_date = datetime.now()
                from_date = to_date.replace(hour=9, minute=15, second=0, microsecond=0)
                
                logger.info(f"{index_name}: Fetching full-day candles from {from_date.strftime('%H:%M')} to {to_date.strftime('%H:%M')}")
                
                candles = None
                
                # Try minute candles for accuracy
                try:
                    minute_candles = kite.historical_data(token, from_date, to_date, "minute")
                    if minute_candles and len(minute_candles) >= 10:
                        candles = minute_candles
                        logger.info(f"{index_name}: Got {len(candles)} minute candles")
                except Exception as e:
                    logger.warning(f"Minute candles failed for {index_name}: {e}")
                
                # Fallback to 5-minute candles
                if not candles or len(candles) < 5:
                    try:
                        five_min_candles = kite.historical_data(token, from_date, to_date, "5minute")
                        if five_min_candles and len(five_min_candles) >= 5:
                            candles = five_min_candles
                            logger.info(f"{index_name}: Using {len(candles)} 5-minute candles")
                    except Exception as e:
                        logger.warning(f"5-minute candles failed for {index_name}: {e}")
                
                if not candles or len(candles) < 3:
                    logger.warning(f"{index_name} has no sufficient candle data")
                    signals["signals"].append(f"⏳ Insufficient candle data for {index_name}")
                    predictions[index_name] = signals
                    continue
                
                logger.info(f"{index_name}: Analyzing {len(candles)} candles for next-day prediction")
                
                # ========== SIGNAL 1: INTRADAY RANGE & CLOSING POSITION ==========
                intraday_high = max([c["high"] for c in candles])
                intraday_low = min([c["low"] for c in candles])
                open_price = candles[0]["open"]
                close_price = candles[-1]["close"]
                intraday_range = intraday_high - intraday_low
                
                signals["intraday_range"] = {"high": round(intraday_high, 2), "low": round(intraday_low, 2)}
                
                # Where did we close in today's range? Top, Middle, or Bottom
                close_ratio = (close_price - intraday_low) / intraday_range if intraday_range > 0 else 0.5
                signals["signals"].append(f"📊 Range: {intraday_low:.2f} - {intraday_high:.2f} | Close: {close_price:.2f}")
                
                if close_ratio >= 0.75:
                    signals["signals"].append(f"✅ Closed in TOP 25% of range - Bullish next day")
                    closing_strength = 100
                    closing_pushup = 20
                elif close_ratio >= 0.50:
                    signals["signals"].append(f"➡️ Closed in upper-middle range - Neutral next day")
                    closing_strength = 60
                    closing_pushup = 5
                elif close_ratio >= 0.25:
                    signals["signals"].append(f"➡️ Closed in lower-middle range - Neutral next day")
                    closing_strength = 40
                    closing_pushup = -5
                else:
                    signals["signals"].append(f"❌ Closed in BOTTOM 25% of range - Bearish next day")
                    closing_strength = 0
                    closing_pushup = -20
                
                signals["closing_strength"] = round(close_ratio * 100, 1)
                
                # ========== SIGNAL 2: INTRADAY MOMENTUM (Open to Close trend) ==========
                price_move = close_price - open_price
                momentum_pct = (price_move / open_price * 100) if open_price > 0 else 0
                signals["intraday_momentum"] = round(momentum_pct, 2)
                
                if momentum_pct > 0.5:
                    signals["signals"].append(f"📈 Day ended BULLISH: +{momentum_pct:.2f}% (Open→Close)")
                    momentum_score = 15
                elif momentum_pct < -0.5:
                    signals["signals"].append(f"📉 Day ended BEARISH: {momentum_pct:.2f}% (Open→Close)")
                    momentum_score = -15
                else:
                    signals["signals"].append(f"➡️ Day NEUTRAL: {momentum_pct:+.2f}%")
                    momentum_score = 0
                
                # ========== SIGNAL 3: CLOSING VOLUME & VOLUME PROFILE ==========
                closing_candles = candles[-5:] if len(candles) >= 5 else candles
                day_volumes = [c["volume"] for c in candles]
                avg_volume = sum(day_volumes) / len(day_volumes) if day_volumes else 1
                closing_volume = candles[-1]["volume"]
                morning_volume = sum([c["volume"] for c in candles[:10]]) / min(10, len(candles))
                
                volume_ratio = (closing_volume / avg_volume) if avg_volume > 0 else 1
                signals["signals"].append(f"📊 Closing Volume: {volume_ratio:.2f}x avg | Total: {sum(day_volumes)/10**6:.1f}M")
                
                if closing_volume > avg_volume * 1.3:
                    signals["volume_profile"] = "🚀 HIGH (Strong move confirmation)"
                    volume_score = 10
                elif closing_volume < avg_volume * 0.7:
                    signals["volume_profile"] = "🟡 LOW (Weak/indecisive)"
                    volume_score = -10
                else:
                    signals["volume_profile"] = "➡️ NORMAL"
                    volume_score = 0
                
                # ========== SIGNAL 4: END-OF-DAY CANDLE QUALITY ==========
                last_candle = candles[-1]
                last_body = abs(last_candle["close"] - last_candle["open"])
                last_full_range = last_candle["high"] - last_candle["low"]
                wick_ratio = last_body / last_full_range if last_full_range > 0 else 0
                
                if wick_ratio > 0.7 and last_candle["close"] > last_candle["open"]:
                    signals["signals"].append(f"🟢 Bullish Closing Candle (strong body, small wicks)")
                    candle_quality = 15
                elif wick_ratio > 0.7 and last_candle["close"] < last_candle["open"]:
                    signals["signals"].append(f"🔴 Bearish Closing Candle (strong body, small wicks)")
                    candle_quality = -15
                elif wick_ratio < 0.3:
                    signals["signals"].append(f"⚠️ DOJI/Indecision Candle (may reverse next day)")
                    candle_quality = 5  # Slight reversal bias
                else:
                    signals["signals"].append(f"➡️ Normal Closing Candle")
                    candle_quality = 0
                
                # ========== SIGNAL 5: PCR RATIO (Put/Call at close) ==========
                pcr_score = 0
                try:
                    if index_name in _dashboard_options:
                        option_data = _dashboard_options[index_name]
                        if "CE" in option_data and "PE" in option_data:
                            ce_oi = option_data["CE"].get("oi", 0)
                            pe_oi = option_data["PE"].get("oi", 0)
                            
                            if ce_oi > 0 and pe_oi > 0:
                                pcr = pe_oi / ce_oi
                                signals["pcr_ratio"] = round(pcr, 3)
                                
                                # PCR interpretation for NEXT DAY
                                if pcr > 1.5:
                                    signals["signals"].append(f"🔄 PCR {pcr:.2f} - HIGH (More puts, bearish bias)")
                                    pcr_score = -20  # Stronger bearish signal
                                elif pcr > 1.2:
                                    signals["signals"].append(f"🔄 PCR {pcr:.2f} - ELEVATED (Puts > Calls)")
                                    pcr_score = -10
                                elif pcr < 0.65:
                                    signals["signals"].append(f"🔄 PCR {pcr:.2f} - LOW (More calls, bullish bias)")
                                    pcr_score = 20  # Stronger bullish signal
                                elif pcr < 0.8:
                                    signals["signals"].append(f"🔄 PCR {pcr:.2f} - REDUCED (Calls > Puts)")
                                    pcr_score = 10
                                else:
                                    signals["signals"].append(f"🔄 PCR {pcr:.2f} - BALANCED (Neutral)")
                                    pcr_score = 0
                            else:
                                signals["signals"].append(f"📊 PCR: Insufficient OI data")
                except Exception as e:
                    logger.debug(f"PCR calculation skipped: {e}")
                
                # ========== FINAL NEXT-DAY PREDICTION ==========
                total_score = closing_pushup + momentum_score + volume_score + candle_quality + pcr_score
                
                # Map score to next-day probability (50-90%)
                probability = 70 + (total_score / 100) * 15
                probability = max(50, min(90, probability))
                signals["next_day_probability"] = round(probability, 1)
                
                # Gap expectations
                gap_expected = abs(momentum_pct) > 0.3  # If big move today, likely gap next day
                if gap_expected:
                    signals["gap_expectation"] = round(momentum_pct * 1.5, 2)  # Expect 1.5x gap
                    signals["signals"].append(f"🔁 GAP EXPECTED: {signals['gap_expectation']:+.2f}% (momentum continuation)")
                else:
                    signals["signals"].append(f"No significant gap expected")
                
                # CE/PE recommendation for next day
                if probability >= 75:
                    if total_score > 10:
                        signals["hold_ce_pe"] = "🟢 STRONG CE HOLD (Bullish next day)"
                        signals["recommendation"] = "BUY_CE"
                    else:
                        signals["hold_ce_pe"] = "🔴 STRONG PE HOLD (Bearish next day)"
                        signals["recommendation"] = "BUY_PE"
                elif probability >= 65:
                    if total_score >= 0:
                        signals["hold_ce_pe"] = "🟡 WEAK CE HOLD (Slightly bullish)"
                        signals["recommendation"] = "SLIGHTLY_BULLISH"
                    else:
                        signals["hold_ce_pe"] = "🟡 WEAK PE HOLD (Slightly bearish)"
                        signals["recommendation"] = "SLIGHTLY_BEARISH"
                else:
                    signals["hold_ce_pe"] = "⚪ NEUTRAL (Wait for morning)"
                    signals["recommendation"] = "NEUTRAL"
                
                logger.info(f"{index_name}: Next-day {signals['recommendation']} | Prob: {probability}% | Score: {total_score}")
                predictions[index_name] = signals
                
            except Exception as e:
                logger.error(f"Error analyzing {index_name}: {str(e)}", exc_info=True)
                signals["signals"].append(f"❌ Analysis Error: {str(e)[:50]}")
                predictions[index_name] = signals
        
        return {
            "timestamp": datetime.now().isoformat(),
            "market_status": "🌙 Market CLOSED - End-of-Day Analysis Complete",
            "data": predictions,
            "prediction_note": "📊 NEXT DAY OPENING PREDICTION | Analysis @ 15:20 IST",
            "methodology": {
                "closing_position": "Where index closed in today's range (top = bullish)",
                "intraday_momentum": "Overall direction from market open to close",
                "volume_profile": "Closing volume vs daily average (high = confirmation)",
                "candle_quality": "Last candle body/wick ratio (strong = conviction)",
                "pcr_ratio": "Put/Call ratio at close (>1.5 = bearish, <0.65 = bullish)"
            },
            "recommendation_note": "🟡 Probabilities: STRONG (75%+) | WEAK (65-74%) | NEUTRAL (<65%)"
        }
        
    except Exception as e:
        logger.error(f"Error in /next-move endpoint: {str(e)}", exc_info=True)
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }