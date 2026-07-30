# BullVaan — Real-Time Options Trading Dashboard

> Multi-strategy scalping platform for NSE/BSE index options with auto-trading engine.

![Market](https://img.shields.io/badge/Market-NSE%20%7C%20BSE-blue)
![Mode](https://img.shields.io/badge/Mode-Paper%20Trading-orange)
![Strategies](https://img.shields.io/badge/Strategies-7-green)
![Engine](https://img.shields.io/badge/Engine-v1.9-brightgreen)

---

## What It Does

BullVaan analyzes NIFTY, BANKNIFTY, and SENSEX using 7 technical strategies grouped into 3 categories. When Trend + Strength agree and Momentum doesn't oppose, it generates a signal (STRONG or MEDIUM) and auto-trades ATM options.

**Core idea:** You don't buy because one indicator says so. You buy when multiple independent strategies agree — and only if the price hasn't spiked.

**v1.9 addition:** The engine now logs real-time OI, volume, and order book data from KiteTicker for each ATM option. The backtester uses this as entry confirmation gates — OI buildup, volume spikes, buy/sell imbalance, and PCR filtering — to reduce trades from 30-40/day to high-conviction entries only.

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
│   ├── backtest_signal_logs.py    # Signal log backtester (17 variants)
│   ├── strategies/                # 7 strategies (MA, RSI, MACD, EMA, Supertrend, Stoch, ADX)
│   ├── utils/
│   │   ├── zerodha_data.py        # Zerodha historical candles
│   │   ├── nse_live.py            # NSE index data
│   │   ├── logger.py              # File-based logging
│   │   └── config.py              # Loads .env
│   ├── data/
│   │   ├── trades.json            # Trade log (paper)
│   │   └── signal_logs/           # Per-day JSONL signal logs for backtesting
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/                 # Dashboard, Trades, Charts, History, Settings, etc.
│   │   ├── components/            # MarketTicker, OptionSuggestion, PremarketSignals, etc.
│   │   └── layout/MainLayout.js   # Sidebar + routing
│   └── package.json
├── config/trading_rules.json      # Strategy params, targets, lot sizes
├── ENGINE_README.md               # Auto-trader rules & design doc
└── README.md                      # This file
```

---

## Strategies (7)

| Category | Strategy | Parameters | Purpose |
|----------|----------|------------|---------|
| **Trend** | Moving Average | MA(5) | Direction of trend |
| **Trend** | EMA Crossover | EMA(5, 13) | Direction of trend |
| **Momentum** | RSI | RSI(7) | Speed of movement |
| **Momentum** | MACD | MACD(5, 13, 1) | Speed of movement |
| **Momentum** | Stochastic | Stoch(5, 3, 3) | Speed of movement |
| **Strength** | Supertrend | ST(7, 2) | Trend reliability |
| **Strength** | ADX | ADX(14) | Trend reliability |

**Signal logic:** Trend + Strength must agree → STRONG (all 3 categories agree) or MEDIUM (Momentum neutral). If Momentum opposes or Trend ≠ Strength → NEUTRAL (no trade).

---

## Signal → Trade Flow

```
KiteTicker tick (every ~2 seconds, MODE_FULL)
  → Zerodha historical candles (5m)
  → 7 strategies compute BUY / SELL / NEUTRAL
  → Category consensus (Trend, Momentum, Strength)
  → Overall signal: STRONG / MEDIUM / NEUTRAL
  → Anti-spike filter (is price elevated above recent average?)
  → OI/Volume confirmation (v1.9 — backtester):
      → OI building in trade direction?
      → Volume above rolling average?
      → Buy/sell qty imbalance supports entry?
      → PCR (put/call OI ratio) supports direction?
  → Price confirmation (stable across 2 ticks?)
  → Auto-trader: entry with target + stop-loss
  → Dashboard: live display + option suggestion

Signal log records (every 2s per index):
  → Price data: ce_price, pe_price, spot_price
  → OI data: ce_oi, pe_oi (v1.9+)
  → Volume data: ce_volume, pe_volume (v1.9+)
  → Order book: ce_buy_qty, ce_sell_qty, pe_buy_qty, pe_sell_qty (v1.9+)
```

---

## Auto-Trader (Paper Mode) — v1.9

### Core Parameters
- **Capital:** ₹1,00,000
- **Indices:** NIFTY, BANKNIFTY, SENSEX (lots calculated dynamically, max 5)
- **Tick interval:** 2 seconds via KiteTicker

### Adaptive Config (Choppy → Trending) with Hybrid Neutral Exit

The engine starts each day with a conservative "choppy" config and automatically upgrades to an aggressive "trending" config after 2 consecutive winning trades. The neutral-exit behavior also toggles with the switch.

| Phase | Trigger | NIFTY | BANKNIFTY | SENSEX | Neutral Exit |
|-------|---------|-------|-----------|--------|-------------|
| **Choppy** | Market open | T5/SL5, BE@3 | T12/SL10 | T12/SL10 | **ON** — exit on neutral |
| **Trending** | 2 consecutive wins | T10/SL8, BE@5 | T15/SL18 | T6/SL12 | **OFF** — ignore neutral |

- **One-way switch:** once upgraded, stays trending for rest of day
- **Why start choppy?** Smaller SLs = cheaper "detection cost". On trending days, 2 wins come fast.
- **Why hybrid neutral?** Choppy: neutral exit cuts losses early. Trending: neutral exit prematurely kills winners.

**Backtester proof (11 days):** Adaptive + hybrid neutral = **₹+68,296** (59.7% WR, 7/11 green days) vs single config ₹+32,454 (**+110% improvement**).

Configured in `config/trading_rules.json` under `adaptive_config`.

### Per-Index Rules (Static Fallback)
| Index | Target | Stop Loss | Breakeven Lock | Lot Size |
|-------|--------|-----------|----------------|----------|
| NIFTY | 10 pts | 8 pts | +5 pts → SL to breakeven | 65 |
| BANKNIFTY | 20 pts | 15 pts | — | 30 |
| SENSEX | 12 pts | 10 pts | — | 20 |

> These are used when adaptive config is disabled. When enabled, the adaptive choppy/trending values override them.

### Entry Filters (applied in order)
1. Signal strength STRONG or MEDIUM
2. No open position on this index
3. Profit protection not active
4. **Entry skip window** — not in 10:00-10:30 dead zone
5. **Loss streak combo** — not blocked by consecutive losses per-index
6. **Afternoon SELL-only** — BUY signals blocked after 12:30 PM
7. ATM strike + price obtained
8. **Premium cap** — skip if BN ≥ ₹1,000, SENSEX ≥ ₹500
9. **Anti-spike warmup** — need ≥3 prices before allowing entry
10. **Anti-spike filter** — skip if price > 5-tick avg + 1pt
12. **OI confirmation** (v1.9, backtester) — skip if OI declining for trade direction
13. **Volume spike** (v1.9, backtester) — skip if volume below 1.5× rolling avg
14. **Buy/sell imbalance** (v1.9, backtester) — skip if order book doesn't support direction
15. **PCR filter** (v1.9, backtester) — skip if put/call ratio contradicts entry
16. Capital available
17. 2-tick price confirmation

### Anti-Spike Filter (the key edge)
The engine maintains a rolling window of the last 10 ATM option prices per index. Before entering, it checks if the current price is more than 1 point above the average of the last 5 prices. If it is, the entry is skipped — the price has spiked and buying at that level is unprofitable.

Three layers ensure the price history is always populated:
- **Pre-market warmup (9:15-9:20)** — collects live option prices before trading starts
- **Warmup blocking** — blocks entry until ≥3 prices collected (~6 seconds)
- **Signal log prefill** — on mid-day restart, reloads up to 10 prices from today's signal log (strike-aware)

**Backtester proof (8 days):** Without anti-spike = +₹528. With anti-spike 1pt = **+₹37,040** (8/8 profitable days).

### Premium Cap
High-premium options have worse SL/target ratios. The engine skips entry if the option premium exceeds a per-index cap: BANKNIFTY < ₹1,000, SENSEX < ₹500, NIFTY has no cap.

**Backtester proof (8 days):** Without premium cap = +₹37,040. With premium cap = **+₹44,371** (+20% improvement).

### Loss Streak Combo
Per-index filter that blocks new entries when consecutive losses pile up. Two trigger conditions (whichever hits first):
- **3 consecutive losses** of any amount → block
- **2+ consecutive losses** totaling ≥ ₹3,000 → block

Resets on any win (PnL ≥ 0). A single loss never triggers.

**Why not the old "consecutive SL block"?** The v1.5 removal of the 2-SL block was correct for the old rule (too aggressive). The streak combo is smarter — it's amount-aware and requires a minimum count, so it only blocks during genuine losing streaks, not normal trading volatility.

**Backtester proof (9 days):** Without streak = -₹3,858. With streak combo = **+₹23,327**. Real trades: saves **+₹56,655** (₹1,13,890 → ₹1,70,545).

Configured in `config/trading_rules.json` under `loss_streak`.

### Entry Skip Window (10:00–10:30)
The 10:00–10:30 window is the worst 30-minute slot across 45 trading days (35% win rate, -₹14,769 aggregate). The opening momentum exhausts around 10:00 and the market chops before the next trend forms at 10:30+. No new entries are placed during this period.

**Combined proof (10 signal log days):** Streak + skip = **+₹41,468** vs no filters = +₹8,190.

Configured in `config/trading_rules.json` under `entry_skip_window`. Set to `null` to disable.

### Safety Controls
| Control | Value | Status |
|---------|-------|--------|
| Market hours | 9:20 AM – 3:25 PM IST | Active |
| Pre-market warmup | 9:15 – 9:20 AM IST | Active |
| EOD forced exit | 3:25 PM IST | Active |
| Max lots per trade | 5 | Active |
| Anti-spike filter | 1 point threshold | Active |
| Anti-spike warmup | 3 ticks min | Active |
| Premium cap | BN<₹1K, SX<₹500 | Active |
| Loss streak combo | 3 losses OR 2+₹3K | Active |
| Entry skip window | 10:00–10:30 | Active |
| Price confirmation | 2 ticks | Active |
| Breakeven lock | NIFTY: +5 pts | Active |
| Adaptive config | Choppy→Trending after 2 wins | Active |
| Hybrid neutral exit | ON in choppy, OFF in trending | Active |
| Afternoon SELL-only | BUY blocked after 12:30 PM | Active |
| OI confirmation | Skip if OI declining in trade direction | Backtester |
| Volume spike | Skip if volume < 1.5× rolling avg | Backtester |
| Buy/sell imbalance | Skip if order book ratio < 1.3 | Backtester |
| PCR filter | Skip if PCR contradicts direction | Backtester |
| Daily loss kill switch | ₹5,000 | Disabled |
| Profit protection | Peak ₹3K, drop ₹2K | Disabled |

### What's NOT in the Engine (removed in v1.5)
- ~~Cooldowns~~ — Backtester proved cooldowns cost ₹31K over 6 days
- ~~Max trades/day~~ — Cap of 9 left ₹16K on the table
- ~~Late session multiplier~~ — Removed with cooldowns
- ~~Consecutive SL block~~ — Backtester: blocking after 2 SLs = +₹5,974 vs no block = +₹26,849. **Replaced by loss streak combo** (smarter amount+count based filter)
- ~~Momentum guard~~ — Backtester: momentum guard = -₹4,109 vs no guard = +₹26,849

See [ENGINE_README.md](ENGINE_README.md) for full rules, anti-spike algorithm details, and backtester results.

---

## Backtester

```bash
cd backend
python3 backtest_signal_logs.py 2026-06-15
```

Replays signal log data through 34 variant configurations. Tests anti-spike thresholds, cooldowns, trade limits, neutral exits, premium caps, loss streak combos, OI/volume confirmation filters, and combinations. Used to validate every parameter before implementing in the live engine.

### OI/Volume Variants (v1.9)
| Variant | What It Tests |
|---------|---------------|
| ZL | OI confirmation only |
| ZM | Volume spike (1.5×) only |
| ZN | Buy/sell imbalance (1.3×) only |
| ZO | PCR filter only |
| ZP | All OI/vol filters combined |

---

## Pages

| Page | Description |
|------|-------------|
| **Dashboard (F&O)** | Signals, VIX, ATR, options suggestion, auto-trader toggle |
| **Stocks** (SwingTrade.js) | Nifty50 Smart Movers — sector analysis, breakout detection |
| **Charts** (CandlesCharts.js) | Live candlestick charts (1m, 5m, 15m) |
| **Trades** | Active + completed trades with live P&L |
| **History** | Trade history |
| **Settings** | Configuration |
| **Login / Signup** | Auth pages |

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

- **KiteTicker MODE_FULL** for `last_trade_time` (true price freshness) + OI, volume, buy/sell qty, order book depth (v1.9)
- **Adaptive dual-config** — start choppy (small SLs), upgrade to trending after 2 wins (+110% over single config)
- **Hybrid neutral exit** — ON during choppy (cut losses early), OFF during trending (let winners run)
- **Afternoon SELL-only** — BUY signals blocked after 12:30 PM; Indian markets drift down in afternoons, BUY signals are the #1 loss source (+₹22K improvement over 12 days)
- **Anti-spike filter** — the single biggest improvement, turning +₹528 into +₹37K over 8 days
- **Premium cap** — skipping expensive options adds another +₹7K (₹37K → ₹44K over 8 days)
- **No cooldowns, no trade limits** — backtester proved these hurt more than help
- **Signal cache** with 300s TTL (matches 5m candle timeframe)
- **In-memory trades cache** to avoid disk I/O on every tick
- **2-tick price confirmation** before auto-entry
- **Atomic snapshot** for ATM strike + price (prevents strike/price mismatch)
- **Category gate:** Momentum alone can never trigger a trade
- **Background option subscriber** keeps ATM prices fresh for all 3 indices every 5s
- **`trading_rules.json`** is the single source of truth for strategy parameters
- **Signal logger** records every tick for post-market backtesting — now includes OI, volume, and order book data (v1.9)
- **OI/Volume confirmation gates** (v1.9) — 4 institutional-grade entry filters (OI buildup, volume spike, order book imbalance, PCR) tested in backtester before live deployment

---

*Last updated: 24 Jun 2026 — Engine v1.9 (OI/Volume Confirmation Gates)*
