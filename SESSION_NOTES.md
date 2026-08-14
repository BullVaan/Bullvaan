# Bullvaan — Session Notes
> Last updated: 2026-08-14  
> This file captures everything built, every decision made, and all open tasks.  
> Read this file first when starting a new session or on a new machine.

---

## 1. Project Overview

**Bullvaan** is a personal algorithmic trading platform for Indian markets (NIFTY, BANKNIFTY, SENSEX).

- **Backend**: Python FastAPI (`backend/`) running on port 8000
- **Frontend**: React (`frontend/`) running on port 3000, proxied to backend
- **Broker**: Zerodha Kite Connect API
- **Auth**: Supabase (user login/signup)
- **Theme**: Dark — background `#020617`, cards `#0f172a`

---

## 2. How to Start the Project

### Backend
```bash
cd backend
source venv/bin/activate
uvicorn api.server:app --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm start
```

### Zerodha Access Token (must be refreshed every day)
```bash
cd backend
source venv/bin/activate
python3 utils/generate_access_token.py
# Paste the URL in browser → login → copy request_token from redirect URL → paste back
# Copy the access_token printed → paste into .env as ACCESS_TOKEN=xxxx
```

### .env file location: `backend/.env`
```
API_KEY=your_zerodha_api_key
API_SECRET=your_zerodha_api_secret
ACCESS_TOKEN=refreshed_each_day
SUPABASE_URL=...
SUPABASE_KEY=...
```

---

## 3. Premarket Strategy — "Bulls Approach"

### Concept
Every morning, GIFT NIFTY trades before Indian markets open.  
We use GIFT NIFTY's gap vs. NIFTY's previous close to predict market direction and place an options trade.

### Signal Rules
| Condition | Action |
|---|---|
| `\|gap\| < 30 pts` | FLAT — no trade |
| `gap > 30 pts` | BULLISH — buy NIFTY CE (ITM_100) |
| `gap < -30 pts` | BEARISH — buy NIFTY PE (ITM_100) |
| `\|gap\| ≥ 150 pts` | Strong signal → enter at **9:15 AM** |
| `30 ≤ \|gap\| < 150 pts` | Moderate signal → enter at **9:20 AM** |

### Strike Selection
- **BULLISH CE**: ATM − 100 pts (ITM_100 call, one strike in the money)
- **BEARISH PE**: ATM + 100 pts (ITM_100 put, one strike in the money)
- Strike is always computed from the **9:15 AM spot price**, even if entry is at 9:20

### T/SL Per Index
| Index | Lot Size | Target | Stop Loss | Capital |
|---|---|---|---|---|
| NIFTY | 65 | 55 pts | 45 pts | ₹1,00,000 |
| BANKNIFTY | 30 | 60 pts | 75 pts | ₹1,00,000 |
| SENSEX | 20 | 60 pts | 75 pts | ₹1,00,000 |

### IEP (Pre-open Auction) Timing
- Wait until **9:08 AM IST** before fetching IEP data (not available before that)
- Retry every 30 seconds until data arrives **or** 9:12 AM deadline
- IEP noise floor: gaps < 20 pts treated as neutral

### Entry Mode — Rule C
When NIFTY IEP signal conflicts with the gap direction, don't enter immediately — wait for confirmation:
- **CE (BULLISH)**: wait for a higher-high **green** candle after the entry time
- **PE (BEARISH)**: same — wait for the option going UP (lower-low red spot candle)
- Rule C always watches for the **option going UP** regardless of CE/PE
- If Rule C never fires, no trade is taken

### BN IEP Conflict Flip Rule
When GIFT NIFTY gap is BULLISH but BANKNIFTY IEP is strongly bearish, flip from CE to PE:

| Condition | Action |
|---|---|
| `direction == BULLISH` AND `BN IEP gap < −50 pts` | Flip to PE, apply Rule C for PE entry |
| `BN IEP gap ≥ −50 pts` | No flip — stick with CE |

**Threshold = 50 pts** (conservative; both confirmed flip days were −54.5 pts).

Implemented in:
- `backend/premarket/run_signal.py` — saves `trade_direction`, `opt_type`, `entry_mode` in signal record
- `backend/premarket/executor.py` — reads signal record, uses `trade_direction` for strike selection
- `backend/adaptive/main.py` — reads `iep_prices.BANKNIFTY.gap` from signal record

### BN Conflict Flip — Track Record
| Date | BN IEP gap | Day type | CE result | PE result | Flip rule fired? | Correct? |
|---|---|---|---|---|---|---|
| Aug 5, 2026 | −54.5 | BULLISH | SL −₹20,475 | TARGET +₹32,175 | ✅ Yes | ✅ |
| Aug 12, 2026 | −54.5 | BULLISH | SL −₹26,325 | TARGET +₹32,175 | ✅ Yes | ✅ |
| Aug 13, 2026 | −86.7 | FLAT (skip) | — | — | Would have fired | — |
| Aug 14, 2026 | −45.5 | FLAT (skip) | +₹1,869 EOD | (CE profitable) | No (−45.5 > −50) | ✅ |

### Files (all inside `backend/premarket/`)
| File | Purpose |
|---|---|
| `signal.py` | Pure maths — thresholds, INDEX_CONFIG, gap/strike/lot calculations |
| `run_signal.py` | Morning report script — fetch snapshot, compute gap, print signal |
| `main.py` | Full orchestrator — run once at 9:00 AM, handles everything end-to-end |
| `executor.py` | Trade placement + monitoring loop (Target/SL/EOD exit) |

### How to Run (morning routine)
```bash
cd backend && source venv/bin/activate

# Full auto run (paper mode) — all 3 indices
python3 -m premarket.main

# Specific index only
python3 -m premarket.main --index NIFTY

# Skip the wait timers (for testing)
python3 -m premarket.main --index NIFTY --no-wait

# Live orders (careful!)
python3 -m premarket.main --live
```

### What `main.py` does step by step
1. Takes GIFT NIFTY snapshot
2. Computes gap + direction (BULLISH/BEARISH/FLAT)
3. Logs "Waiting until 09:08 IST..." → fetches IEP with retry loop
4. Prints signal report
5. If FLAT → exits
6. Waits until 9:15 AM → fetches spot price for all indices → stores in `spot_at_open` dict
7. If entry is 9:20, waits until 9:20
8. Places orders using `spot_at_open` (strike is always from 9:15 price)
9. Monitors every 2 seconds → exits on Target / SL
10. At 15:25 → force-exits all remaining positions
11. Prints summary + appends to `premarket_trades.jsonl`

### Monitoring Logs
Every ~60 seconds during monitoring:
```
NIFTY2680424450CE  ltp=128.50  entry=114.95  P&L=+13.55pts  T=55  SL=-45
```

---

## 4. Adaptive Strategy

### Concept
A second, lower-risk strategy that enters at **10:00 AM** at the ATM strike, after opening volatility has settled.

### Rules
| Parameter | Value |
|---|---|
| Entry time | 10:00 AM open price |
| Strike | ATM (computed from spot at 10:00) |
| Opt type | CE for BULLISH, PE for BEARISH |
| Target | 20 pts |
| Stop Loss | 30 pts |
| BN conflict flip | Same rule as premarket — if `BN IEP gap < −50` on BULLISH day, take ATM PE |

### File
`backend/adaptive/main.py`

### How to Run
```bash
cd backend && source venv/bin/activate
python3 -m adaptive.main
```

### Adaptive Results (hypothetical, Aug 2026)
| Date | Direction | Opt | Entry | Outcome | PnL |
|---|---|---|---|---|---|
| Aug 12 | BULLISH → PE (flip) | PE ATM | ₹78 | TARGET | +₹11,700 |
| Aug 13 | FLAT (hypo) | PE | — | TARGET | +₹2,600 |
| Aug 14 | FLAT (hypo) | CE ATM | ₹78 | TARGET | +₹1,300 |

---

## 5. Live Paper Trade Results (as of Aug 3, 2026)

Stored in: `backend/data/premarket_trades.jsonl`

| Date | Direction | Gap | Symbol | Lots | Qty | Buy | Exit | Reason | P&L |
|---|---|---|---|---|---|---|---|---|---|
| 2026-07-31 | BULLISH | +91.35 | NIFTY2680424250CE | 9 | 585 | ₹164.90 | ₹172.40 | EOD | **+₹4,387.50** |
| 2026-08-03 | BULLISH | +220.40 | NIFTY2680424450CE | 13 | 845 | ₹114.95 | ₹142.30 | EOD | **+₹23,110.75** |

**Total paper P&L: +₹27,498.25**

### Notes on Jul 31
- Wrong strike was taken on first run (9:20 spot used instead of 9:15 spot)
- Correct 24200 CE would have peaked at 248.5 and hit target at 12:25
- Fix was applied: strike now always uses 9:15 spot

### Notes on Aug 3
- Gap = +220.4 (strong) → entered at 9:15
- Hit 173.2 at 12:15 (needed 174.95 for T=60) — near miss
- With T=55, target was 171.5 → would have been hit at ~11:05

---

## 6. Backtest Results (NIFTY, Jul 22 – Aug 3, 2026)

Data source: `backend/data/nifty_option_history.json`  
9 days. Gaps hardcoded. BEARISH now uses ITM_100 PE (changed from OTM_50).

### T=55 / SL=45 (current config)
| Metric | Value |
|---|---|
| Trades | 7 (1 day flat, 1 day not in data) |
| Wins | 5 |
| Losses | 0 |
| EOD exits | 2 (Jul 31, Aug 3 — both profitable) |
| Win rate | 71% |
| **Total P&L** | **+₹1,67,905** |

### Why T=55/SL=45 was chosen over T=60/SL=50
- T=60/SL=50 gave: 4W 0L 3EOD (57% win rate)
- T=55/SL=45 gives: 5W 0L 2EOD (71% win rate)
- Aug 3 trade: T=60 missed (173.2 vs 174.95), T=55 would have been TARGET

---

## 7. Signal History

Stored in: `backend/data/premarket_signals.jsonl`  
(Code to save signals was added after Jul 31 and Aug 3 runs — file may be empty)

To save today's signal manually:
```bash
cd backend && source venv/bin/activate
python3 -m premarket.run_signal
```

---

## 8. Frontend Pages

| Route | File | Description |
|---|---|---|
| `/` | `Login.js` | Login page (no sidebar) |
| `/signup` | `Signup.js` | Signup |
| `/dashboard` | `Dashboard.js` | Market overview |
| `/trades` | `Trades.jsx` | Manual trades + Bulls Approach premarket table |
| `/swing-trade` | `SwingTrade.js` | Stock screener |
| `/next-move` | `NextMove.jsx` | Next move predictor |
| `/candles-charts` | `CandlesCharts.js` | Charting |
| `/history` | `History.jsx` | Trade history |
| `/settings` | `Settings.jsx` | Settings |

### Trades Page (`/trades`) — Two Sections
1. **Active Orders** (top): Manual trades, add/delete/sell, live LTP via WebSocket
2. **Bulls Approach** (bottom): Premarket trades from `premarket_trades.jsonl`

The date filter at the top affects both tables.  
Bulls Approach shows all records when no date is selected; filters to selected date when a date is picked.

### Sidebar
- Fixed position (`position: fixed`) — does NOT scroll with the page
- `open` state lifted to `MainLayout.js`, passed as prop to `Sidebar.js`
- Width: 220px open, 80px collapsed
- Main content uses `marginLeft` that matches sidebar width

---

## 9. Backend API Endpoints (Key Ones)

| Method | Path | Description |
|---|---|---|
| GET | `/trades` | Get trades by date (default: today IST) |
| POST | `/trades` | Add a manual trade |
| DELETE | `/trades/{id}` | Delete a trade |
| GET | `/premarket-trades` | Get premarket trades (all, or filtered by `?date=YYYY-MM-DD`) |
| GET | `/signals` | Get trading signals |
| GET | `/options` | Options data |
| GET | `/indices` | Index data |
| WS | `/ws/trades` | WebSocket for live LTP on open trades |
| GET | `/auto-trader/status` | Auto-trader engine status |

### premarket-trades endpoint
- No `?date` → returns ALL records (entire history)
- `?date=2026-07-31` → returns only that day's records
- Returns: `{ date, total_pnl, trade_count, trades[] }`

---

## 10. Key Data Files

| File | Description |
|---|---|
| `backend/data/premarket_trades.jsonl` | All live/paper premarket trade records |
| `backend/data/premarket_signals.jsonl` | Daily signal reports (includes IEP data, trade_direction) |
| `backend/data/premarket_snapshots.jsonl` | Morning GIFT NIFTY snapshots |
| `backend/data/signal_logs/YYYY-MM-DD.jsonl` | Per-day intraday signal logs (spot prices, candle events) |
| `backend/data/nifty_option_history.json` | NIFTY CE candle history (all days, 5-min candles) |
| `backend/data/nifty_pe_history.json` | NIFTY PE candle history (auto-saved by fetch_option_data.py) |
| `backend/data/banknifty_option_history.json` | BANKNIFTY CE candle history |
| `backend/data/banknifty_pe_history.json` | BANKNIFTY PE candle history |
| `backend/data/sensex_option_history.json` | SENSEX CE candle history |
| `backend/data/sensex_pe_history.json` | SENSEX PE candle history |
| `backend/data/trades.json` | Manual trades (from /trades page) |
| `config/trading_rules.json` | Trading rules config |

> **Note:** `backend/data/` is in `.gitignore` — data files are local only.

### premarket_trades.jsonl record fields
```json
{
  "date": "2026-08-03",
  "direction": "BULLISH",
  "gap": 220.4,
  "tradingsymbol": "NIFTY2680424450CE",
  "lots": 13,
  "lot_size": 65,
  "quantity": 845,
  "buy_price": 114.95,
  "buy_time": "09:15:01",
  "exit_price": 142.3,
  "exit_time": "15:25:01",
  "exit_reason": "EOD",
  "pnl": 23110.75,
  "mode": "paper"
}
```

---

## 11. EOD Data Fetch Routine

```bash
cd backend && source venv/bin/activate
python fetch_option_data.py          # today
python fetch_option_data.py 2026-08-05  # specific date
```

Fetches **both CE and PE** for all 3 indices (NIFTY, BANKNIFTY, SENSEX) in one run.
- CE → `*_option_history.json`
- PE → `*_pe_history.json`
- `fetch_pe_candles.py` is superseded — no longer needed.

---

## 12. Zerodha Instrument Tokens (Important)

| Instrument | Token |
|---|---|
| GIFT NIFTY | `291849` |
| NIFTY 50 spot | `NSE:NIFTY 50` |
| NIFTY BANK spot | `NSE:NIFTY BANK` |
| SENSEX spot | `BSE:SENSEX` |

---

## 13. Open Tasks / Next Steps

- [ ] **BN conflict threshold**: Validate with more data between −20 and −50 pts to confirm 50pt boundary
- [ ] **BANKNIFTY + SENSEX live runs**: Only NIFTY has been run live so far
- [ ] **Adaptive strategy live run**: `adaptive/main.py` written but not yet run in paper/live mode
- [ ] **premarket_signals.jsonl display**: Consider showing signal history in frontend
- [ ] **Historical PE data**: Re-run `fetch_option_data.py` for older dates to backfill pe_history files

---

## 14. Key Decisions Made (Why Things Are The Way They Are)

| Decision | Reason |
|---|---|
| T=55/SL=45 for NIFTY premarket | 71% win rate vs 57% with T=60/SL=50 |
| T=20/SL=30 for adaptive | Lower risk at ATM; ATM has less premium than ITM_100 |
| ITM_100 for premarket CE/PE | More premium, better absolute profit per point |
| ATM for adaptive | Entry at 10:00 when volatility settles; tight T/SL suits ATM |
| Strike from 9:15 spot always | Jul 31 bug: 9:20 spot gave wrong strike, missed target |
| IEP wait until 9:08 + retry until 9:12 | IEP data not available before pre-open auction ends |
| IEP noise floor = 20 pts | Gaps < 20 pts are indistinguishable from noise |
| BN conflict threshold = 50 pts | Conservative — both confirmed data points were −54.5 pts; −45.5 was CE-profitable |
| Rule C always watches option going UP | CE up = spot up; PE up = spot down — same logic regardless of opt_type |
| `fetch_option_data.py` fetches both CE and PE | Needed for daily analysis without a separate manual script |
| `backend/data/` in .gitignore | Data files are large, local, and change daily — not for version control |
| `position: fixed` sidebar | User feedback — sidebar was scrolling with page |
| Bulls Approach shows all records by default | Premarket trades are sparse (1/day) — showing all is more useful |

---

## 15. Strategy Performance Summary (PREMARKET_README.md Chapter 4)

| Index | Trades | W | L | EOD | P&L |
|---|---|---|---|---|---|
| NIFTY | 7 | 5 | 0 | 2 | +₹1,67,905 |
| BANKNIFTY | 5 | 4 | 1 | 0 | +₹15,300 |
| SENSEX | 2 | 2 | 0 | 0 | +₹10,800 |
| **TOTAL** | **14** | **11** | **1** | **2** | **+₹1,94,005** |

Period: Jul 22 – Aug 3, 2026 (backtest on option history data)
