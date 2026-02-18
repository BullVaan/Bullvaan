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

        # vote counts
        buy = votes.count("BUY")
        sell = votes.count("SELL")
        neutral = votes.count("NEUTRAL")

        # consensus logic (scalping: 3+ votes for signal)
        if buy >= 3:
            consensus = "BUY"
        elif sell >= 3:
            consensus = "SELL"
        else:
            consensus = "NEUTRAL"

        # response
        return {
            "symbol": symbol,
            "index_name": SUPPORTED_INDICES[symbol],
            "timeframe": timeframe,
            "timeframe_info": TIMEFRAME_CONFIG[timeframe],
            "price": round(current_price, 2),
            "consensus": consensus,
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
