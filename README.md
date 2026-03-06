# BullVaan — Real-Time Options Trading Dashboard

> Multi-strategy scalping platform for NSE/BSE index options with auto-trading engine.

![Market](https://img.shields.io/badge/Market-NSE%20%7C%20BSE-blue)
![Mode](https://img.shields.io/badge/Mode-Paper%20Trading-orange)
![Strategies](https://img.shields.io/badge/Strategies-7-green)

---

## What It Does

BullVaan analyzes NIFTY, BANKNIFTY, and SENSEX using 7 technical strategies grouped into 3 categories. When Trend + Strength agree and Momentum doesn't oppose, it generates a signal (STRONG or MEDIUM) and can auto-trade ATM options.

**Core idea:** You don't buy because one indicator says so. You buy when multiple independent strategies agree.

---

## Tech Stack

| Layer | Tech |
|-------|------|
| **Backend** | Python, FastAPI, Uvicorn |
| **Frontend** | React (CRA) |
| **Broker API** | Zerodha KiteConnect + KiteTicker (MODE_FULL) |
| **Data** | Zerodha historical candles, yfinance (stocks), NSE live |
| **Charts** | Lightweight Charts (TradingView) |

---

## Project Structure

```
BullVaan/
├── backend/
│   ├── api/
│   │   ├── server.py              # FastAPI server (~21 routes, 5 WebSockets)
│   │   ├── login.py               # POST /api/login
│   │   └── signup.py              # POST /api/signup
│   ├── engine/auto_trader.py      # Auto-trading engine (paper mode)
│   ├── strategies/                # 7 strategies (MA, RSI, MACD, EMA, Supertrend, Stoch, ADX)
│   ├── utils/
│   │   ├── zerodha_data.py        # Zerodha historical candles
│   │   ├── nse_live.py            # NSE index data
│   │   ├── logger.py              # File-based logging (trades, signals, app)
│   │   └── config.py              # Loads .env (minimal)
│   ├── data/trades.json           # Trade log (paper)
│   ├── .env                       # API keys (not committed)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/                 # Dashboard, Stocks, Trades, Charts, Login, Signup, etc.
│   │   ├── components/            # MarketTicker, OptionSuggestion, RoleCard, etc.
│   │   └── layout/MainLayout.js   # Sidebar + routing
│   └── package.json
├── config/trading_rules.json      # Strategy params, targets, lot sizes
└── ENGINE_README.md               # Auto-trader rules & design doc
```

---

## Strategies (7)

| Category | Strategy | Parameters |
|----------|----------|------------|
| **Trend** | Moving Average | MA(5) |
| **Trend** | EMA Crossover | EMA(5, 13) |
| **Momentum** | RSI | RSI(7) |
| **Momentum** | MACD | MACD(5, 13, 1) |
| **Momentum** | Stochastic | Stoch(5, 3, 3) |
| **Strength** | Supertrend | ST(7, 2) |
| **Strength** | ADX | ADX(14) |

**Signal logic:** Trend + Strength must agree → STRONG (all 3 categories agree) or MEDIUM (Momentum neutral). If Momentum opposes or Trend ≠ Strength → NEUTRAL (no trade).

---

## Signal → Trade Flow

```
KiteTicker tick (real-time)
  → Zerodha historical candles (5m)
  → 7 strategies compute BUY / SELL / NEUTRAL
  → Category consensus (Trend, Momentum, Strength)
  → Overall signal: STRONG / MEDIUM / NEUTRAL
  → Auto-trader: entry/exit with target + stop-loss
  → Dashboard: live display + option suggestion
```

---

## Auto-Trader (Paper Mode)

- **Capital:** ₹1,00,000
- **Indices:** NIFTY, BANKNIFTY, SENSEX (lots calculated dynamically, max 5)
- **STRONG signal:** Target +20 pts, SL -10 pts (1:2 R:R)
- **MEDIUM signal:** Target +12 pts, SL -10 pts (1:1.2 R:R)
- **Safety:** Max 15 trades/day, ₹5,000 daily loss kill switch, 9:20 AM–3:25 PM only
- **Tick interval:** 2 seconds via KiteTicker

See [ENGINE_README.md](ENGINE_README.md) for full rules.

---

## Pages

| Page | Description |
|------|-------------|
| **Dashboard (F&O)** | Signals, VIX, ATR, options suggestion, auto-trader toggle |
| **Stocks** (SwingTrade.js) | Nifty50 Smart Movers — sector analysis, breakout detection |
| **Charts** (CandlesCharts.js) | Live candlestick charts (1m, 5m, 15m) |
| **Trades** | Active + completed trades with live P&L |
| **History** | Trade history (stub) |
| **Settings** | Configuration (stub) |
| **Login / Signup** | Auth pages (localStorage-based) |

---

## Setup

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env with Zerodha credentials
echo "API_KEY=your_key" > .env
echo "ACCESS_TOKEN=your_token" >> .env

uvicorn api.server:app --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm start          # Runs on port 3000, proxies API to 8000
```

### Zerodha Access Token
```bash
# Generate daily token (expires at 6 AM IST)
cd backend
python test_zerodha.py
```

---

## WebSocket Endpoints

| Path | Purpose | Data |
|------|---------|------|
| `/ws/ticker` | Live index prices | NIFTY, BANKNIFTY, SENSEX |
| `/ws/options` | Live option chain | ATM/OTM CE/PE with LTP |
| `/ws/trades` | Trade updates | Active trades with live P&L |
| `/ws/nifty50` | Stock movers | 50 stocks with signals |
| `/ws/candles/{symbol}/{interval}` | Live candles | 1m, 5m, 15m OHLC |

---

## Key Design Decisions

- **KiteTicker MODE_FULL** for `last_trade_time` (true price freshness, not exchange timestamp)
- **Signal cache** with 300s TTL (matches 5m candle timeframe)
- **In-memory trades cache** to avoid disk I/O on every tick
- **2-tick price confirmation** before auto-entry
- **Category gate:** Momentum alone can never trigger a trade
- **`trading_rules.json`** is the single source of truth for strategy parameters

---

*Last updated: 6 Mar 2026*
