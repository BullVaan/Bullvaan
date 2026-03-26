# Bullvaan Auto-Trading Engine — Rules & Design

> Paper Trading Mode | Capital: ₹1,00,000 | Market: NSE/BSE Options

---

## 1. Strategy Categories

| Category     | Strategies              | Count | Purpose              |
|-------------|-------------------------|-------|----------------------|
| **Trend**     | MA(5), EMA(5,13)        | 2     | Direction of trend   |
| **Momentum**  | RSI(7), MACD(5,13,1), Stoch(5,3,3) | 3 | Speed of movement |
| **Strength**  | Supertrend(7,2), ADX(14) | 2    | Trend reliability    |

---

## 2. Signal Strength Classification

### Core Rule: Trend + Strength Must Agree

**Trend** and **Strength** are the two structural categories — they must both point in the same direction (BUY or SELL) for any trade signal.

**Momentum** acts as a confirmer — it must either agree or stay neutral. If Momentum opposes, no trade.

#### Per-Category Rules (unchanged)
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

### Rule 1 — Strong Signal
| Parameter       | Value            |
|----------------|------------------|
| Signal Type    | STRONG           |
| Target Profit  | **20 pts** (₹)   |
| Stop Loss      | **10 pts** (₹)   |
| Risk:Reward    | 1:2              |
| Re-entry       | ✅ Yes, cooldown: 3 min (target), 5 min (SL) |
| Action         | Buy ATM CE (BUY) or ATM PE (SELL) |

### Rule 2 — Medium Signal
| Parameter       | Value            |
|----------------|------------------|
| Signal Type    | MEDIUM           |
| Target Profit  | **12 pts** (₹)   |
| Stop Loss      | **10 pts** (₹)   |
| Risk:Reward    | 1:1.2            |
| Re-entry       | ✅ Yes, cooldown: 3 min (target), 5 min (SL) |
| Action         | Buy ATM CE (BUY) or ATM PE (SELL) |

> **Note:** Only two signal strengths exist: STRONG and MEDIUM. Trend + Strength agreement is the non-negotiable foundation.

---

## 4. Entry Conditions

An auto-trade is placed when ALL of the following are true:

1. Signal strength is STRONG or MEDIUM (not NEUTRAL/NONE)
2. No open position already exists for that index
3. Sufficient capital available (ATM price × lot size × lots ≤ available capital)
4. Current time is between **9:20 AM – 3:25 PM IST**
5. Daily trade count < 15
6. Daily loss has not hit the kill switch (₹5,000)
7. Cooldown period has passed (5 min after SL, 3 min after target, 2 min after NEUTRAL exit)
8. 2-tick price confirmation passes (entry price must be consistent across 2 consecutive ticks)

---

## 5. Exit Conditions

A trade is auto-closed when ANY of the following is true:

| Condition           | Action                                      |
|---------------------|---------------------------------------------|
| **Target hit**      | LTP ≥ buy_price + target_pts → SELL + 3min cooldown |
| **Stop-loss hit**   | LTP ≤ buy_price - sl_pts → SELL + 5min cooldown |
| **Signal reversal** | BUY→SELL or SELL→BUY → Close (re-enter next tick) |
| **Signal NEUTRAL**  | Close position + 2min cooldown               |
| **EOD Exit**        | 3:25 PM IST → Close ALL open positions      |
| **Kill switch**     | Daily loss ≥ ₹5,000 → Close ALL, block new trades (engine stays in idle loop) |
| **Manual stop**     | AUTO toggle OFF → Close all auto-traded positions (reason: `MANUAL_STOP`) |

> **Fallback:** If LTP is unavailable during Kill Switch, EOD Exit, or Manual Stop, the engine sells at `buy_price` (flat exit) to avoid positions staying open.

---

## 6. Capital Management

### Starting Capital
- **₹1,00,000** (paper trading)

### Allocation Strategy
| Index      | Lot Size | Max Lots | Lot calculation |
|-----------|----------|----------|------------------|
| NIFTY      | 65       | 5        | Dynamic (based on available capital) |
| BANKNIFTY  | 30       | 5        | Dynamic (based on available capital) |
| SENSEX     | 20       | 5        | Dynamic (based on available capital) |

### Dynamic Lot Calculation
```
available_capital = total_capital - sum(open_position_costs)
max_lots = floor(available_capital / (ATM_price × lot_size))
lots = min(max_lots, 5)   # Capped at 5 lots
```

### Priority Order (when capital is limited)
1. **NIFTY** — Most liquid, tightest spreads
2. **BANKNIFTY** — High movement, good returns
3. **SENSEX** — Least priority

---

## 7. Safety Controls

| Control              | Value                | Description                                  |
|---------------------|----------------------|----------------------------------------------|
| Max trades/day      | **15**               | No new trades after 15th                     |
| Max daily loss      | **₹5,000**           | Kill switch — close all, block new trades    |
| Market hours only   | **9:20 AM – 3:25 PM**| No trades outside this window                |
| EOD forced exit     | **3:25 PM IST**      | All positions closed, no overnight holding   |
| Cooldown (SL hit)   | **5 minutes**        | Wait after stop-loss before re-entry         |
| Cooldown (target)   | **3 minutes**        | Wait after target hit before re-entry        |
| Cooldown (NEUTRAL)  | **2 minutes**        | Wait after NEUTRAL exit before re-entry      |
| Max lots per trade  | **5**                | Hard cap regardless of capital               |


---

## 8. Signal Strength Detection (Code Logic)

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

## 9. How It Works (Flow)

The engine runs as an async background task, ticking **every 2 seconds** (`asyncio.sleep(2)`).

```
Every tick (~2 seconds, real-time via KiteTicker):
│
├─ 1. Reset daily counters if new trading day
│
├─ 2. Check kill switch → Daily loss ≥ ₹5,000?
│     └─ Yes → Close all, block new trades (idle loop)
│
├─ 3. Check EOD → Is it ≥ 3:25 PM?
│     └─ Yes → Close all open positions
│
├─ 4. Check market hours → Is it 9:20 AM – 3:25 PM?
│     └─ No → Skip trading
│
├─ 5. For each index (NIFTY, BANKNIFTY, SENSEX — priority order):
│     │
│     ├─ 5a. Has open position?
│     │     ├─ Check SL → LTP ≤ buy_price - SL → SELL + 5min cooldown
│     │     ├─ Check Target → LTP ≥ buy_price + target → SELL + 3min cooldown
│     │     ├─ Check signal → reversed? → SELL (+ re-enter)
│     │     └─ Check signal → NEUTRAL? → SELL + 2min cooldown
│     │
│     └─ 5b. No open position?
│           ├─ Get signal strength (STRONG/MEDIUM/NEUTRAL)
│           ├─ Check trade count < 15
│           ├─ Check cooldown timer
│           ├─ Calculate ATM strike (nearest 50 for NIFTY, 100 for BANKNIFTY/SENSEX)
│           ├─ Check capital availability (needs ATM price to calculate lots)
│           ├─ 2-tick price confirmation (entry price must match across 2 ticks)
│           └─ All clear? → BUY ATM option
│
└─ 6. Log everything → trades.json + console
```

---

## 10. Dashboard Integration

- **AUTO toggle** on dashboard to enable/disable auto-trading
- When AUTO is ON:
  - Manual BUY/SELL buttons disabled (engine controls trades)
  - "AUTO" badge shown on trade tile
  - All trades logged same as manual (visible in Trades page)
- When AUTO is OFF:
  - Engine calls `stop()` → closes all open **auto-traded** positions (reason: `MANUAL_STOP`)
  - Manual trades are untouched
  - Manual BUY/SELL buttons re-enabled

### Background Option Subscriber

A background async task (`_subscribe_all_index_options`) starts automatically on server startup. It runs independently of the dashboard:

- **Runs every 5 seconds**, loops through all 3 indices (NIFTY, BANKNIFTY, SENSEX)
- For each index: reads spot price from tick store → calculates ATM strike → subscribes ATM CE/PE tokens to KiteTicker → updates `_dashboard_options` from tick store
- This ensures the auto-trader has fresh option prices for **all indices**, not just the one currently viewed on the dashboard
- The frontend WebSocket still updates `_dashboard_options` for the viewed index (every ~1s, fresher) — the background task fills in the other two
- No dependency on browser being open or on any specific page

---

## 11. Paper Trading Mode

- **No real Zerodha orders** are placed
- Trades are logged to `trades.json` with real live prices from KiteTicker
- Buy at ATM option LTP at time of signal
- Sell at ATM option LTP when exit condition triggers
- P&L calculated: `(sell_price - buy_price) × quantity`
- Visible on Trades page alongside manual trades (tagged as `auto: true`)

---

## 12. Future: Live Trading (Phase 2)

When paper trading proves profitable, flip `mode: "live"`:
- Uses `kite.place_order()` for real order placement
- Order type: MARKET (for speed) or LIMIT
- Requires proper margin in Zerodha account
- Same rules, same safety controls
- Additional: Order confirmation + rejection handling

---

*Last updated: 11 Mar 2026*
*Engine version: 1.3 (Paper Trading — Background Option Subscriber)*
