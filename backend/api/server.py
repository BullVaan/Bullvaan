from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import logging

from utils.nse_live import fetch_nse_indices


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
            current_vix = float(vix_data['Close'].iloc[-1])
            
            # Previous close = yesterday's close
            if len(vix_data) > 1:
                prev_close_vix = float(vix_data['Close'].iloc[-2])
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
# WebSocket: Real-time Ticker
# =========================
@app.websocket("/ws/ticker")
async def ws_ticker(websocket: WebSocket):
    """
    Streams real-time NSE index prices to the frontend
    Updates every 2 seconds during market hours
    """
    await websocket.accept()
    try:
        while True:
            data = fetch_nse_indices()
            await websocket.send_text(json.dumps(data))
            await asyncio.sleep(2)  # push every 2 seconds
    except WebSocketDisconnect:
        pass
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