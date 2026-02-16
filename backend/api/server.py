from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# scoring engine
from engine.smart_engine import calculate_score

app = FastAPI(title="Bullvan Trading API")

# =========================
# CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
# Initialize Strategies
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
# Health Check
# =========================
@app.get("/")
def home():
    return {"status": "Bullvan API running"}

# =========================
# Get Signals
# =========================
@app.get("/signals")
def get_signals(symbol: str = "^NSEI"):

    if symbol not in SUPPORTED_INDICES:
        return {"error": "Invalid symbol"}

    try:
        fetched = fetch_history(symbol)
        df = standardize_ohlcv(fetched.df)

        if df.empty:
            return {"error": "No market data"}

        current_price = float(df["close"].iloc[-1])

        results = []

        # run strategies
        for strat in strategies:
            signal = strat.calculate(df)
            results.append({
                "name": strat.name,
                "signal": signal
            })

        # ===== ADVANCED ENGINE =====
        decision, confidence, score = calculate_score(results)

        return {
            "symbol": symbol,
            "index_name": SUPPORTED_INDICES[symbol],
            "price": round(current_price, 2),

            "signal": decision,
            "confidence": confidence,
            "score": score,

            "signals": results
        }

    except Exception as e:
        return {
            "error": "Server error",
            "message": str(e)
        }

# =========================
# Indices List
# =========================
@app.get("/indices")
def get_indices():
    return SUPPORTED_INDICES
