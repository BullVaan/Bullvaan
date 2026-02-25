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

### STRONG Signal
- **Trend**: ALL 2 strategies agree (BUY or SELL)
- **Momentum**: At least 2 of 3 agree with same direction
- **Strength**: ALL 2 strategies agree
- **Basically**: All 3 category tiles show same direction

### MEDIUM Signal
- **Trend**: ALL 2 strategies agree
- **Strength**: ALL 2 strategies agree
- **Momentum**: Mostly NEUTRAL (2+ neutral)
- **Basically**: Trend + Strength aligned, Momentum sitting out

### WEAK Signal (⚠️ "Use Stop Loss" alert)
- **Trend+Strength**: 3 of 4 agree on direction
- **Momentum**: Opposes direction (2+ opposite)
- **Basically**: `stop_loss_warning = True` in our consensus logic
- Current code: Momentum says opposite but Trend+Strength overrides

---

## 3. Trading Rules

### Rule 1 — Strong Signal
| Parameter       | Value            |
|----------------|------------------|
| Signal Type    | STRONG           |
| Target Profit  | **20 pts** (₹)   |
| Stop Loss      | **10 pts** (₹)   |
| Risk:Reward    | 1:2              |
| Re-entry       | ✅ Yes, after 5-min cooldown |
| Action         | Buy ATM CE (BUY) or ATM PE (SELL) |

### Rule 2 — Medium Signal
| Parameter       | Value            |
|----------------|------------------|
| Signal Type    | MEDIUM           |
| Target Profit  | **12 pts** (₹)   |
| Stop Loss      | **10 pts** (₹)   |
| Risk:Reward    | 1:1.2            |
| Re-entry       | ✅ Yes, after 5-min cooldown |
| Action         | Buy ATM CE (BUY) or ATM PE (SELL) |

### Rule 3 — Weak Signal
| Parameter       | Value            |
|----------------|------------------|
| Signal Type    | WEAK (⚠️ Use SL) |
| Target Profit  | **10 pts** (₹)   |
| Stop Loss      | **8 pts** (₹)    |
| Risk:Reward    | 1:1.25           |
| Re-entry       | ❌ No             |
| Action         | Buy ATM CE (BUY) or ATM PE (SELL) |

---

## 4. Entry Conditions

An auto-trade is placed when ALL of the following are true:

1. Signal strength is STRONG, MEDIUM, or WEAK (not NEUTRAL)
2. No open position already exists for that index
3. Sufficient capital available (ATM price × lot size × lots ≤ available capital)
4. Current time is between **9:20 AM – 3:15 PM IST**
5. Daily trade count < 15
6. Daily loss has not hit the kill switch (₹5,000)
7. Cooldown period has passed (5 min for Strong/Medium after SL hit)

---

## 5. Exit Conditions

A trade is auto-closed when ANY of the following is true:

| Condition           | Action                                      |
|---------------------|---------------------------------------------|
| **Target hit**      | LTP ≥ buy_price + target_pts → SELL         |
| **Stop-loss hit**   | LTP ≤ buy_price - sl_pts → SELL             |
| **Signal reversal** | BUY→SELL or SELL→BUY → Close, then re-enter |
| **Signal NEUTRAL**  | Close position                              |
| **EOD Exit**        | 3:15 PM IST → Close ALL open positions      |
| **Kill switch**     | Daily loss ≥ ₹5,000 → Close ALL, stop engine|

---

## 6. Capital Management

### Starting Capital
- **₹1,00,000** (paper trading)

### Allocation Strategy (Option B)
| Index      | Lot Size | Default Lots | ~Cost per trade |
|-----------|----------|-------------|-----------------|
| NIFTY      | 65       | 3           | ~₹30,000        |
| BANKNIFTY  | 30       | 1           | ~₹27,000        |
| SENSEX     | 20       | 3           | ~₹19,000        |
| **Total**  |          |             | **~₹76,000**    |
| **Buffer** |          |             | **~₹24,000**    |

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
| Max daily loss      | **₹5,000**           | Kill switch — close all, stop engine for day |
| Market hours only   | **9:20 AM – 3:15 PM**| No trades outside this window                |
| EOD forced exit     | **3:15 PM IST**      | All positions closed, no overnight holding   |
| Cooldown (Strong)   | **5 minutes**        | Wait after SL hit before re-entry            |
| Cooldown (Medium)   | **5 minutes**        | Wait after SL hit before re-entry            |
| Cooldown (Weak)     | **No re-entry**      | One shot only                                |
| Max lots per trade  | **5**                | Hard cap regardless of capital               |


---

## 8. Signal Strength Detection (Code Logic)

```python
# From server.py consensus logic:

trend_signals   = ["MA(5)", "EMA(5,13)"]         # 2 strategies
momentum_signals = ["RSI(7)", "MACD(5,13,1)", "Stoch(5,3,3)"]  # 3 strategies  
strength_signals = ["Supertrend(7,2)", "ADX(14)"]  # 2 strategies

# STRONG: All categories agree
if trend_all_agree AND momentum_2of3_agree AND strength_all_agree:
    signal_strength = "STRONG"

# MEDIUM: Trend + Strength agree, Momentum neutral
elif trend_all_agree AND strength_all_agree AND momentum_mostly_neutral:
    signal_strength = "MEDIUM"

# WEAK: stop_loss_warning = True (Trend+Strength overrides opposing Momentum)
elif stop_loss_warning == True:
    signal_strength = "WEAK"
```

---

## 9. How It Works (Flow)

```
Every tick (real-time via KiteTicker):
│
├─ 1. Check time → Is it 9:20 AM – 3:15 PM?
│     └─ No → If 3:15+ → Close all open positions
│
├─ 2. Check kill switch → Daily loss ≥ ₹5,000?
│     └─ Yes → Close all, stop engine
│
├─ 3. For each index (NIFTY, BANKNIFTY, SENSEX):
│     │
│     ├─ 3a. Has open position?
│     │     ├─ Check SL → LTP ≤ buy_price - SL → SELL
│     │     ├─ Check Target → LTP ≥ buy_price + target → SELL
│     │     ├─ Check signal → reversed? → SELL (+ re-enter)
│     │     └─ Check signal → NEUTRAL? → SELL
│     │
│     └─ 3b. No open position?
│           ├─ Get signal strength (STRONG/MEDIUM/WEAK/NEUTRAL)
│           ├─ Check capital availability
│           ├─ Check cooldown timer
│           ├─ Check trade count < 15
│           └─ All clear? → BUY ATM option
│
└─ 4. Log everything → trades.json + console
```

---

## 10. Dashboard Integration

- **AUTO toggle** on dashboard to enable/disable auto-trading
- When AUTO is ON:
  - Manual BUY/SELL buttons disabled (engine controls trades)
  - "AUTO" badge shown on trade tile
  - All trades logged same as manual (visible in Trades page)
- When AUTO is OFF:
  - Engine stops monitoring
  - Existing open positions stay open (manual control)
  - Manual BUY/SELL buttons re-enabled

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

*Last updated: 25 Feb 2026*
*Engine version: 1.0 (Paper Trading)*
