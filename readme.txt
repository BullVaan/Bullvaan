================================================================================
                         BULLVAAN - TRADING PLATFORM
                    Real-Time Multi-Strategy Trading System
================================================================================

📚 WHAT THIS PROJECT DOES (IN SIMPLE TERMS):
================================================================================

Imagine you're buying vegetables in a market. You don't buy just because one 
person says "tomatoes are good today". You ask 10 different vendors, and if 
7-8 of them say "yes, tomatoes are fresh today", THEN you buy.

This platform does the SAME with stock trading:
- It shows ALL Nifty OPTIONS (different strike prices like 22300, 22400, 22500)
- YOU select which specific option you want to trade (22400 CE for example)
- It gets LIVE price data for YOUR SELECTED option every second
- It has 10 different "experts" (strategies) analyzing that option's price
- Each expert says "BUY" (green light) or "SELL" (red light)
- If 7-8 experts say "BUY", the system suggests you BUY that option
- If 7-8 experts say "SELL", the system suggests you SELL
- You see all 10 experts on your screen in colored boxes (tiles)

NIFTY OPTIONS = Contracts that give you right to buy/sell Nifty at specific price
- 22300 CE = Right to buy Nifty at 22,300 (CE = Call Option = Betting price goes UP)
- 22300 PE = Right to sell Nifty at 22,300 (PE = Put Option = Betting price goes DOWN)

SCALPING = Quick trading (buy and sell within minutes to make small profits)

================================================================================
                            PROJECT STRUCTURE
================================================================================

BullVaan/
│
├── readme.txt                          # This file - Project documentation
│
├── backend/                            # Server-side code (Python)
│   ├── venv/                           # Virtual environment (created by you)
│   │   ├── bin/                        # Python executables
│   │   ├── lib/                        # Installed packages
│   │   └── ...                         # Other venv files
│   │
│   ├── main.py                         # Main application entry point
│   ├── requirements.txt                # Python packages needed
│   ├── .env                            # Environment variables (secrets)
│   │
│   ├── api/                            # API Integration
│   │   ├── __init__.py
│   │   ├── kotak_neo.py               # Kotak Neo REST API + WebSocket Client
│   │   ├── kotak_websocket.py         # WebSocket handler for live data (NEW)
│   │   ├── kotak_neo_sdk.py           # Official SDK wrapper (experimental)
│   │   └── option_chain.py            # Fetches all Nifty strike prices
│   │   └── websocket_handler.py       # Handles real-time data streaming
│   │
│   ├── strategies/                     # Trading Strategies (10 experts)
│   │   ├── __init__.py
│   │   ├── base_strategy.py           # Base template for all strategies
│   │   ├── strategy_1_moving_average.py    # Expert 1: Moving Average
│   │   ├── strategy_2_rsi.py               # Expert 2: RSI (strength meter)
│   │   ├── strategy_3_macd.py              # Expert 3: MACD (trend follower)
│   │   ├── strategy_4_bollinger_bands.py   # Expert 4: Price bands
│   │   ├── strategy_5_ema_crossover.py     # Expert 5: EMA 21/29 crossover
│   │   ├── strategy_6_pivot_points.py      # Expert 6: Pivot Points (scalping)
│   │   ├── strategy_7_volume_analysis.py   # Expert 7: Volume spikes
│   │   ├── strategy_8_price_action.py      # Expert 8: Candlestick patterns
│   │   ├── strategy_9_supertrend.py        # Expert 9: Supertrend indicator
│   │   └── strategy_10_vwap.py             # Expert 10: Volume weighted price
│   │
│   ├── engine/                         # Core Trading Logic
│   │   ├── __init__.py
│   │   ├── consensus_engine.py        # Combines 10 expert opinions
│   │   ├── position_manager.py        # Tracks if you bought/sold
│   │   ├── risk_manager.py            # Stop-loss & profit targets
│   │   └── signal_processor.py        # Processes buy/sell signals
│   │
│   ├── database/                       # Data Storage
│   │   ├── __init__.py
│   │   ├── models.py                  # Database structure
│   │   ├── trade_logger.py            # Saves all trades
│   │   └── signal_history.py          # Saves all signals
│   │
│   ├── utils/                          # Helper Functions
│   │   ├── __init__.py
│   │   ├── logger.py                  # Records events in files
│   │   ├── config.py                  # Settings & configuration
│   │   └── helpers.py                 # Common utility functions
│   │
│   └── tests/                          # Testing Code
│       ├── test_strategies.py
│       └── test_consensus.py
│
├── frontend/                           # User Interface (React/Next.js)
│   ├── package.json                    # JavaScript packages needed
│   ├── next.config.js                  # Next.js configuration
│   │
│   ├── public/                         # Static files (images, icons)
│   │   ├── logo.png
│   │   └── favicon.ico
│   │   └── charting_library/          # TradingView Lightweight Charts
│   │
│   ├── src/
│   │   ├── pages/                      # Website pages
│   │   │   ├── index.js               # Home/Dashboard page
│   │   │   └── _app.js                # Main app wrapper
│   │   │
│   │   ├── components/                 # Reusable UI pieces
│   │   │   ├── Dashboard.jsx          # Main dashboard layout
│   │   │   ├── StrikeSelector.jsx     # Dropdown to select option strike
│   │   │   ├── OptionChain.jsx        # Shows all available strikes
│   │   │   ├── StrategyTile.jsx       # Individual strategy box (green/red)
│   │   │   ├── ConsensusPanel.jsx     # Shows 7/10 vote count
│   │   │   ├── LiveChart.jsx          # Live candlestick chart with indicators
│   │   │   ├── PriceChart.jsx         # Simple line chart (backup)
│   │   │   ├── IndicatorOverlay.jsx   # Shows EMA, BB lines on chart
│   │   │   ├── PositionStatus.jsx     # Shows if you bought/not
│   │   │   ├── ProfitLossCard.jsx     # Shows profit/loss
│   │   │   └── TradeLog.jsx           # Lists all trades
│   │   │
│   │   ├── hooks/                      # Custom React hooks
│   │   │   ├── useWebSocket.js        # Connects to live data
│   │   │   └── useStrategies.js       # Manages strategy data
│   │   │
│   │   ├── store/                      # State Management (Redux/Zustand)
│   │   │   ├── strategyStore.js       # Stores strategy signals
│   │   │   ├── tradeStore.js          # Stores trade data
│   │   │   └── marketStore.js         # Stores market data
│   │   │
│   │   ├── services/                   # API Communication
│   │   │   ├── api.js                 # Backend API calls
│   │   │   └── websocket.js           # WebSocket connection
│   │   │
│   │   └── styles/                     # CSS Styling
│   │       ├── globals.css
│   │       └── dashboard.module.css
│   │
│   ├── node_modules/                   # Installed npm packages (auto-created)
│   ├── .next/                          # Next.js build files (auto-created)
│   ├── .env.local                      # Frontend environment variables
│   └── package-lock.json               # Locked versions of packages
│
├── config/                             # Configuration Files
│   ├── kotak_neo_config.json          # API credentials
│   ├── strategy_config.json           # Strategy parameters
│   └── trading_rules.json             # Trading rules (7/10 threshold)
│
├── logs/                               # Log Files
│   ├── trades.log                     # All executed trades
│   ├── signals.log                    # All strategy signals
│   └── errors.log                     # Error messages
│
├── data/                               # Historical Data
│   ├── historical_prices/             # Past price data
│   └── backtest_results/              # Strategy test results
│
├── docs/                               # Documentation
│   ├── STRATEGY_EXPLANATIONS.md       # How each strategy works
│   ├── API_SETUP.md                   # Kotak Neo setup guide
│   └── DEPLOYMENT.md                  # How to deploy
│
├── .gitignore                          # Files to ignore in Git
│                                       # (includes venv/, node_modules/, .env)
├── docker-compose.yml                  # Docker setup (for easy deployment)
├── Dockerfile                          # Docker configuration
└── .env                                # Environment variables (secrets)


NOTE: Files/folders marked as "(auto-created)" or "(created by you)" will appear
      after running setup commands. Don't create them manually!


================================================================================
                    SIMPLE EXPLANATIONS OF KEY CONCEPTS
================================================================================

1. WHAT ARE NIFTY OPTIONS?
   - NIFTY SPOT = Current value of Nifty index (e.g., 22,450)
   - NIFTY OPTION = A contract to buy/sell Nifty at a FIXED price (strike)
   
   Two types:
   a) CALL (CE) = You bet price will go UP
      Example: Buy 22400 CE at ₹150
      If Nifty goes to 22,600 → Your option becomes ₹200+ → Profit!
      
   b) PUT (PE) = You bet price will go DOWN
      Example: Buy 22400 PE at ₹100
      If Nifty falls to 22,200 → Your option becomes ₹200+ → Profit!
   
   Why Options?
   - Less capital needed (₹5,000-10,000 vs ₹5 lakhs for futures)
   - Higher returns percentage (can double in minutes)
   - Perfect for scalping/intraday

2. HOW TO CHOOSE STRIKE PRICE?
   - ATM (At The Money) = Strike close to current Nifty
     Example: Nifty at 22,450 → 22400 or 22500 strikes are ATM
     → Most liquid, good for scalping
   
   - OTM (Out of The Money) = Strike far from current price
     Example: Nifty at 22,450 → 22600 CE or 22300 PE
     → Cheaper but riskier
   
   - ITM (In The Money) = Strike already crossed
     Example: Nifty at 22,450 → 22300 CE or 22600 PE
     → More expensive but safer
   
   FOR SCALPING: Use ATM or slightly OTM (1-2 strikes away)

3. WHAT IS A STRATEGY?
3. WHAT IS A STRATEGY?
   Think of it as a "rule" or "expert opinion"
   Example: "If price goes above 100, say BUY. If below 90, say SELL"

4. COMMON STRATEGIES (YOUR 10 EXPERTS):

   a) MOVING AVERAGE (MA)
      - Like calculating average marks of last 5 exams
      - If current price > average price, it's going UP (BUY)
      - If current price < average price, it's going DOWN (SELL)

   b) RSI (Relative Strength Index)
      - Measures if stock is "tired" (overbought) or "energetic" (oversold)
      - Like a battery meter: 0-30 = time to charge (BUY), 70-100 = overcharged (SELL)

   c) MACD (Moving Average Convergence Divergence)
      - Compares two different averages
      - When fast average crosses slow average UP = BUY signal
      - When fast crosses DOWN = SELL signal

   d) BOLLINGER BANDS
      - Creates upper & lower price boundaries
      - Price touching lower band = cheap, might go up (BUY)
      - Price touching upper band = expensive, might fall (SELL)

   e) EMA CROSSOVER (EMA 21/29)
      - Similar to MA but gives more importance to recent prices
      - EMA21 = Fast line (21 periods), EMA29 = Slow line (29 periods)
      - When EMA21 crosses EMA29 UP = BUY (fast overtaking slow = momentum UP)
      - When EMA21 crosses DOWN = SELL (losing momentum)
      - This is your SPECIFIC request - great for catching trends early!

   f) PIVOT POINTS (PERFECT FOR SCALPING!)
      - Calculates key support/resistance levels for the day
      - Like "magnetic zones" where price tends to bounce or break
      - Price bouncing UP from support pivot = BUY
      - Price bouncing DOWN from resistance pivot = SELL
      - Very popular with intraday traders - resets every day at 9:15 AM
      - Simple formula using previous day's High, Low, Close

   g) VOLUME ANALYSIS
      - Checks how many people are trading
      - High volume + price rising = strong BUY signal
      - High volume + price falling = strong SELL signal

   h) PRICE ACTION (CANDLESTICK PATTERNS)
      - Reads candles like a story - no math needed!
      - Bullish patterns (BUY signals):
        * Bullish Engulfing = Big green candle swallows previous red
        * Hammer = Long lower tail, buyers stepped in
        * Morning Star = Three-candle reversal pattern
      - Bearish patterns (SELL signals):
        * Bearish Engulfing = Big red candle swallows previous green
        * Shooting Star = Long upper tail, sellers rejected high prices
        * Evening Star = Reversal at top
      - Most reliable for options scalping - direct price behavior

   i) SUPERTREND
      - Shows trend direction clearly
      - Green line = uptrend (BUY), Red line = downtrend (SELL)

   j) VWAP (Volume Weighted Average Price)
      - Average price weighted by volume
      - Price above VWAP = bullish (BUY)
      - Price below VWAP = bearish (SELL)

   NOTE: All these strategies work on YOUR SELECTED option's price data,
   not Nifty spot. So when you select "22400 CE", all 10 strategies analyze
   the price movement of that specific option contract.

5. CONSENSUS ENGINE
   - This is the "voting system"
   - Collects opinions from all 10 strategies
   - Counts: 8 say BUY, 2 say SELL = 80% BUY consensus
   - If consensus ≥ 70% (7/10) → Take action

6. WEBSOCKET
   - Like a phone call that stays connected
   - Normal API = you call, ask price, hang up, call again (slow)
   - WebSocket = call stays connected, price updates automatically (fast)

7. POSITION MANAGER
   - Tracks: Did you BUY? How many? At what price? Which option?
   - Prevents buying twice without selling first

8. RISK MANAGER
   - Stop-Loss: "If I lose ₹500, sell automatically"
   - Target: "If I profit ₹1000, sell automatically"
   - Protects your money

9. LIVE CHARTING (What Kotak Neo Provides vs What We Build)
   
   KOTAK NEO GIVES US:
   ✅ Real-time price ticks (every 1 second via WebSocket)
   ✅ Historical OHLC data (Open, High, Low, Close for each minute/5min/15min)
   ✅ Volume data
   ✅ Bid/Ask prices
   ✅ Market depth
   
   KOTAK NEO DOES NOT GIVE:
   ❌ Ready-made chart widget
   ❌ Visual indicators overlaid
   
   WE BUILD THE CHART USING:
   - Lightweight Charts library (by TradingView - same as professional trading apps)
   - Takes Kotak's price data → Converts to candlesticks → Displays beautifully
   - We draw EMA 21/29 lines on top of candles
   - We place markers (arrows) where strategies say BUY/SELL
   - Updates LIVE as new data comes from Kotak
   
   CHART FEATURES:
   - Candlestick view (green = price went up, red = price went down)
   - Multiple timeframes: 1-minute, 5-minute, 15-minute candles
   - Indicator overlays: EMA lines, Bollinger Bands drawn on the same chart
   - Volume bars below the price chart
   - Zoom in/out, pan left/right to see history
   - Crosshair to see exact price at any time
   
   SIMPLE ANALOGY:
   Kotak Neo = Weather station (provides temperature, humidity data)
   Our Chart = Weather app display (takes that data, shows beautiful graphs)

================================================================================
                        HOW THE SYSTEM WORKS (FLOW)
================================================================================

UPDATED FLOW WITH WEBSOCKET INTEGRATION:

1. USER AUTHENTICATION:
   - Open Google Authenticator → Get TOTP code
   - Backend authenticates with Kotak Neo (login + validate)
   - Receives trade_token, sid, server_id
   - WebSocket client automatically initialized

2. DASHBOARD INITIALIZATION:
   - Backend fetches scrip master CSV from Kotak
   - Downloads 100,000+ instrument tokens
   - Filters Nifty options by strike price (e.g., 25000)
   - Shows available options: 25000 CE, 25000 PE, etc.

3. USER SELECTS OPTION:
   - YOU select ONE option from dropdown (e.g., "NIFTY2621025000CE")
   - Backend connects WebSocket to wss://mlhsm.kotaksecurities.com
   - Sends connection payload with auth credentials

4. LIVE DATA STREAMING:
   - Backend subscribes to selected option via WebSocket
   - Receives tick-by-tick updates:
     * Last Traded Price (LTP)
     * Bid/Ask prices
     * Volume
     * OHLC (current candle)
   - Updates arrive every second during market hours

5. STRATEGY EXECUTION:
   - Each tick feeds into all 10 strategies simultaneously
   - Strategies calculate technical indicators:
     * Moving Average (20-period)
     * RSI (14-period)
     * MACD (5,13,1 for scalping)
     * Bollinger Bands
     * EMA 21/29 crossover
     * Pivot Points (daily)
     * Volume spikes
     * Price action patterns
     * Supertrend
     * VWAP
   - Each strategy outputs: BUY / SELL / NEUTRAL

6. CONSENSUS ENGINE:
   - Counts votes: e.g., 8 BUY, 1 SELL, 1 NEUTRAL
   - Calculates consensus: 8/10 = 80%
   - Threshold check: 80% ≥ 70% (from trading_rules.json)
   - Generates FINAL signal: BUY

7. FRONTEND UPDATE (via WebSocket):
   - Backend → Frontend WebSocket connection
   - Sends signal + metadata to dashboard
   - Frontend updates in real-time:
     * 10 strategy tiles (green/red/gray)
     * Consensus meter: "8/10 BUY"
     * Live chart updates with current price
     * Signal markers on chart

8. TRADE EXECUTION (if auto-trading enabled):
   - Position Manager receives BUY signal
   - Checks risk limits (stop-loss, position size)
   - Places order via Kotak Neo API
   - Logs trade in database
   - Updates P&L on dashboard

9. MONITORING & UPDATES:
   - Continuous tick data → strategies → signals
   - If consensus shifts to SELL → Exit signal generated
   - You can switch to different strike anytime
   - Strategies recalculate instantly for new option

10. END OF SESSION:
    - Market closes (3:30 PM IST)
    - WebSocket disconnects
    - Final P&L calculated
    - All trades logged for analysis

================================================================================
                        SYSTEM ARCHITECTURE DIAGRAM
================================================================================

┌─────────────────────────────────────────────────────────────────────────┐
│                            USER INTERFACE                                │
│                       (Next.js + TradingView Charts)                     │
│                                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │  Dashboard   │  │  Strategy    │  │   Chart      │                  │
│  │   Tiles      │  │  Controls    │  │   View       │                  │
│  │ (10 boxes)   │  │  (Dropdown)  │  │ (Live OHLC)  │                  │
│  └──────────────┘  └──────────────┘  └──────────────┘                  │
└─────────────────────────────────────────────────────────────────────────┘
                              ↕ WebSocket (Socket.io)
┌─────────────────────────────────────────────────────────────────────────┐
│                          BACKEND SERVER                                  │
│                        (FastAPI + Python)                                │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │              KOTAK NEO CLIENT (kotak_neo.py)                        │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │ │
│  │  │  Authentication  │  │  Scrip Master    │  │   WebSocket     │  │ │
│  │  │  (TOTP + MPIN)   │  │  (Symbol Search) │  │   Handler       │  │ │
│  │  └──────────────────┘  └──────────────────┘  └─────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    STRATEGY ENGINES (10 Total)                      │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │ │
│  │  │   MA     │ │   RSI    │ │   MACD   │ │ Bollinger│ │  EMA    │ │ │
│  │  │ Strategy │ │ Strategy │ │ Strategy │ │ Strategy │ │Strategy │ │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └─────────┘ │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │ │
│  │  │  Pivot   │ │  Volume  │ │  Price   │ │Supertrend│ │  VWAP   │ │ │
│  │  │ Strategy │ │ Strategy │ │  Action  │ │ Strategy │ │Strategy │ │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └─────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                ↓                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    CONSENSUS ENGINE                                 │ │
│  │              (Aggregates signals from 10 strategies)                │ │
│  │              Threshold: 7/10 (70%) for trade signal                 │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                ↓                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │               POSITION & RISK MANAGER                               │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │ │
│  │  │  Position Size   │  │  Stop Loss       │  │  Trade Logger   │  │ │
│  │  │  Calculator      │  │  Calculator      │  │  (Database)     │  │ │
│  │  └──────────────────┘  └──────────────────┘  └─────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                              ↕ WebSocket (Live Data)
┌─────────────────────────────────────────────────────────────────────────┐
│                        KOTAK NEO API                                     │
│                  wss://mlhsm.kotaksecurities.com                         │
│                                                                           │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────────┐  │
│  │  Live Tick Data  │  │  Scrip Master    │  │  Order Execution    │  │
│  │  (Every Second)  │  │  (CSV Download)  │  │  (Buy/Sell Orders)  │  │
│  └──────────────────┘  └──────────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                              ↕ Market Hours Only
┌─────────────────────────────────────────────────────────────────────────┐
│                         NSE INDIA MARKET                                 │
│                    (9:15 AM - 3:30 PM IST)                               │
│                                                                           │
│              Live Options Trading: NIFTY, BANKNIFTY, etc.                │
└─────────────────────────────────────────────────────────────────────────┘

KEY DATA FLOWS:
══════════════

1. USER → BACKEND: Option selection, strategy parameters
2. KOTAK API → BACKEND: Live tick data (WebSocket stream)
3. BACKEND → STRATEGIES: Price data for analysis
4. STRATEGIES → CONSENSUS: Individual BUY/SELL/NEUTRAL signals
5. CONSENSUS → POSITION MGR: Final trade signal
6. POSITION MGR → KOTAK API: Order placement
7. BACKEND → FRONTEND: Real-time updates (WebSocket)
8. BACKEND → DATABASE: Trade logs, P&L records

CRITICAL COMPONENTS:
═══════════════════

✅ IMPLEMENTED:
- KotakNeoClient (authentication + WebSocket)
- KotakWebSocket (live data handler)
- MovingAverageStrategy (first strategy)
- Configuration & Logging systems
- Symbol search & filtering

⏳ IN PROGRESS:
- WebSocket testing during market hours
- Database schema for tick storage

⬜ TODO:
- 9 remaining strategies
- Consensus engine
- Position manager
- Risk calculator
- Frontend dashboard

================================================================================
                            TECHNOLOGY STACK
================================================================================

BACKEND:
- Python 3.10+
- FastAPI (modern web framework)
- Pandas & NumPy (data processing)
- TA-Lib (technical analysis library)
- SQLAlchemy (database)
- WebSocket (real-time communication)

FRONTEND:
- Next.js 14 (React framework)
- TypeScript (for type safety)
- Tailwind CSS (styling)
- Lightweight Charts by TradingView (professional candlestick charts)
- Recharts (backup for simple charts)
- Zustand / Redux (state management)
- Socket.io-client (WebSocket client)

CHARTING:
- TradingView Lightweight Charts - Professional, fast, real-time capable
- Displays: Candlesticks (1min, 5min), Volume bars, Indicator overlays
- Shows: EMA 21/29 lines, Bollinger Bands, Buy/Sell signals as markers

DATABASE:
- PostgreSQL (main database)
- Redis (caching & real-time data)

DEPLOYMENT:
- Docker (containerization)
- AWS / DigitalOcean (hosting)

================================================================================
                    SETUP INSTRUCTIONS (STEP-BY-STEP)
================================================================================

📋 PREREQUISITES:
- Python 3.10 or higher installed
- Node.js 18+ and npm installed
- Kotak Neo trading account
- Terminal/Command Prompt access

================================================================================
STEP 1: CREATE PROJECT STRUCTURE
================================================================================

1.1 Open Terminal/Command Prompt
1.2 Navigate to project folder:
    cd /Users/ashishyadav/Documents/BullVaan

================================================================================
STEP 2: SETUP BACKEND (Python)
================================================================================

2.1 Create backend directory:
    mkdir backend
    cd backend

2.2 Create Python virtual environment:
    python3 -m venv venv
    
    What this does: Creates isolated Python environment (keeps packages separate)

2.3 Activate virtual environment:
    
    On macOS/Linux:
    source venv/bin/activate
    
    On Windows:
    venv\Scripts\activate
    
    You should see (venv) at the start of your terminal prompt ✅

2.4 Create requirements.txt file in backend folder with these packages:
    fastapi==0.104.1
    uvicorn[standard]==0.24.0
    websockets==12.0
    pandas==2.1.3
    numpy==1.26.2
    ta-lib==0.4.28
    sqlalchemy==2.0.23
    python-dotenv==1.0.0
    requests==2.31.0
    pydantic==2.5.0

2.5 Install all packages:
    pip install -r requirements.txt
    
    (This will take 2-3 minutes - installing all Python libraries)

2.6 Verify installation:
    pip list
    
    You should see all packages listed ✅

================================================================================
STEP 3: SETUP FRONTEND (React/Next.js)
================================================================================

3.1 Go back to main project folder:
    cd /Users/ashishyadav/Documents/BullVaan

3.2 Create Next.js frontend:
    npx create-next-app@latest frontend
    
    When prompted, choose:
    - TypeScript? → Yes
    - ESLint? → Yes
    - Tailwind CSS? → Yes
    - src/ directory? → Yes
    - App Router? → Yes
    - Import alias? → No

3.3 Navigate to frontend:
    cd frontend

3.4 Install additional packages:
    npm install lightweight-charts socket.io-client zustand axios recharts

3.5 Verify installation:
    npm run dev
    
    Open http://localhost:3000 - you should see Next.js welcome page ✅

================================================================================
STEP 4: KOTAK NEO ACCOUNT SETUP
================================================================================

4.1 Open Kotak Neo trading account (if not already done)
4.2 Login to Kotak Neo portal
4.3 Go to API section and generate:
    - Consumer Key
    - Consumer Secret
    - Access Token
4.4 Save these credentials securely (we'll use them later)

================================================================================
STEP 5: CREATE CONFIGURATION FILES
================================================================================

5.1 Create config folder in main project:
    mkdir config

5.2 Create config/kotak_neo_config.json:
    {
      "consumer_key": "YOUR_KEY_HERE",
      "consumer_secret": "YOUR_SECRET_HERE",
      "access_token": "YOUR_TOKEN_HERE",
      "api_url": "https://gw-napi.kotaksecurities.com"
    }

5.3 Create .env file in backend folder:
    DATABASE_URL=sqlite:///./trading.db
    REDIS_URL=redis://localhost:6379
    SECRET_KEY=your-secret-key-here
    DEBUG=True

================================================================================
STEP 6: START DEVELOPMENT
================================================================================

6.1 Start Backend (in one terminal):
    cd /Users/ashishyadav/Documents/BullVaan/backend
    source venv/bin/activate
    python main.py
    
    Backend should run on: http://localhost:8000

6.2 Start Frontend (in another terminal):
    cd /Users/ashishyadav/Documents/BullVaan/frontend
    npm run dev
    
    Frontend should run on: http://localhost:3000

6.3 Access Dashboard:
    Open browser → http://localhost:3000

================================================================================
CURRENT STATUS: Virtual Environment Created ✅
NEXT STEP: Install Python packages (requirements.txt)
================================================================================

================================================================================
                        TRADING RULES CONFIGURATION
================================================================================

Location: config/trading_rules.json

{
  "consensus_threshold": 0.7,        # 70% = 7/10 strategies must agree
  "position_size": 1,                # How many lots to trade
  "stop_loss_percent": 0.5,          # Exit if 0.5% loss
  "target_percent": 1.0,             # Exit if 1% profit
  "trading_hours": {
    "start": "09:15",                # Market open time
    "end": "15:30"                   # Market close time
  },
  "max_trades_per_day": 10,          # Maximum trades allowed
  "enable_auto_trading": false       # true = auto trade, false = manual
}

================================================================================
                            DASHBOARD LAYOUT
================================================================================

+--------------------------------------------------------------------+
|                    BULLVAAN DASHBOARD                              |
+--------------------------------------------------------------------+
| NIFTY SPOT: 22,450.50 (+0.85%)  |  Position: NONE  |  P&L: +₹2,450 |
+--------------------------------------------------------------------+
|                                                                    |
|  SELECT OPTION TO TRADE:                                           |
|  ┌─────────────────────────────────────────────────────┐           |
|  │ Nifty 22400 CE  ▼                                    │ [CHANGE] |
|  └─────────────────────────────────────────────────────┘           |
|                                                                    |
|  Available Options: 22300 CE/PE | 22400 CE/PE | 22500 CE/PE        |
|                     22600 CE/PE | 22700 CE/PE | 22800 CE/PE        |
|                                                                    |
|  Selected: NIFTY 22400 CE | Price: ₹145.50 | Change: +5.30         |
+--------------------------------------------------------------------+
|                                                                    |
|  STRATEGY TILES (10 boxes in 2 rows)                               |
|                                                                    |
|  [GREEN]     [GREEN]     [RED]      [GREEN]     [GREEN]            |
|   MA          RSI        MACD        BB       EMA 21/29            |
|   BUY         BUY        SELL        BUY         BUY               |
|                                                                    |
|  [GREEN]     [GRAY]      [GREEN]    [GREEN]     [GREEN]            |
|  PIVOT      VOLUME    PRICE ACTION   SUPER       VWAP              |
|   BUY        NEUTRAL     BUY         BUY         BUY               |
|                                                                    |
+--------------------------------------------------------------------+
|                      CONSENSUS: 8/10 BUY (80%)                     |
|              [==========> ] Green bar showing 80%                  |
|                                                                    |
|                    💡 STRONG BUY SIGNAL - Consider Entry           |
+--------------------------------------------------------------------+
|                                                                    |
|  LIVE CANDLESTICK CHART: Nifty 22400 CE (5-min candles)            |
|  ┌────────────────────────────────────────────────────────┐        |
|  │    📊 EMA21 (blue line) ━━━━                           │        |
|  │    📊 EMA29 (orange line) ━━━━                         │        |
|  │    🟢 Buy Signal (arrow up)   🔴 Sell Signal (down).    │       |
|  │                                                        │        |
|  │    ▌  ▌  ▌  ▌  ▌  ▌  ▌  ▌  ▌  ← Candlesticks           │        |
|  │    │  │  │  │  │  │  │  │  │                           │        |
|  │    ▂▂▃▃▄▄▅▅▆▆▇▇▇▇▆▆▅▅▄▄▃▃▂▂  ← Volume bars             │        |
|  │    10:15   10:30   10:45   11:00   11:15   11:30       │        |
|  └────────────────────────────────────────────────────────┘        |
|  Timeframe: [1m] [5m] [15m] [1h] ← Switch candle duration          |
+--------------------------------------------------------------------+
|  TRADE LOG:                                                        |
|  10:05 AM - BUY  22400 CE @ ₹145 - Consensus: 8/10                 |
|  10:12 AM - SELL 22400 CE @ ₹150 - Profit: ₹250 (1 lot)            |
+--------------------------------------------------------------------+

================================================================================
                            DEVELOPMENT PHASES
================================================================================

PHASE 1: FOUNDATION (Week 1-2)
- Setup project structure
- Kotak Neo API integration
- Basic WebSocket connection
- Database setup

PHASE 2: STRATEGIES (Week 3-4)
- Implement all 10 strategies
- Test each strategy individually
- Create base strategy class

PHASE 3: CONSENSUS ENGINE (Week 5)
- Build voting system
- Position manager
- Risk manager

PHASE 4: FRONTEND (Week 6-7)
- Dashboard UI
- Strategy tiles
- Real-time updates
- Charts

PHASE 5: TESTING (Week 8)
- Paper trading (no real money)
- Backtest with historical data
- Fix bugs

PHASE 6: DEPLOYMENT (Week 9-10)
- Docker setup
- Cloud deployment
- Monitoring & alerts

================================================================================
                            RISK WARNINGS ⚠️
================================================================================

1. START WITH PAPER TRADING (fake money) for at least 1 month
2. NEVER risk more than 2% of your capital per trade
3. Trading involves REAL MONEY LOSS - be careful
4. Test all strategies thoroughly before going live
5. Have emergency stop-loss always enabled
6. Don't trade with borrowed money
7. Scalping requires fast internet and low latency
8. Kotak Neo API has rate limits - check documentation

================================================================================
                                NEXT STEPS
================================================================================

COMPLETED:
1. ✅ Create project structure
2. ✅ Setup virtual environment & install packages
3. ✅ Kotak Neo authentication (TOTP-based)
4. ✅ Scrip master integration (symbol search)
5. ✅ WebSocket integration for live data
6. ✅ Moving Average strategy implemented
7. ✅ Configuration & logging systems

IN PROGRESS:
8. ⏳ Testing WebSocket during market hours
9. ⏳ Building historical data storage

TODO:
10. ⬜ Implement remaining 9 strategies
11. ⬜ Build consensus engine
12. ⬜ Create position manager
13. ⬜ Build frontend dashboard
14. ⬜ Paper trading implementation
15. ⬜ Risk management system
16. ⬜ Go live (carefully!)

================================================================================
                    WEBSOCKET INTEGRATION (LATEST UPDATE)
================================================================================

🔴 IMPORTANT DISCOVERY:
Kotak Neo API does NOT provide historical OHLC data via REST API!
This was confirmed via GitHub discussions: 
https://github.com/Kotak-Neo/kotak-neo-api/discussions/115

Multiple users have been requesting this feature since Jan 2024, but it's 
still not available.

✅ WHAT WORKS:
- Authentication with TOTP (Google Authenticator)
- Scrip master download (finding symbols)
- WebSocket connection for LIVE tick data

❌ WHAT DOESN'T WORK:
- REST API for historical OHLC candles
- Backtesting data from Kotak Neo

📊 SOLUTION IMPLEMENTED:

We've integrated WebSocket support for real-time data:

1. NEW FILE: backend/api/kotak_websocket.py
   - Connects to wss://mlhsm.kotaksecurities.com
   - Handles live market data streaming
   - Stores quotes in memory
   - Supports subscribe/unsubscribe

2. UPDATED: backend/api/kotak_neo.py
   - Auto-initializes WebSocket after authentication
   - Methods added:
     * connect_websocket() - Establish connection
     * subscribe_live_feed(instruments) - Subscribe to symbols
     * get_live_quote(symbol) - Get latest price
     * set_websocket_callbacks() - Custom event handlers

3. TESTING:
   Run: python -m api.kotak_neo
   - Authenticates successfully
   - Finds Nifty options by strike
   - Connects WebSocket
   - Subscribes to live feed
   - Prints real-time tick data

📈 DATA STRATEGY (RECOMMENDED):

For your trading platform, use HYBRID approach:

SHORT-TERM (Testing Phase):
- Use NSEpy library for Nifty spot/index data
- Good enough to test strategy logic
- Free and immediate

LONG-TERM (Production):
- Store WebSocket tick data to SQLite database
- Build your own historical dataset over time
- Run data collector during market hours (9:15 AM - 3:30 PM IST)
- Perfect alignment between backtest and live data

IMPLEMENTATION:
Phase 1: WebSocket → Database storage (tomorrow's task)
Phase 2: NSEpy integration for immediate strategy testing
Phase 3: Dashboard with TradingView Lightweight Charts

🕐 MARKET HOURS:
Indian Stock Market: Monday-Friday, 9:15 AM - 3:30 PM IST
Your Norway Time: 4:45 AM - 11:00 AM CET

WebSocket will ONLY work during market hours!

================================================================================
                         HOW TO USE WEBSOCKET
================================================================================

BASIC USAGE:

from api.kotak_neo import KotakNeoClient

# Initialize client
client = KotakNeoClient()

# Authenticate
totp = "123456"  # From Google Authenticator
if client.login(totp) and client.validate():
    
    # Set up callback for live data
    def on_message(data):
        print(f"Live: {data}")
    
    client.set_websocket_callbacks(on_message=on_message)
    
    # Connect WebSocket
    client.connect_websocket()
    
    # Wait for connection
    import time
    time.sleep(3)
    
    # Subscribe to instruments
    instruments = [
        {"instrument_token": "NIFTY2621025000CE", "exchange_segment": "nse_fo"}
    ]
    client.subscribe_live_feed(instruments)
    
    # Get live quotes
    while True:
        quote = client.get_live_quote("NIFTY2621025000CE")
        if quote:
            print(f"LTP: {quote.get('lp')}")
        time.sleep(1)

WHAT YOU'LL RECEIVE:
- Last Traded Price (LTP)
- Bid/Ask prices
- Volume
- OHLC for current candle
- Tick-by-tick updates

================================================================================
                            CONTACT & SUPPORT
================================================================================

For questions or issues:
- Read docs/ folder for detailed guides
- Check logs/ folder for error messages
- Start with small trades
- Learn each strategy before using

REMEMBER: The goal is consistent small profits, not hitting jackpot!

Good luck with your trading journey! 🚀

================================================================================
