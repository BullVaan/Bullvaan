# Bullvaan Auto-Trading Engine — Rules & Design

> Paper Trading Mode | Capital: ₹1,00,000 | Market: NSE/BSE Options

---

## 1. Strategy Categories

The engine uses 7 technical indicators grouped into 3 categories. Each category votes independently, and the combined result drives trade decisions.

| Category     | Strategies                        | Count | Purpose              |
|-------------|-----------------------------------|-------|----------------------|
| **Trend**     | MA(5), EMA(5, 13)                | 2     | Direction of trend   |
| **Momentum**  | RSI(7), MACD(5, 13, 1), Stoch(5, 3, 3) | 3 | Speed of movement |
| **Strength**  | Supertrend(7, 2), ADX(14)        | 2     | Trend reliability    |

---

## 2. Signal Strength Classification

### Core Rule: Trend + Strength Must Agree

**Trend** and **Strength** are the two structural categories — they must both point in the same direction (BUY or SELL) for any trade signal.

**Momentum** acts as a confirmer — it must either agree or stay neutral. If Momentum opposes, no trade.

#### Per-Category Consensus Rules
| Indicators | Rule |
|-----------|------|
| 2 (Trend, Strength) | Both must agree. BUY+NEUTRAL = BUY. BUY+SELL = NEUTRAL (conflict). |
| 3 (Momentum) | Any BUY+SELL present = NEUTRAL (conflict). 2+ NEUTRAL = NEUTRAL. Otherwise active direction wins. |

#### Overall Signal
| Scenario | Signal Strength |
|---------|----------------|
| Trend + Strength + Momentum all agree | **STRONG** |
| Trend + Strength agree, Momentum = NEUTRAL | **MEDIUM** |
| Trend + Strength agree, Momentum **opposes** | **NEUTRAL** (no trade) |
| Trend ≠ Strength (disagree or one neutral) | **NEUTRAL** (no trade) |

> **Key insight:** Momentum alone can never trigger a trade. Only Trend + Strength alignment matters. Momentum just upgrades MEDIUM → STRONG or blocks the trade if it opposes.

---

## 3. Trading Rules

### Per-Index Target & Stop-Loss

Each index has its own target and stop-loss tuned from backtester analysis on 6 days of signal log data:

| Index      | Target (pts) | Stop Loss (pts) | Breakeven Lock | Lot Size |
|-----------|-------------|------------------|----------------|----------|
| NIFTY      | 10          | 8                | +5 pts → SL moves to breakeven | 65 |
| BANKNIFTY  | 20          | 15               | —              | 30 |
| SENSEX     | 12          | 10               | —              | 20 |

> **Why these SL levels?** Tested tighter (5/10/7) and wider (12/22/15) in backtester. Tighter = more trades but noise stops you out (lower WR, lower PnL). Wider = higher WR but negative risk:reward. Current levels are optimal.

### Adaptive Config Switching (Choppy → Trending) with Hybrid Neutral Exit

The engine uses an adaptive dual-config system that starts conservative and upgrades mid-day based on performance. It also toggles the neutral-exit behavior: in choppy mode, trades exit on SIGNAL_NEUTRAL to cut losses early; in trending mode, neutral exits are disabled so trades ride through dips to hit the bigger target.

| Phase | Trigger | NIFTY | BANKNIFTY | SENSEX | Neutral Exit |
|-------|---------|-------|-----------|--------|-------------|
| **Start (Choppy)** | Market open | T5/SL5, BE@3 | T12/SL10 | T12/SL10 | **ON** — exit on neutral |
| **Switch (Trending)** | After 2 consecutive wins | T10/SL8, BE@5 | T15/SL18 | T6/SL12 | **OFF** — ignore neutral |

two separate configs, use the choppy one on choppy days and the trending one on trending days. Let me find the best of each and show the combined result.

Massive difference. Here are the two best configs:

Dual Config Results
Setup	Choppy	Trend	TOTAL
Best dual combo	+₹9,350	+₹78,098	₹+87,447
Current (single config)	-₹16,734	+₹47,785	₹+31,052
Improvement	+₹26,084	+₹30,313	+₹56,395 (2.8x)
The two configs:
Choppy config (C1): Small targets, tight SL

Index	Target	SL	BE Lock
NIFTY	5	5	3
BANKNIFTY	12	10	None
SENSEX	12	10	None
Trending config (T2): Bigger targets, wider SL

Index	Target	SL	BE Lock
NIFTY	10	8	5
BANKNIFTY	15	18	None
SENSEX	6	12	None
The trending config is interesting — BANKNIFTY gets a wider SL (18) than target (15), letting trades breathe. SENSEX gets a tiny target (6) with wide SL (12), scalping quick profits.



**How it works:**
1. Every day starts with the **choppy config** (smaller targets, tighter SLs, neutral exit ON)
2. After **2 consecutive winning trades** (across all indices), the engine switches to the **trending config** (wider SLs, bigger targets, neutral exit OFF) for the rest of the day
3. The switch is **one-way** — once upgraded, it stays on trending config until next day
4. Resets daily at midnight

**Why hybrid neutral exit?**
- **Choppy mode (neutral ON):** When the market is choppy, signals flip frequently. Exiting on neutral cuts small losses early instead of waiting for the full SL hit.
- **Trending mode (neutral OFF):** Once the market proves it's trending (2 wins), neutral exits hurt — they exit profitable trades prematurely during temporary signal dips. Letting trades run to target or SL produces bigger winners.

**Why start choppy?** On choppy days, losses are smaller (NIFTY SL=5 vs 8). On trending days, 2 quick wins happen fast → switch to bigger targets early. Choppy SL losses are the cheapest "detection cost".

**Backtester results (11 days):**

| Config | PnL | Win Rate | Green Days |
|--------|-----|----------|------------|
| **Adaptive + Hybrid Neutral** | **₹+68,296** | **59.7%** | **7/11** |
| Current single config | ₹+32,454 | 53.0% | 6/11 |
| Improvement | **+₹35,842 (+110%)** | **+6.7%** | **+1 day** |

**Exit reason breakdown (adaptive):**
- Choppy mode: 38 trades — 12 SIGNAL_NEUTRAL exits (₹-4,271), small controlled early exits
- Trending mode: 353 trades — 0 SIGNAL_NEUTRAL exits, trades run to target (213 TARGET_HITs = ₹+267K)

Configured in `config/trading_rules.json` under `adaptive_config`.

### Afternoon SELL-Only Filter (after 12:30)

After 12:30 PM IST, the engine only takes SELL signals (buys PE options). All BUY signals (CE entries) are blocked.

**Why this exists:**

Backtester analysis of 12 trading days revealed that BUY signals are fundamentally weaker than SELL signals. On BUY-dominant days (Jun 10, 18, 22), every configuration loses money — the engine fires BUY during flat/sideways periods where neither direction works. In contrast, SELL signals consistently produce profitable trades, especially in the afternoon session.

The root cause: Indian markets (NIFTY/BANKNIFTY/SENSEX) have a structural afternoon downward bias. Morning BUY traps — where the market rallies briefly, triggers BUY consensus, then reverses — are the #1 source of losses. By the afternoon, trends become clearer and SELL signals align with this natural drift.

**Key design decisions:**

1. **No confirmation wait** — Testing 3, 5, and 10-minute confirmation windows all reduced profits. SELL signals are already reliable; waiting delays entry into good moves. The anti-spike filter already handles bad entries.

2. **No streak block reset** — Morning streak blocks (3 losses or 2+₹3K per-index) are NOT reset at 12:30. Testing showed reset hurts by ₹17,655. Indices blocked in the morning were correctly blocked — they kept producing losers even with afternoon SELL signals.

3. **12:30 cutoff, not earlier** — 12:00 cutoff tested worse. Some profitable BUY trades happen between 12:00-12:30.

**Backtester proof (12 signal log days):**

| Config | Total PnL | Trades | Win Rate | Green Days |
|--------|-----------|--------|----------|------------|
| Adaptive baseline | ₹+57,666 | 462 | 59% | 8/12 |
| **Adaptive + PM SELL-only** | **₹+79,880** | **409** | **61%** | **9/12** |
| Improvement | **+₹22,214 (+39%)** | **-53** | **+2%** | **+1 day** |

**Day-by-day impact (biggest movers):**

| Day | Without Filter | With Filter | Delta | Why |
|-----|---------------|-------------|-------|-----|
| Jun 18 (BUY day) | ₹+1,079 | ₹+10,143 | **+₹9,064** | Afternoon BUY trap eliminated |
| Jun 10 (BUY day) | ₹-3,691 | ₹+2,382 | **+₹6,073** | Same — losing BUY trades blocked |
| Jun 17 (mixed) | ₹+10,506 | ₹+14,317 | **+₹3,811** | Bad afternoon BUY trades cut |
| Jun 11 (SELL day) | ₹+20,862 | ₹+22,400 | **+₹1,538** | Fewer losing BUY trades |

Fewer trades (409 vs 462) with higher win rate (62% vs 59%) — the filter removes 53 low-quality BUY trades without touching profitable SELL signals.

Configured in `config/trading_rules.json` under `afternoon_sell_only`. Set to `null` to disable.

---

## 4. Anti-Spike Filter — The Key Edge

### Why Anti-Spike Exists

When a signal appears (STRONG or MEDIUM), the ATM option premium often spikes immediately. If the engine buys at that spiked price, it enters at an inflated level and the premium quickly reverts — resulting in an instant SL hit or a losing trade even when the direction was correct.

### How It Works

```
For each index, the engine maintains a rolling window of the last 10 option prices.

On every entry attempt:
1. Append current ATM price to the rolling window
2. If fewer than 3 prices in window → BLOCK entry (warmup)
3. Take the last 5 prices (or fewer if < 5 available)
4. Calculate the average of that window
5. If current price > average + 1 point → SKIP entry (log "ANTI-SPIKE")
6. If price is within 1 point of average → allow entry to proceed

The window resets daily via _reset_daily().
```

### Anti-Spike Warmup

The engine **never allows blind entries**. Three layers ensure the price history is populated before any trade:

| Scenario | How it warms up | Ready by |
|---|---|---|
| **Start before 9:15** | `_warmup_price_hist()` collects live option prices during 9:15-9:20 (F&O open, engine not trading yet) | Before 9:20 |
| **Start at 9:20+** (fresh day) | Warmup blocking: first 3 ticks (~6 sec) per index are collected but no entry allowed | ~6 seconds |
| **Mid-day restart** | `_prefill_price_hist()` reads today's signal log, loads up to 10 prices per index (strike-aware — only from latest ATM strike) | Immediately |

### Premium Cap

High-premium (deep ITM) options have worse SL/target ratios. The engine skips entry if the option premium exceeds a per-index cap:

| Index | Max Premium | What happens |
|---|---|---|
| NIFTY | No cap | Always allowed |
| BANKNIFTY | ₹1,000 | Skip if ATM price ≥ ₹1,000 |
| SENSEX | ₹500 | Skip if ATM price ≥ ₹500 |

**Backtester proof (8 days):** Without premium cap = +₹37,040. With premium cap = **+₹44,371** (+20% improvement, 5/8 days better, 1 day worse, 2 neutral).

Configured in `config/trading_rules.json` under `max_premium`.

### Example

```
Rolling window: [152.3, 153.1, 152.8, 153.0, 152.5]
Average of last 5: 152.74

New price arrives: 154.2
Difference: 154.2 - 152.74 = 1.46 pts → EXCEEDS 1pt threshold → SKIP

Next tick: 153.1
Difference: 153.1 - 152.74 = 0.36 pts → WITHIN threshold → ALLOW ENTRY
```

### Why 1 Point?

Backtester tested thresholds of 1, 2, 3, and 5 points across 8 trading days:

| Threshold | 8-Day PnL | Days Profitable |
|-----------|-----------|------------------|
| No filter (baseline) | +₹528* | Variable |
| **1 point** | **+₹37,040** | **8/8** |
| 2 points | +₹33,461 | 8/8 |
| 3 points | +₹32,427 | 7/8 |
| 5 points | +₹32,090 | 7/8 |

*Baseline varies by day. 1 point is the tightest filter — it skips the most spike entries and produces the best results.

### Why Not Price Confirmation Alone?

The engine already has a 2-tick price confirmation step (price must be stable across 2 consecutive readings). But price confirmation checks if the price is *consistent* — anti-spike checks if the price is *elevated*. A price can be consistently high (spiked and staying there for 2 ticks) but still be a bad entry because it's above the recent average. Both filters serve different purposes and work together.

### Code Location

```python
# In auto_trader.py — Entry logic, after ATM price is obtained:

# Update rolling price history for anti-spike
hist = self._price_hist.setdefault(prefix, [])
hist.append(atm_price)
if len(hist) > 10:
    hist.pop(0)

# Premium cap: skip entry if option premium too expensive
prem_cap = MAX_PREMIUM.get(prefix)
if prem_cap and atm_price >= prem_cap:
    logger.info(f"PREMIUM-CAP: {option_name} ₹{atm_price} >= cap ₹{prem_cap} → SKIP")
    continue

# Anti-spike: need at least 3 prices before allowing any entry
if len(hist) < 3:
    logger.info(f"ANTI-SPIKE: {prefix} warming up ({len(hist)}/3 prices) → SKIP")
    continue
window = hist[-5:] if len(hist) >= 5 else hist
avg = sum(window) / len(window)
if atm_price > avg + 1:
    logger.info(f"ANTI-SPIKE: {option_name} ₹{atm_price} > avg ₹{avg:.2f} + 1pt → SKIP")
    continue
```

---

## 5. Entry Conditions (in order)

An auto-trade is placed when ALL of the following pass, checked in this exact sequence:

| # | Check | What happens if it fails |
|---|-------|--------------------------|
| 1 | Signal is BUY or SELL (not NEUTRAL) with strength STRONG or MEDIUM | Skip — no actionable signal |
| 2 | No open position exists for this index | Skip — one trade at a time per index |
| 3 | Signal strength has a matching rule in config | Skip — unknown strength |
| 4 | **Entry skip window** — not in 10:00-10:30 dead zone | Skip — digestion period |
| 5 | **Loss streak combo** — not blocked by consecutive losses | Skip — streak limit hit |
| 6 | **Afternoon SELL-only** — BUY blocked after 12:30 PM | Skip — afternoon BUY signals are unreliable |
| 7 | **Adaptive config** — use choppy or trending target/SL based on win streak | Uses current active config |
| 8 | Profit protection not active | Skip — protecting profits |
| 9 | ATM strike + price obtained atomically | Skip — no fresh price data |
| 10 | **Anti-spike filter** — price ≤ avg + 1pt | Skip — price is spiked |
| 11 | Sufficient capital available | Skip — can't afford the trade |
| 12 | 2-tick price confirmation (price stable across 2 readings) | Wait — store and retry next tick |
| 13 | Market hours (9:20 AM – 3:25 PM IST) | Skip — outside trading window |
| 14 | Kill switch not triggered (daily loss < ₹5,000) | Skip — daily loss limit hit |

> **What was removed (v1.5):** Cooldowns, max trade count, consecutive SL block, and momentum guard were all removed after backtester analysis proved they reduce profitability. Anti-spike is a better filter than any of these restrictions.

---

## 6. Exit Conditions

A trade is auto-closed when ANY of the following is true:

| Condition           | Action                                      |
|---------------------|---------------------------------------------|
| **Target hit**      | LTP ≥ buy_price + target_pts → SELL         |
| **Stop-loss hit**   | LTP ≤ buy_price - sl_pts → SELL             |
| **Breakeven exit**  | Breakeven locked + LTP ≤ buy_price → SELL (₹0 loss) |
| **Signal reversal** | BUY→SELL or SELL→BUY → Close (re-enter next tick) |
| **Signal NEUTRAL**  | Close position (choppy mode only — ignored in trending) |
| **EOD Exit**        | 3:25 PM IST → Close ALL open positions      |
| **Kill switch**     | Daily loss ≥ ₹5,000 → Close ALL, block new trades |
| **Manual stop**     | AUTO toggle OFF → Close all auto-traded positions |

### Breakeven Lock (NIFTY only)

Once a NIFTY trade gains +5 points from entry, the SL is permanently moved to the buy price (breakeven). This means:
- Best case: trade hits target (+10 pts)
- Worst case: trade exits at breakeven (₹0 loss instead of -8 pts)
- The lock is one-directional — once activated, it never reverts

> **Fallback:** If LTP is unavailable during Kill Switch, EOD Exit, or Manual Stop, the engine sells at `buy_price` (flat exit) to avoid positions staying open overnight.

---

## 7. Capital Management

### Starting Capital
- **₹1,00,000** (paper trading)

### Dynamic Lot Calculation
```
available_capital = total_capital - sum(open_position_costs)
max_lots = floor(available_capital / (ATM_price × lot_size))
lots = min(max_lots, 5)   # Capped at 5 lots per trade
```

### Priority Order (when capital is limited)
1. **NIFTY** — Most liquid, tightest spreads
2. **BANKNIFTY** — High movement, good returns
3. **SENSEX** — Least priority

---

## 8. Safety Controls

| Control              | Value                | Description                                  | Status |
|---------------------|----------------------|----------------------------------------------|--------|
| Market hours only   | **9:20 AM – 3:25 PM**| No trades outside this window                | Active |
| Pre-market warmup   | **9:15 – 9:20 AM**  | Collect option prices for anti-spike before trading | Active |
| EOD forced exit     | **3:25 PM IST**      | All positions closed, no overnight holding   | Active |
| Max lots per trade  | **5**                | Hard cap regardless of capital               | Active |
| Anti-spike filter   | **1 point**          | Skip entry if option price > 5-tick avg + 1pt | Active |
| Anti-spike warmup   | **3 ticks**          | Block entry until ≥3 prices collected per index | Active |
| Premium cap         | **BN<₹1K, SX<₹500** | Skip entry if option premium too high        | Active |
| Loss streak combo   | **3 losses OR 2+₹3K**| Block per-index entries on consecutive loss streaks | Active |
| Entry skip window   | **10:00–10:30**      | No new entries during opening range digestion | Active |
| Signal log prefill  | **On restart**       | Reload price history from today's signal log (strike-aware) | Active |
| Price confirmation  | **2 ticks**          | Entry price must be stable across 2 readings | Active |
| Breakeven lock      | **NIFTY: +5 pts**    | Once LTP ≥ buy+5, SL moves to breakeven     | Active |
| Adaptive config     | **Choppy→Trending**  | Start conservative, switch after 2 wins      | Active |
| Hybrid neutral exit | **Choppy=ON, Trend=OFF** | Neutral exit toggles with adaptive mode  | Active |
| Afternoon SELL-only | **After 12:30 PM**   | Block BUY entries in afternoon — SELL signals only | Active |
| OI Confirmation     | **OI rising check**  | Skip entry if OI declining for trade direction | Backtester |
| Volume Spike        | **1.5× avg**         | Skip entry if option volume below 1.5× rolling avg | Backtester |
| Buy/Sell Imbalance  | **1.3× ratio**       | Skip entry if buyer/seller ratio insufficient | Backtester |
| PCR Filter          | **0.7–1.3 range**    | Skip entry if Put/Call ratio contradicts direction | Backtester |
| Max daily loss      | **₹5,000**           | Kill switch — close all, block new trades    | Disabled |
| Profit protection   | **₹3,000 / ₹2,000** | If PnL peaks ≥ ₹3K then drops ₹2K → stop    | Disabled |

### What Was Removed in v1.5

| Removed Control     | Old Value            | Why Removed                                  |
|---------------------|----------------------|----------------------------------------------|
| Max trades/day      | 9                    | Backtester: max 9 = +₹10,606 vs unlimited = +₹26,849. Cap leaves ₹16K on table |
| SL cooldown         | 15 min               | Backtester: 15min cooldown = -₹4,232 vs no cooldown = +₹26,849. Blocks recovery trades |
| Target cooldown     | 5 min                | Same — prevents valid re-entries after profitable exit |
| Neutral cooldown    | 5 min                | Same — blocks re-entry when signal returns |
| Late session 2× mult | After 10:30 AM      | Doubled all cooldowns — removed along with cooldowns |
| Consecutive SL block | 2 per index          | Backtester: block after 2 SLs = +₹5,974 vs no block = +₹26,849. Blocks profitable recovery |
| Momentum guard      | Per-index             | Backtester: momentum guard = -₹4,109 vs no guard = +₹26,849. Blocks valid re-entries |

> **Why:** Cooldowns and trade limits were designed as safety nets for a system without good entry filtering. Anti-spike is a smarter filter — it prevents *bad entries* (spiked prices) rather than blindly blocking *all entries* including good ones.

---

## 9. Signal Strength Detection (Code Logic)

```python
# From server.py — Category-Level Consensus

def category_consensus(signals):
    """
    2 indicators: both must agree, BUY+NEUTRAL=BUY, conflict=NEUTRAL
    3 indicators: 2+ neutral=NEUTRAL, any conflict=NEUTRAL, else active direction
    """
    buy_c  = signals.count("BUY")
    sell_c = signals.count("SELL")
    neutral_c = signals.count("NEUTRAL")
    if buy_c > 0 and sell_c > 0:       return "NEUTRAL"  # conflict
    if len(signals) >= 3 and neutral_c >= 2: return "NEUTRAL"  # neutral majority
    if buy_c > 0:  return "BUY"
    if sell_c > 0: return "SELL"
    return "NEUTRAL"

trend_dir    = category_consensus([MA, EMA])              # 2 strategies
momentum_dir = category_consensus([RSI, MACD, Stoch])     # 3 strategies
strength_dir = category_consensus([Supertrend, ADX])      # 2 strategies

# Core rule: Trend + Strength must agree
if trend_dir in ("BUY", "SELL") and trend_dir == strength_dir:
    if momentum_dir == trend_dir:      → STRONG  (all 3 agree)
    elif momentum_dir == "NEUTRAL":    → MEDIUM  (Trend+Strength, Momentum sitting out)
    else:                              → NEUTRAL (Momentum opposes — don't trade)
else:
    → NEUTRAL (Trend & Strength don't align — don't trade)
```

---

## 10. How It Works (Tick-by-Tick Flow)

The engine runs as an async background task, ticking **every 2 seconds** via KiteTicker.

```
Every tick (~2 seconds, real-time):
│
├─ 1. Reset daily counters if new trading day
│     └─ Prefill anti-spike price history from signal log
│
├─ 2. EOD check → Is it ≥ 3:25 PM IST?
│     └─ Yes → Close all open positions, disable engine
│
├─ 3. Market hours check → 9:20 AM – 3:25 PM IST?
│     └─ No → If 9:15-9:20 → warmup (collect prices, no trades)
│     └─ Otherwise → Skip
│
├─ 4. For each index (NIFTY → BANKNIFTY → SENSEX):
│     │
│     ├─ Fetch signal (consensus, strength, VIX)
│     ├─ Log signal to signal_logs/YYYY-MM-DD.jsonl
│     │
│     ├─ 4a. HAS OPEN POSITION?
│     │     ├─ Get live LTP for the specific strike held
│     │     ├─ Breakeven lock → LTP ≥ buy + 5? → move SL to breakeven
│     │     ├─ Stop loss → LTP ≤ effective SL → SELL
│     │     ├─ Target → LTP ≥ buy + target → SELL
│     │     ├─ Signal reversed → SELL (re-enter next tick)
│     │     └─ Signal NEUTRAL → SELL (choppy mode) / IGNORE (trending mode)
│     │
│     └─ 4b. NO OPEN POSITION?
│           ├─ Signal = NEUTRAL/NONE? → skip
│           ├─ Entry skip window (10:00-10:30)? → skip
│           ├─ Loss streak combo active? → skip
│           ├─ Afternoon SELL-only (after 12:30, BUY blocked)? → skip
│           ├─ Profit protection active? → skip
│           ├─ Get ATM strike + price (atomic snapshot)
│           ├─ Premium cap → price ≥ index cap? → skip
│           ├─ Anti-spike warmup → < 3 prices? → skip
│           ├─ Capital check → can afford? → skip if not
│           ├─ Price confirmation → stable across 2 ticks? → wait if not
│           └─ All clear → BUY ATM option
│
└─ 5. Sleep 2 seconds → repeat
```

---

## 11. Dashboard Integration

- **AUTO toggle** on dashboard enables/disables auto-trading
- When AUTO is ON:
  - Manual BUY/SELL buttons disabled (engine controls trades)
  - "AUTO" badge shown on trade tiles
  - All trades logged same as manual (visible in Trades page)
- When AUTO is OFF:
  - Engine calls `stop()` → closes all open auto-traded positions (reason: `MANUAL_STOP`)
  - Manual trades are untouched
  - Manual BUY/SELL buttons re-enabled

### Background Option Subscriber

A background async task (`_subscribe_all_index_options`) runs independently of the dashboard:

- Runs every 5 seconds, loops through all 3 indices
- For each: reads spot price → calculates ATM strike → subscribes ATM CE/PE to KiteTicker
- Ensures auto-trader has fresh option prices for all indices, not just the one being viewed
- No dependency on browser being open

---

## 12. Signal Logger

The engine writes a full signal log every 2 seconds for post-market analysis:

```
backend/data/signal_logs/YYYY-MM-DD.jsonl
```

Each line is one JSON record per index per tick:
```json
{
  "ts": "10:05:32",
  "index": "NIFTY",
  "consensus": "SELL",
  "strength": "MEDIUM",
  "vix": 16.95,
  "spot_price": 23218.2,
  "market": {"NIFTY": 23218.2, "BANKNIFTY": 54256.6, "SENSEX": 73780.29},
  "atm_strike": 23200,
  "ce_price": 184.5,
  "pe_price": 147.2,
  "ce_oi": 1250000,
  "pe_oi": 980000,
  "ce_volume": 45000,
  "pe_volume": 32000,
  "ce_buy_qty": 12000,
  "ce_sell_qty": 8500,
  "pe_buy_qty": 7000,
  "pe_sell_qty": 11000,
  "strategies": [
    {"name": "MA(5)", "signal": "SELL"},
    {"name": "RSI(7)", "signal": "NEUTRAL"},
    {"name": "MACD(5,13,1)", "signal": "NEUTRAL"},
    {"name": "EMA(5,13)", "signal": "SELL"},
    {"name": "Supertrend(7,2)", "signal": "SELL"},
    {"name": "Stoch(5,3,3)", "signal": "NEUTRAL"},
    {"name": "ADX(14)", "signal": "SELL"}
  ],
  "open_trade": null,
  "cooldown": false,
  "blocked": false,
  "daily_pnl": -2681.0,
  "trade_count": 2
}
```

### OI / Volume Fields (added v1.9)

Starting v1.9, every signal log record includes real-time OI and volume data from KiteTicker MODE_FULL:

| Field | Source | What It Tells You |
|-------|--------|--------------------|
| `ce_oi` | ATM CE open interest | How many CE contracts are outstanding |
| `pe_oi` | ATM PE open interest | How many PE contracts are outstanding |
| `ce_volume` | ATM CE traded volume | How actively CE is being traded today |
| `pe_volume` | ATM PE traded volume | How actively PE is being traded today |
| `ce_buy_qty` | ATM CE total buy quantity in order book | Buyer aggression for CE |
| `ce_sell_qty` | ATM CE total sell quantity in order book | Seller aggression for CE |
| `pe_buy_qty` | ATM PE total buy quantity in order book | Buyer aggression for PE |
| `pe_sell_qty` | ATM PE total sell quantity in order book | Seller aggression for PE |

These fields are **absent in signal logs before 25 Jun 2026**. The backtester handles this gracefully — OI/volume filters skip when data is missing.

### Use Cases
- Replay a full trading day with different entry rules (backtester)
- Detect opening range direction
- Count signal flips (choppy day detection)
- Correlate VIX levels with win/loss outcomes
- Test parameter changes without waiting for next market day
- **Analyze OI buildup vs price movement** (new: detect short covering traps, fresh position building)
- **Volume spike correlation** (new: identify entries with real momentum vs noise)

---

## 13. Backtester (`backtest_signal_logs.py`)

The backtester replays signal log data through different variant configurations to compare strategies. It simulates one trade at a time per index using the same entry/exit logic as the real engine.

### Key Features
- Runs independently per index (NIFTY, BANKNIFTY, SENSEX in parallel)
- Uses the same SL/target/breakeven logic as the real engine
- No cooldown, no max-trades — unlimited trading to measure raw signal quality
- Anti-spike filter with configurable threshold
- 4-second minimum gap after exit to prevent same-tick re-entry
- **OI/Volume confirmation filters** (v1.9): `oi_confirm`, `vol_spike_mult`, `imbalance_ratio`, `pcr_filter`

### OI/Volume Backtester Variants (v1.9)

| Variant | Desc | Filters Used |
|---------|------|--------------|
| ZL_oi_confirm | Adaptive + OI confirmation | `oi_confirm: true` |
| ZM_vol_spike | Adaptive + volume spike | `vol_spike_mult: 1.5` |
| ZN_imbalance | Adaptive + buy/sell imbalance | `imbalance_ratio: 1.3` |
| ZO_pcr_filter | Adaptive + PCR filter | `pcr_filter: {min_for_buy: 0.7, max_for_sell: 1.3}` |
| ZP_all_oi_vol | Adaptive + ALL OI/vol filters combined | All 4 filters active |

These variants are identical to ZK_adaptive on signal logs before 25 Jun 2026 (no OI data available). Starting 25 Jun, they will produce different trade counts and PnL as the filters activate.

### Proven Results (6 trading days: Jun 8–15, 2026)
| Configuration | 6-Day PnL | Win Rate | Key Insight |
|--------------|-----------|----------|-------------|
| Baseline (no filters) | -₹1,504 | 46% | Raw signals lose money |
| Anti-spike 1pt | **+₹26,849** | 50% | Best performer, 6/6 profitable days |
| Anti-spike 2pt | +₹23,651 | 49% | Good but less selective |
| + 15min cooldown | -₹4,232 | 37% | Cooldown destroys performance |
| + Max 9 trades | +₹10,606 | 53% | Leaves ₹16K on the table |
| + Consec SL block (2) | +₹5,974 | 49% | Blocks profitable recovery trades |
| + Momentum guard | -₹4,109 | 38% | Blocks valid re-entries |

---

## 14. Loss Streak Combo Filter

A per-index entry filter that blocks new trades when consecutive losses pile up. Unlike the old "consecutive SL block" (removed in v1.5), this uses a **combo rule** that's both amount-aware and count-aware.

### How It Works

After each trade closes, the engine records the PnL per index. Before every new entry, it walks backward through the closed trades until it finds a win (PnL ≥ 0). The consecutive loss count and total loss amount determine whether to block:

| Trigger | Condition | Example |
|---------|-----------|---------|
| **Count trigger** | 3+ consecutive losses regardless of amount | 3 small losses of ₹200 each → blocked |
| **Amount trigger** | 2+ consecutive losses totaling ≥ ₹3,000 | 2 losses of ₹1,800 + ₹1,500 = ₹3,300 → blocked |
| **Single loss** | Never triggers | 1 loss of ₹5,000 → NOT blocked |
| **Reset** | Any win (PnL ≥ 0) resets the streak | Win after 2 losses → clean slate |

### Why This Works

The old "block after 2 SLs" was too aggressive — it blocked profitable recovery trades and cost ₹20K+ over 6 days. The streak combo is smarter:
- Single losses are normal trading — don't react
- 2 small losses are fine — the 3rd might be the recovery
- 2+ losses totaling ₹3K+ means the index is bleeding — stop trading it
- 3 consecutive losses of any size means the signal is wrong — stop

### Configuration

```json
// config/trading_rules.json
"loss_streak": {
    "max_consecutive_losses": 3,
    "max_streak_amount": 3000,
    "min_losses_for_amount": 2
}
```

### Code Logic

```python
# In auto_trader.py — _is_streak_blocked(prefix)
def _is_streak_blocked(self, prefix: str) -> bool:
    closed = self._daily_closed.get(prefix, [])
    count, total_loss = 0, 0
    for pnl in reversed(closed):
        if pnl >= 0:
            break
        count += 1
        total_loss += abs(pnl)
    if count >= LOSS_STREAK['max_consecutive_losses']:
        return True
    if (count >= LOSS_STREAK['min_losses_for_amount']
            and total_loss >= LOSS_STREAK['max_streak_amount']):
        return True
    return False
```

### Backtester Proof

**Signal log replay (9 days):**
| Metric | Without Streak | With Streak | Diff |
|--------|---------------|-------------|------|
| Trades | ~350 | 300 | -14% |
| Win Rate | ~48% | 52% | +4% |
| Total PnL | -₹3,858 | **+₹23,327** | +₹27,185 |
| NIFTY | — | +₹11,658 | — |
| BANKNIFTY | -₹30,444 | -₹2,404 | +₹28,040 |
| SENSEX | — | +₹14,074 | — |

**Real trades validation (all-time, 930 trades baseline):**
| Metric | Without Streak | With Streak | Diff |
|--------|---------------|-------------|------|
| Trades | 930 | 617 | -34% |
| Total PnL | +₹1,13,890 | **+₹1,70,545** | **+₹56,655** |

The filter is most impactful on BANKNIFTY, which tends to have extended loss runs. It cuts losing streaks short while still allowing full participation during winning periods.

---

## 15. Entry Skip Window (10:00–10:30)

A time-based entry filter that blocks all new trades during the 10:00–10:30 window — the "opening range digestion" period.

### Why 10:00–10:30?

Analysis of 954 auto-trades across 45 trading days shows this is the worst 30-minute slot:

| Time Slot | Trades | Win Rate | Total PnL | Avg PnL |
|-----------|--------|----------|-----------|---------|
| 09:30–10:00 | 65 | **57%** | **+₹1,42,153** | +₹2,187 |
| **10:00–10:30** | **71** | **35%** | **-₹14,769** | **-₹208** |
| 10:30–11:00 | 76 | 50% | +₹25,644 | +₹337 |
| 11:00–11:30 | 61 | 59% | +₹21,314 | +₹349 |

The opening momentum (9:20–10:00) exhausts around 10:00. The market then digests the move — reverses, chops, and false-signals — before the next trend forms around 10:30+. Trading in this window has a 35% win rate and loses ₹14,769 in aggregate.

### Configuration

```json
// config/trading_rules.json
"entry_skip_window": ["10:00", "10:30"]
```

Set to `null` to disable.

### Combined with Streak Filter (Backtester Proof, 10 days)

| Variant | 10-Day PnL | Trades |
|---------|-----------|--------|
| No filters | +₹8,190 | 487 |
| Streak only | +₹34,940 | 236 |
| Skip 10:00–10:30 only | +₹22,539 | 483 |
| **Streak + Skip 10:00–10:30** | **+₹41,468** | **269** |

The combo is the best total — streak blocks loss spirals, time skip avoids the dead zone that often triggers early streaks.

### Real Trades Validation (45 days, 954 trades)

Removing the 71 trades entered in 10:00–10:30: **+₹1,27,269 → +₹1,42,038 (+₹14,769)**. Better on 10 days, worse on 3, neutral on 31.

---

## 16. Paper Trading Mode

- **No real Zerodha orders** are placed
- Trades logged to `trades.json` with real live prices from KiteTicker
- Buy at ATM option LTP at time of signal
- Sell at ATM option LTP when exit condition triggers
- P&L calculated: `(sell_price - buy_price) × quantity`
- Visible on Trades page alongside manual trades (tagged as `auto: true`)

---

## 17. Future: Live Trading (Phase 2)

When paper trading proves profitable:
- Flip `mode: "live"` in `trading_rules.json`
- Uses `kite.place_order()` for real order placement
- Order type: MARKET (for speed) or LIMIT
- Requires proper margin in Zerodha account
- Same rules, same safety controls
- Additional: Order confirmation + rejection handling

---

## Changelog

### v1.9 — 24 Jun 2026
- **Added** OI/Volume data logging to signal logs (8 new fields: ce_oi, pe_oi, ce_volume, pe_volume, ce_buy_qty, ce_sell_qty, pe_buy_qty, pe_sell_qty)
- **Added** `_auto_get_oi_volume_snapshot()` in server.py — reads OI, volume, buy/sell qty from KiteTicker MODE_FULL ticks already in `_tick_store`
- **Added** `_dashboard_options` now stores OI, volume, buy_qty, sell_qty alongside LTP for ATM options
- **Added** 4 new backtester entry filters: OI confirmation (`oi_confirm`), volume spike (`vol_spike_mult`), buy/sell imbalance (`imbalance_ratio`), PCR filter (`pcr_filter`)
- **Added** 5 new backtester variants (ZL–ZP) testing OI/volume filters individually and combined
- **Why:** The 7 strategy indicators are all lagging (price-based). OI, volume, and order book depth are leading/confirming signals that show institutional positioning in real-time. Professional traders use OI buildup + volume confirmation before entering — this automates exactly that.
- **Key insight:** KiteTicker MODE_FULL was already streaming OI, volume, buy_quantity, sell_quantity, and 5-level depth for all subscribed ATM options every 2 seconds. The engine was storing the full tick dict but only reading `last_price`. Zero additional API cost — just reading fields already available.
- **Data availability:** OI/volume fields present in signal logs from 25 Jun 2026 onwards. Backtester gracefully skips filters when data is absent (old logs).
- **Status:** Backtester only — will be promoted to live engine after validation on live OI data.

### v1.8 — 23 Jun 2026
- **Added** afternoon SELL-only filter (BUY signals blocked after 12:30 PM, SELL-only in afternoon)
- **Why:** BUY signals are the engine's #1 loss source. 12-day analysis: every BUY-dominant day loses money. Morning BUY traps cause most damage; afternoon SELL signals align with Indian market's structural downward bias.
- **Tested and rejected:** 5-min confirmation wait (reduces profit by ₹30K), streak reset at 12:30 (costs ₹17K), 12:00 cutoff (too early)
- **Backtester validated:** +₹79,880 (12 days) vs ₹+57,666 baseline adaptive (**+39%, +₹22K**), 61% WR, 9/12 green days
- **Config:** `afternoon_sell_only` added to `trading_rules.json`

### v1.7 — 22 Jun 2026
- **Added** adaptive dual-config system (choppy → trending after 2 consecutive wins)
- **Added** hybrid neutral exit (ON in choppy mode, OFF in trending mode)
- **Fixed** p >= 0 bug in adaptive switch trigger (₹0 breakeven counted as "win" → premature switch)
- **Backtester validated:** +₹68,296 (11 days) vs ₹+32,454 single config (**+110% improvement**)
- **Config:** `adaptive_config` section added to `trading_rules.json`

### v1.6 — 18 Jun 2026
- **Added** loss streak combo filter (3 consecutive losses OR 2+ losses totaling ≥₹3K → block per-index)
- **Added** entry skip window (10:00–10:30 dead zone, configurable)
- **Backtester validated:** streak combo saves +₹22K over 10 signal log days; skip window saves +₹14K over 45 real trading days; combo = +₹41K (10 days)
- **Config:** `loss_streak` and `entry_skip_window` blocks added to `trading_rules.json`

### v1.5 — 15 Jun 2026
- **Added** anti-spike filter (1pt threshold, rolling 5-tick average)
- **Removed** all cooldowns (SL, target, neutral, late-session multiplier)
- **Removed** max trades per day limit (was 9)
- **Removed** consecutive SL block (was 2 per index → block for day)
- **Removed** momentum guard (was skip if premium < last buy on same strike)
- **Backtester validated:** 6 days of signal log data, anti-spike 1pt = +₹26,849 (6/6 profitable)

### v1.4 — 8 Jun 2026
- Added signal logger (JSONL per day)
- Added breakeven lock (NIFTY: +5 pts → SL to breakeven)
- Fixed momentum check cross-strike bug

### v1.3
- Added per-index target/SL rules
- Added 2-tick price confirmation
- Added consecutive SL block

### v1.2
- Added profit protection (peak ₹3K, drawdown ₹2K)
- Added momentum weakening guard

### v1.1
- Initial auto-trading engine with cooldowns and trade limits
