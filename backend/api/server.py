from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json

from utils.nse_live import fetch_nse_indices


# strategies
from strategies.strategy_1_moving_average import MovingAverageStrategy
from strategies.strategy_2_rsi import RSIStrategy
from strategies.strategy_3_macd import MACDStrategy
from strategies.strategy_4_bollinger_bands import BollingerBandsStrategy
from strategies.strategy_5_ema_crossover import EMACrossoverStrategy
from strategies.strategy_6_supertrend import SupertrendStrategy
from strategies.strategy_7_vwap import VWAPStrategy
from strategies.strategy_8_stochastic import StochasticStrategy
from strategies.strategy_9_adx import ADXStrategy
from strategies.strategy_10_volume import VolumeStrategy

# data utils
from utils.yahoo_finance import fetch_history, standardize_ohlcv

app = FastAPI(title="Bullvan Trading API")


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
# Initialize Strategies Once
# =========================
strategies = [
    MovingAverageStrategy(20),
    RSIStrategy(14, 40, 60),
    MACDStrategy(5, 13, 1),
    BollingerBandsStrategy(20, 2),
    EMACrossoverStrategy(9, 21),
    SupertrendStrategy(10, 3),
    VWAPStrategy(),
    StochasticStrategy(),
    ADXStrategy(),
    VolumeStrategy(),
]


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
def get_signals(symbol: str = "^NSEI"):
    """
    Returns signals for selected index
    Default = NIFTY
    """

    # validate symbol
    if symbol not in SUPPORTED_INDICES:
        return {
            "error": "Invalid symbol",
            "supported": list(SUPPORTED_INDICES.keys())
        }

    try:
        # fetch market data
        fetched = fetch_history(symbol)
        df = standardize_ohlcv(fetched.df)

        if df.empty:
            return {"error": "No market data received"}

        # current price
        current_price = float(df["close"].iloc[-1])

        results = []
        votes = []

        # run strategies
        for strat in strategies:
            signal = strat.calculate(df)

            results.append({
                "name": strat.name,
                "signal": signal
            })

            votes.append(signal)

        # vote counts
        buy = votes.count("BUY")
        sell = votes.count("SELL")
        neutral = votes.count("NEUTRAL")

        # consensus logic
        if buy >= 7:
            consensus = "BUY"
        elif sell >= 7:
            consensus = "SELL"
        else:
            consensus = "NEUTRAL"

        # response
        return {
            "symbol": symbol,
            "index_name": SUPPORTED_INDICES[symbol],
            "price": round(current_price, 2),
            "consensus": consensus,
            "buy_votes": buy,
            "sell_votes": sell,
            "neutral_votes": neutral,
            "total_strategies": len(strategies),
            "signals": results
        }

    except Exception as e:
        return {
            "error": "Server error",
            "message": str(e)
        }


# =========================
# Available Indices Route
# =========================
@app.get("/indices")
def get_indices():
    return SUPPORTED_INDICES


# =========================
# NSE Ticker (HTTP fallback)
# =========================
@app.get("/ticker")
def get_ticker():
    """HTTP fallback — returns latest NSE index prices"""
    return fetch_nse_indices()


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
