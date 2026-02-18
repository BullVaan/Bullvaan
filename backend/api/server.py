from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

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

# utils
from utils.yahoo_finance import fetch_history, standardize_ohlcv

# dual engine
from engine.dual_engine import calculate_score


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
# INDICES
# =========================
SUPPORTED_INDICES = {
    "^NSEI": "NIFTY 50",
    "^NSEBANK": "BANK NIFTY",
    "^BSESN": "SENSEX",
}

# =========================
# STRATEGIES
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
# ATR CALC
# =========================
def calculate_atr(df, period=14):
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()

    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    tr = ranges.max(axis=1)

    atr = tr.rolling(period).mean()
    return float(atr.iloc[-1])


# =========================
# VOL FILTER
# =========================
def atr_volatility_filter(df):
    atr = calculate_atr(df)
    price = df["close"].iloc[-1]
    atr_pct = (atr / price) * 100

    if 0.5 <= atr_pct <= 2:
        return True, atr, atr_pct, "GOOD"
    elif atr_pct < 0.5:
        return False, atr, atr_pct, "LOW"
    else:
        return False, atr, atr_pct, "HIGH"


# =========================
# TREND FILTER
# =========================
def trend_strength_filter(adx):
    if adx is None:
        return False
    return adx >= 20


# =========================
# STRUCTURE
# =========================
def market_structure_filter(df):
    highs = df["high"].tail(5).values
    lows = df["low"].tail(5).values

    higher_highs = all(x < y for x, y in zip(highs, highs[1:]))
    higher_lows = all(x < y for x, y in zip(lows, lows[1:]))

    lower_highs = all(x > y for x, y in zip(highs, highs[1:]))
    lower_lows = all(x > y for x, y in zip(lows, lows[1:]))

    if higher_highs and higher_lows:
        return "UP"
    elif lower_highs and lower_lows:
        return "DOWN"
    else:
        return "SIDEWAYS"


# =========================
# REGIME DETECTOR
# =========================
def detect_market_regime(adx, structure):
    if adx and adx > 25 and structure != "SIDEWAYS":
        return "TREND"
    return "SCALP"


# =========================
# HOME
# =========================
@app.get("/")
def home():
    return {"status": "Bullvan API running"}


# =========================
# SIGNAL ENGINE
# =========================
@app.get("/signals")
def get_signals(symbol: str = "^NSEI"):

    if symbol not in SUPPORTED_INDICES:
        return {"error": "Invalid symbol"}

    # ---------- FETCH ----------
    try:
        fetched = fetch_history(symbol)

        if not fetched or fetched.df is None or fetched.df.empty:
            raise ValueError("Empty dataset received")

        df = standardize_ohlcv(fetched.df)

        if df is None or df.empty:
            raise ValueError("Standardized dataframe empty")

    except Exception as e:
        return {"error": "Market data unavailable", "details": str(e)}

    # ---------- PRICE ----------
    try:
        price = float(df["close"].iloc[-1])
    except:
        return {"error": "Invalid price data"}

    # ---------- STRATEGIES ----------
    results = []
    adx_value = None

    for strat in strategies:
        try:
            sig = strat.calculate(df)
        except:
            sig = "NEUTRAL"

        results.append({
            "name": str(strat.name),
            "signal": str(sig)
        })

        if "ADX" in strat.name:
            try:
                meta = strat.get_signal()
                adx_value = meta["metadata"].get("adx")
                if adx_value is not None:
                    adx_value = float(adx_value)
            except:
                adx_value = None

    # ---------- FILTER DATA ----------
    vol_ok, atr, atr_pct, atr_state = atr_volatility_filter(df)
    trend_ok = trend_strength_filter(adx_value)
    structure = market_structure_filter(df)

    # ---------- REGIME ----------
    mode = detect_market_regime(adx_value, structure)

    # ---------- SCORE ----------
    decision, confidence, score = calculate_score(results, mode)

    # ---------- APPLY FILTERS ----------
    filters_passed = bool(vol_ok and trend_ok and structure != "SIDEWAYS")

    # ONLY block trades in TREND mode
    if mode == "TREND" and not filters_passed:
        decision = "NO TRADE"
        confidence = 0

    # ---------- RESPONSE ----------
    return {
        "symbol": symbol,
        "index_name": SUPPORTED_INDICES[symbol],
        "price": round(price, 2),

        "signal": str(decision),
        "confidence": float(round(confidence, 2)),
        "score": float(round(score, 2)),
        "engine_mode": mode,

        "atr": round(float(atr), 2),
        "atr_percent": round(float(atr_pct), 2),
        "atr_state": str(atr_state),

        "trend_strength": round(float(adx_value), 2) if adx_value else None,
        "market_structure": str(structure),
        "filters_passed": bool(filters_passed),

        "signals": results
    }


# =========================
# INDICES LIST
# =========================
@app.get("/indices")
def get_indices():
    return SUPPORTED_INDICES
