# Bullvaan Project - Structure Reorganization Action Plan

**Prepared:** March 25, 2026  
**Total Estimated Time:** 30-40 hours  
**Recommended Team:** 1-2 developers working systematically through phases

---

## PHASE 1: FRONTEND STRUCTURE (6-8 hours)

### Step 1.1: Standardize File Extensions (1 hour)

**Goal:** All React components use `.jsx`, utils use `.js`

**Files to Rename:**

```
From:                           To:
────────────────────────────────────────────────────
src/pages/Dashboard.js    →    src/pages/Dashboard.jsx
src/pages/CandlesCharts.js →   src/pages/CandlesCharts.jsx
src/pages/SwingTrade.js   →    src/pages/SwingTrade.jsx
src/pages/Login.js        →    src/pages/Login.jsx
src/pages/Signup.js       →    src/pages/Signup.jsx
src/components/MarketStatus.js → src/components/MarketStatus.jsx
src/components/MarketTicker.js → src/components/MarketTicker.jsx
src/components/OptionSuggestion.js → src/components/OptionSuggestion.jsx
src/components/PremarketSignals.js → src/components/PremarketSignals.jsx
src/components/RoleCard.js → src/components/RoleCard.jsx
```

**Keep as `.js`:**

- src/utils/api.js ✅
- src/utils/auth.js ✅
- src/App.js (main, can be either)
- src/index.js (entry point)

**Commands:**

```bash
cd p:\Projects\Bullvaan\frontend\src

# Rename in pages/
ren pages\Dashboard.js pages\Dashboard.jsx
ren pages\CandlesCharts.js pages\CandlesCharts.jsx
ren pages\SwingTrade.js pages\SwingTrade.jsx
ren pages\Login.js pages\Login.jsx
ren pages\Signup.js pages\Signup.jsx

# Rename in components/
ren components\MarketStatus.js components\MarketStatus.jsx
ren components\MarketTicker.js components\MarketTicker.jsx
ren components\OptionSuggestion.js components\OptionSuggestion.jsx
ren components\PremarketSignals.js components\PremarketSignals.jsx
ren components\RoleCard.js components\RoleCard.jsx
```

**After renaming, verify no import errors:**

```bash
npm start
# Check console for import errors
# Fix any import paths that reference old filenames
```

---

### Step 1.2: Move Layout Components (1 hour)

**Goal:** Move Sidebar and ProtectedRoute to layout/

**Current Structure:**

```
src/
├── components/
│   ├── Sidebar.jsx           ← MOVE
│   ├── ProtectedRoute.jsx    ← MOVE
│   ├── RoleCard.jsx
│   ├── StockModal.jsx
│   ├── MarketStatus.jsx
│   ├── MarketTicker.jsx
│   ├── OptionSuggestion.jsx
│   └── PremarketSignals.jsx
└── layout/
    └── MainLayout.jsx
```

**New Structure:**

```
src/
├── components/
│   ├── RoleCard.jsx
│   ├── StockModal.jsx
│   ├── MarketStatus.jsx
│   ├── MarketTicker.jsx
│   ├── OptionSuggestion.jsx
│   └── PremarketSignals.jsx
└── layout/
    ├── MainLayout.jsx
    ├── Sidebar.jsx           ← MOVE HERE
    └── ProtectedRoute.jsx    ← MOVE HERE
```

**Commands:**

```bash
cd p:\Projects\Bullvaan\frontend\src

# Move files
move components\Sidebar.jsx layout\
move components\ProtectedRoute.jsx layout\
```

**Update Imports:**

In `layout/MainLayout.jsx`, change:

```javascript
// BEFORE:
import Sidebar from "../components/Sidebar";

// AFTER:
import Sidebar from "./Sidebar";
```

In `App.jsx`, change:

```javascript
// BEFORE:
import ProtectedRoute from "./components/ProtectedRoute";

// AFTER:
import ProtectedRoute from "./layout/ProtectedRoute";
```

**Verify:** Run `npm start` and check for import errors.

---

### Step 1.3: Create Feature-Based Component Organization (2 hours)

**Goal:** Organize components by feature for discoverability

**New Structure:**

```
src/components/
├── common/                   ← Reusable components
│   ├── RoleCard.jsx
│   └── StockModal.jsx        (Used in SwingTrade but could be generic)
├── dashboard/                ← Dashboard-specific
│   ├── MarketStatus.jsx
│   ├── MarketTicker.jsx
│   ├── OptionSuggestion.jsx
│   └── RoleCard.jsx          (or leave in common)
└── swingTrade/               ← SwingTrade-specific
    ├── PremarketSignals.jsx
    └── StockModal.jsx        (or leave in common)
```

**Commands:**

```bash
cd p:\Projects\Bullvaan\frontend\src\components

# Create folders
mkdir common
mkdir dashboard
mkdir swingTrade

# Move to common/
move RoleCard.jsx common\

# Move to dashboard/
move MarketStatus.jsx dashboard\
move MarketTicker.jsx dashboard\
move OptionSuggestion.jsx dashboard\

# Move to swingTrade/
move PremarketSignals.jsx swingTrade\
```

**For StockModal.jsx:** Decide:

- If only used in SwingTrade → move to `swingTrade/`
- If potentially reused → keep in `common/`

**Update Imports in components:**

Example - `components/common/RoleCard.jsx`:

```javascript
// No change needed unless it had relative imports
```

Example - `components/dashboard/MarketStatus.jsx`:

```javascript
// No change needed unless it had relative imports to other components
```

**Update Imports in Pages:**

In `pages/Dashboard.jsx`:

```javascript
// BEFORE:
import RoleCard from "../components/RoleCard";
import OptionSuggestion from "../components/OptionSuggestion";
import MarketTicker from "../components/MarketTicker";
import MarketStatus from "../components/MarketStatus";

// AFTER:
import RoleCard from "../components/dashboard/RoleCard";
import OptionSuggestion from "../components/dashboard/OptionSuggestion";
import MarketTicker from "../components/dashboard/MarketTicker";
import MarketStatus from "../components/dashboard/MarketStatus";
```

In `pages/SwingTrade.jsx`:

```javascript
// BEFORE:
import StockModal from "../components/StockModal";
import PremarketSignals from "../components/PremarketSignals";

// AFTER:
import StockModal from "../components/swingTrade/StockModal";
import PremarketSignals from "../components/swingTrade/PremarketSignals";
```

**Verify:** Run `npm start` and verify all pages load.

---

### Step 1.4: Create Missing Infrastructure Folders (2 hours)

**Goal:** Add structure for constants, services, and helpers

**Create Folder Structure:**

```bash
cd p:\Projects\Bullvaan\frontend\src

# Create new folders
mkdir constants
mkdir services
mkdir utils\helpers
```

**Create `src/constants/index.js`:**

```javascript
// API Endpoints
export const API_ENDPOINTS = {
  BASE_URL: "http://localhost:8000",
  INDICES: "/indices",
  TRADES: "/trades",
  AUTO_TRADER: "/auto-trader",
  LOGIN: "/login",
  SIGNUP: "/signup",
};

// Local Storage Keys
export const STORAGE_KEYS = {
  ACCESS_TOKEN: "access_token",
  USER_ID: "user_id",
  EMAIL: "email",
  SESSION_ID: "sessionId",
};

// UI Constants
export const UI = {
  MODE_OPTIONS: { PAPER: "paper", REAL: "real" },
  TRADE_STATUS: { OPEN: "open", CLOSED: "closed" },
  TIMEFRAMES: ["1m", "5m", "15m", "30m", "1h", "4h", "daily"],
};
```

**Create `src/services/api.js`:**
Move relevant code from `utils/api.js`:

```javascript
import { API_ENDPOINTS } from "../constants";

export async function apiCall(endpoint, options = {}) {
  try {
    const response = await fetch(
      `${API_ENDPOINTS.BASE_URL}${endpoint}`,
      options,
    );
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error(`API Error [${endpoint}]:`, error.message);
    throw error;
  }
}
```

**Create `src/services/auth.js`:**
Move auth logic from `utils/auth.js`:

```javascript
// Move token management functions here
// Reference existing utils/auth.js for functions to move
```

**Update imports in components/pages** to use new paths:

```javascript
// BEFORE:
import { getAuthHeaders } from "../utils/auth";
import { API_ENDPOINTS } from "../constants"; // or hardcoded

// AFTER:
import { getAuthHeaders } from "../services/auth";
import { API_ENDPOINTS } from "../constants";
```

**Status:** Old `utils/` folder can be kept but will become minimal.

---

### Step 1.5: Verify Frontend Changes

**Commands:**

```bash
cd p:\Projects\Bullvaan\frontend

# Install dependencies if needed
npm install

# Test the application
npm start

# Check for errors in console
# Visit http://localhost:3000
# Test key pages: Login, Dashboard, SwingTrade
```

**Checklist:**

- [ ] All pages load without errors
- [ ] No import path errors in console
- [ ] Navigation works
- [ ] Components render correctly

---

## PHASE 2: BACKEND DATABASE & TESTS CONSOLIDATION (8-10 hours)

### Step 2.1: Migrate Database Code (3 hours)

**Goal:** Move all database-related code into `backend/database/`

**Current Scattered Code:**

```
backend/utils/supabase_client.py      ← Move to database/client.py
backend/utils/trades_db.py            ← Merge to database/trades.py
backend/utils/auto_trader_db.py       ← Merge to database/trades.py
backend/utils/user_credentials.py     ← Move to database/credentials.py
```

**Step 1: Create database/client.py**

Copy `backend/utils/supabase_client.py` to `backend/database/client.py`:

```bash
cd p:\Projects\Bullvaan\backend
copy utils\supabase_client.py database\client.py
```

**Step 2: Merge trade databases**

Create `backend/database/trades.py` by combining:

- Functions from `backend/utils/trades_db.py`
- Functions from `backend/utils/auto_trader_db.py`

Structure it as:

```python
"""
Unified Trade Management Layer

Handles both manual trades and auto-trader trades.
No distinction in storage - both saved same way.
"""

from .client import supabase
from typing import Dict, List, Optional

# ───────────────────────────────────
# Manual Trade Operations (from trades_db.py)
# ───────────────────────────────────

def save_trade(trade: dict) -> dict:
    """Save a manual trade"""
    # ... code from trades_db.py ...

def get_user_trades(user_id: str, date: str = None) -> list:
    """Get trades for user"""
    # ... code from trades_db.py ...

# ───────────────────────────────────
# Auto-Trader Trade Operations (from auto_trader_db.py)
# ───────────────────────────────────

def save_auto_trade(trade: dict, user_id=None) -> dict:
    """Save auto-generated trade"""
    # ... code from auto_trader_db.py ...
    # Consider if separate from save_trade() or unified

def get_active_trades(user_id: str) -> dict:
    """Get active trades"""
    # ... merged logic ...

# ───────────────────────────────────
# Utility Functions
# ───────────────────────────────────

def get_trade(trade_id: str) -> dict:
    # ...

def update_trade_sell(trade_id: str, user_id: str, sell_price: float, sell_time: str) -> dict:
    # ...
```

**Commands:**

```bash
cd p:\Projects\Bullvaan\backend

# Copy credentials file
copy utils\user_credentials.py database\credentials.py

# Create __init__.py to export all
# (see next step)
```

**Step 3: Create `backend/database/__init__.py`**

```python
"""Database access layer - unified interface for all data operations"""

from .client import supabase
from .trades import (
    save_trade, get_trade, get_user_trades,
    get_user_trades_by_date, get_active_trades,
    update_trade_sell, delete_trade,
    save_auto_trade, update_auto_trade_sell, delete_auto_trade,
    load_trades_for_autotrader
)
from .credentials import (
    save_user_credentials, get_user_credentials,
    user_has_credentials, delete_user_credentials
)

__all__ = [
    'supabase',
    # Trade operations
    'save_trade', 'get_trade', 'get_user_trades',
    'get_user_trades_by_date', 'get_active_trades',
    'update_trade_sell', 'delete_trade',
    'save_auto_trade', 'update_auto_trade_sell', 'delete_auto_trade',
    'load_trades_for_autotrader',
    # Credentials
    'save_user_credentials', 'get_user_credentials',
    'user_has_credentials', 'delete_user_credentials'
]
```

**Step 4: Update all imports**

Replace imports across codebase:

**In `backend/api/server.py`:**

```python
# BEFORE:
from utils.trades_db import save_trade, get_user_trades, get_active_trades
from utils.auto_trader_db import set_auto_trader_user_id, save_auto_trade
from utils.supabase_client import supabase

# AFTER:
from database import (
    save_trade, get_user_trades, get_active_trades,
    save_auto_trade, supabase
)
from database.auto_trader import (  # Or include in main trades.py
    set_auto_trader_user_id, clear_auto_trader_user_id
)
```

**In `backend/engine/auto_trader.py`:**

```python
# BEFORE:
from utils.auto_trader_db import (
    set_auto_trader_user_id, clear_auto_trader_user_id, get_auto_trader_user_id,
    load_trades_for_autotrader, save_auto_trade, update_auto_trade_sell, delete_auto_trade
)

# AFTER:
from database import (
    load_trades_for_autotrader, save_auto_trade,
    update_auto_trade_sell, delete_auto_trade
)
from database.auto_trader import (
    set_auto_trader_user_id, clear_auto_trader_user_id, get_auto_trader_user_id
)
```

**Find and Replace Tool:**

```bash
cd p:\Projects\Bullvaan\backend

# Find all references to old imports
# Use VS Code Find & Replace (Ctrl+H):
# Find: from utils\.trades_db import
# Replace with: from database import

# Find: from utils\.auto_trader_db import
# Replace with: from database import

# Find: from utils\.supabase_client import
# Replace with: from database import

# Find: from utils\.user_credentials import
# Replace with: from database import
```

---

### Step 2.2: Migrate Test Files (2 hours)

**Goal:** Move all tests to `backend/tests/`

**Current Locations:**

```
backend/test_zerodha.py           → backend/tests/test_zerodha.py
test_live_data.py (in project root!) → backend/tests/integration/test_live_data.py
```

**Commands:**

```bash
cd p:\Projects\Bullvaan\backend

# Move test files
move test_zerodha.py tests\
```

**For test_live_data.py:**

```bash
# From project root
move test_live_data.py backend\tests\integration\
```

**Create backend/tests/**init**.py:**

```python
"""Backend test suite"""
```

**Create backend/tests/conftest.py** (pytest configuration):

```python
"""pytest configuration and fixtures"""

import pytest
import os
from dotenv import load_dotenv

# Load test environment
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

@pytest.fixture
def api_client():
    """FastAPI test client"""
    from fastapi.testclient import TestClient
    from api.server import app
    return TestClient(app)

@pytest.fixture
def sample_trade():
    """Sample trade fixture"""
    return {
        'name': 'NIFTY 25400 CE',
        'lot': 1,
        'buy_price': 450.0,
        'sell_price': 475.0,
        'buy_time': '09:15',
        'sell_time': '10:30'
    }
```

**Update imports in test files:**

In `tests/test_zerodha.py`:

```python
# BEFORE:
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# AFTER:
# pytest handles imports automatically when in tests/ folder
```

---

### Step 2.3: Create pytest.ini Configuration (15 min)

**Create `backend/pytest.ini`:**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --strict-markers
markers =
    integration: Integration tests
    unit: Unit tests
    slow: Slow running tests
```

**Create `backend/tests/fixtures/` for test data:**

```bash
cd p:\Projects\Bullvaan\backend\tests
mkdir fixtures
```

**Create `backend/tests/fixtures/test_data.json`:**

```json
{
  "sample_trade": {
    "name": "NIFTY 25400 CE",
    "lot": 1,
    "buy_price": 450.0,
    "sell_price": 475.0,
    "buy_time": "09:15",
    "sell_time": "10:30"
  }
}
```

---

### Step 2.4: Remove Old Files

**After verifying all imports work, delete:**

```bash
cd p:\Projects\Bullvaan\backend\utils

# These are now in database/
del supabase_client.py
del trades_db.py
del auto_trader_db.py
del user_credentials.py
```

**Verify:** Run tests:

```bash
cd p:\Projects\Bullvaan\backend
pytest tests/ -v
```

---

## PHASE 3: BACKEND UTILITIES REORGANIZATION (6-8 hours)

### Step 3.1: Create Utils Subcategories (2 hours)

**Current state:**

```
backend/utils/
├── auth.py                    ← Security
├── logger.py                  ← Infrastructure
├── nifty50_stocks.py          ← Data
├── nse_live.py                ← Data/API
├── supabase_client.py         ← [MOVED to database/]
├── zerodha_data.py            ← Data/API
├── generate_access_token.py   ← CLI Tool [MOVE to scripts/]
└── (trades_db.py, auto_trader_db.py, user_credentials.py already moved)
```

**New structure:**

```bash
cd p:\Projects\Bullvaan\backend\utils

# Create subdirectories
mkdir security
mkdir data
mkdir legacy  # for gradual migration
```

**Step 1: Organize Security**

```bash
# Move auth to security/
move auth.py security\

# Create backend/utils/security/__init__.py
```

**backend/utils/security/**init**.py:**

```python
"""Security utilities - authentication, encryption, tokens"""

from .auth import (
    hash_password, verify_password, create_access_token,
    verify_token, encrypt_credential, decrypt_credential,
    extract_token_from_header, get_current_user
)

__all__ = [
    'hash_password', 'verify_password', 'create_access_token',
    'verify_token', 'encrypt_credential', 'decrypt_credential',
    'extract_token_from_header', 'get_current_user'
]
```

**Step 2: Organize Data Utilities**

```bash
# Move data files to data/
move nifty50_stocks.py data\nifty50.py
move nse_live.py data\nse.py
move zerodha_data.py data\zerodha.py

# Create backend/utils/data/__init__.py
```

**backend/utils/data/**init**.py:**

```python
"""Data fetching and utilities"""

from .nifty50 import get_nifty50_symbols, get_stock_by_nse_symbol
from .nse import fetch_nse_indices
from .zerodha import fetch_zerodha_history, fetch_india_vix_zerodha

__all__ = [
    'get_nifty50_symbols', 'get_stock_by_nse_symbol',
    'fetch_nse_indices',
    'fetch_zerodha_history', 'fetch_india_vix_zerodha'
]
```

---

### Step 3.2: Create Scripts Folder for CLI Tools (1 hour)

**Goal:** Move CLI tools out of utils/

```bash
cd p:\Projects\Bullvaan\backend

# Create scripts folder
mkdir scripts
```

**Move CLI tool:**

```bash
move utils\generate_access_token.py scripts\
```

**Create `backend/scripts/__init__.py`:**

```python
"""Command-line scripts and utilities"""
```

**Create `backend/scripts/README.md`:**

````markdown
# Backend Scripts

CLI tools for development and operations.

## generate_access_token.py

Generates Zerodha access tokens for testing.

Usage:

```bash
python -m scripts.generate_access_token
```
````

```

---

### Step 3.3: Update All Imports (2-3 hours)

**Search for all import statements:**

Using Find & Replace (Ctrl+H):

```

# Find: from utils.auth import

Replace: from utils.security.auth import

# Find: from utils.nifty50_stocks import

Replace: from utils.data.nifty50 import

# Find: from utils.nse_live import

Replace: from utils.data.nse import

# Find: from utils.zerodha_data import

Replace: from utils.data.zerodha import

# Find: from utils import auth

Replace: from utils.security import auth

# Find: from utils import nifty50_stocks

Replace: from utils.data import nifty50 as nifty50_stocks

````

**Check specific files:**
- `backend/api/server.py`
- `backend/api/login.py`
- `backend/api/signup.py`
- `backend/engine/auto_trader.py`
- `backend/engine/premarket_signals.py`
- All files in `backend/strategies/`

---

### Step 3.4: Verify Backend Changes

```bash
cd p:\Projects\Bullvaan\backend

# Test imports
python -c "from database import save_trade; print('✓ Database imports OK')"
python -c "from utils.security import create_access_token; print('✓ Security imports OK')"
python -c "from utils.data import fetch_nse_indices; print('✓ Data imports OK')"

# If using uvicorn:
uvicorn api.server:app --reload

# Check for import errors in startup
````

---

## PHASE 4: ADVANCED BACKEND IMPROVEMENTS (4-6 hours)

### Step 4.1: Organize Strategy Files (2 hours)

**Current naming:** `strategy_1_*.py`, `strategy_2_*.py`, etc. with gaps (1,2,3,5,6,8,9)

**Option A: Organize by Category (Recommended)**

```bash
cd p:\Projects\Bullvaan\backend\strategies

mkdir trend
mkdir momentum
mkdir strength

# Move trend strategies
move strategy_1_moving_average.py trend\moving_average.py
move strategy_5_ema_crossover.py trend\ema_crossover.py

# Move momentum strategies
move strategy_2_rsi.py momentum\rsi.py
move strategy_3_macd.py momentum\macd.py
move strategy_8_stochastic.py momentum\stochastic.py

# Move strength strategies
move strategy_6_supertrend.py strength\supertrend.py
move strategy_9_adx.py strength\adx.py

# Keep base strategy at root
# base_strategy.py stays
```

**Update `backend/strategies/__init__.py`:**

```python
"""Trading Strategies Package - Organized by Category"""

from .base_strategy import BaseStrategy, SIGNAL_BUY, SIGNAL_SELL, SIGNAL_NEUTRAL

# Trend Strategies (Follow market direction)
from .trend.moving_average import MovingAverageStrategy
from .trend.ema_crossover import EMACrossoverStrategy

# Momentum Strategies (Measure speed of price changes)
from .momentum.rsi import RSIStrategy
from .momentum.macd import MACDStrategy
from .momentum.stochastic import StochasticStrategy

# Strength Strategies (Measure trend strength)
from .strength.supertrend import SupertrendStrategy
from .strength.adx import ADXStrategy

__all__ = [
    'BaseStrategy', 'SIGNAL_BUY', 'SIGNAL_SELL', 'SIGNAL_NEUTRAL',
    # Trend
    'MovingAverageStrategy', 'EMACrossoverStrategy',
    # Momentum
    'RSIStrategy', 'MACDStrategy', 'StochasticStrategy',
    # Strength
    'SupertrendStrategy', 'ADXStrategy',
]
```

**Create `backend/strategies/trend/__init__.py`:**

```python
"""Trend-following strategies"""
from .moving_average import MovingAverageStrategy
from .ema_crossover import EMACrossoverStrategy
__all__ = ['MovingAverageStrategy', 'EMACrossoverStrategy']
```

Similar for `momentum/__init__.py` and `strength/__init__.py`.

**Update imports in files that import strategies:**

In `backend/api/server.py`:

```python
# BEFORE:
from strategies import (
    MovingAverageStrategy, RSIStrategy, MACDStrategy,
    EMACrossoverStrategy, SupertrendStrategy, StochasticStrategy, ADXStrategy
)

# AFTER:
# No change needed if __init__.py exports correctly
from strategies import (
    MovingAverageStrategy, RSIStrategy, MACDStrategy,
    EMACrossoverStrategy, SupertrendStrategy, StochasticStrategy, ADXStrategy
)
```

In `backend/engine/auto_trader.py`:

```python
# BEFORE:
from strategies.strategy_9_adx import ADXStrategy

# AFTER:
from strategies.strength.adx import ADXStrategy
# OR (if exported from __init__.py):
from strategies import ADXStrategy
```

---

### Step 4.2: Improve Engine Organization (1 hour)

**Current:**

```
backend/engine/
├── auto_trader.py
├── premarket_alerts.py
├── premarket_signals.py
└── __init__.py
```

**Recommended:**

```
backend/engine/
├── auto_trader.py
├── premarket/
│   ├── __init__.py
│   ├── signals.py      (move premarket_signals.py)
│   └── alerts.py       (move premarket_alerts.py)
└── __init__.py
```

**Commands:**

```bash
cd p:\Projects\Bullvaan\backend\engine

mkdir premarket

move premarket_signals.py premarket\signals.py
move premarket_alerts.py premarket\alerts.py
```

**Create `backend/engine/premarket/__init__.py`:**

```python
"""Premarket analysis system - signals and alerts"""

from .signals import PremarketSignalEngine
from .alerts import PremarketAlertManager, AlertSeverity, AlertType

__all__ = [
    'PremarketSignalEngine',
    'PremarketAlertManager', 'AlertSeverity', 'AlertType'
]
```

**Update imports in `backend/api/server.py`:**

```python
# BEFORE:
from engine.premarket_signals import PremarketSignalEngine
from engine.premarket_alerts import PremarketAlertManager, AlertSeverity

# AFTER:
from engine.premarket import PremarketSignalEngine, PremarketAlertManager, AlertSeverity
```

---

### Step 4.3: Configure Backend Config Management (1-2 hours)

**Create `backend/config/` folder:**

```bash
cd p:\Projects\Bullvaan\backend

mkdir config
```

**Create `backend/config/__init__.py`:**

```python
"""Configuration management - environment-based config loading"""

import os
import json
from pathlib import Path

DEFAULT_ENV = os.getenv('ENVIRONMENT', 'dev')

def load_trading_config(env: str = DEFAULT_ENV) -> dict:
    """Load trading rules configuration"""

    # Try environment-specific config first
    env_config = Path(__file__).parent / f'trading_rules.{env}.json'
    if env_config.exists():
        with open(env_config) as f:
            return json.load(f)

    # Fall back to default
    default_config = Path(__file__).parent / 'trading_rules.json'
    with open(default_config) as f:
        return json.load(f)

# Load on import
trading_rules = load_trading_config()
```

**Move trading_rules.json:**

```bash
move config\trading_rules.json backend\config\
```

**Update imports in backend code:**

In `backend/engine/auto_trader.py`:

```python
# BEFORE:
_CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'trading_rules.json')
with open(_CONFIG_FILE, 'r') as f:
    _config = json.load(f)

# AFTER:
from config import trading_rules as _config
```

---

### Step 4.4: Create Environment Configuration (30 min)

**Create `backend/config/trading_rules.dev.json`:**

```json
{
  "mode": "paper",
  "total_capital": 100000,
  "max_daily_loss": 10000,
  "max_trades_per_day": 50,
  "test_mode": true,
  "log_level": "DEBUG"
}
```

**Create `backend/config/trading_rules.prod.json`:**

```json
{
  "mode": "real",
  "total_capital": 500000,
  "max_daily_loss": 50000,
  "max_trades_per_day": 20,
  "test_mode": false,
  "log_level": "INFO"
}
```

**Create `.env.example` in backend:**

```
# Zerodha Kite Connect
API_KEY=your_api_key_here
API_SECRET=your_api_secret_here
ACCESS_TOKEN=your_access_token_here

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Application
ENVIRONMENT=dev
LOG_LEVEL=INFO
TRADING_MODE=paper
```

**Add to backend/.gitignore:**

```
.env
.env.local
.env.*.local
```

---

## VERIFICATION CHECKLIST

### Frontend (30 min)

- [ ] All `.jsx` extensions in place
- [ ] All imports updated to new paths
- [ ] App starts: `npm start`
- [ ] No console errors
- [ ] All pages load: Dashboard, SwingTrade, Trades, History
- [ ] Navigation works
- [ ] Components render correctly

### Backend (1 hour)

- [ ] Database imports work: `python -c "from database import save_trade"`
- [ ] Utils reorganized and imports updated
- [ ] Tests runnable: `pytest tests/ -v`
- [ ] Server starts: `uvicorn api.server:app`
- [ ] No startup errors related to imports
- [ ] API endpoints respond
- [ ] Config loads correctly

### Overall (30 min)

- [ ] Frontend connects to backend (test one API call)
- [ ] No console errors in browser
- [ ] No console errors in server logs
- [ ] Code organization matches recommendations
- [ ] File structure documented

---

## Rollback Plan

If something breaks during migration:

1. **Revert from git:**

   ```bash
   git status  # See what changed
   git diff    # See specific changes
   git checkout -- .  # Revert all
   ```

2. **Or restore from backup:**
   - Ensure you have pre-migration backups
   - Copy back only necessary files

3. **Common issues & fixes:**
   - **Import errors:** Check old vs new path
   - **Module not found:** Verify `__init__.py` exists
   - **App won't start:** Check terminal for first error
   - **Tests fail:** Verify pytest.ini and conftest.py

---

## Success Criteria

Migration is complete when:

1. **Frontend:**
   - ✅ All components use `.jsx` extension
   - ✅ Structure is: pages/, components/{common,dashboard,swingTrade}, layout/, services/, constants/
   - ✅ All imports updated
   - ✅ App runs without errors
   - ✅ All pages accessible and functional

2. **Backend:**
   - ✅ Database code in `database/` folder
   - ✅ Tests in `tests/` folder
   - ✅ Utils organized in subfolders
   - ✅ Strategies organized by category
   - ✅ Engine modules organized
   - ✅ All imports updated and working
   - ✅ Tests pass: `pytest tests/`
   - ✅ Server starts and responds
   - ✅ Frontend still connects to backend

3. **Code Quality:**
   - ✅ No unused imports
   - ✅ No relative path hacks
   - ✅ Clear separation of concerns
   - ✅ Easy to add new features

---

## Time Breakdown

| Phase           | Task                       | Estimated       | Actual |
| --------------- | -------------------------- | --------------- | ------ |
| 1               | Frontend extensions        | 1 hour          | \_\_\_ |
| 1               | Move layout components     | 1 hour          | \_\_\_ |
| 1               | Feature-based organization | 2 hours         | \_\_\_ |
| 1               | Missing folders            | 2 hours         | \_\_\_ |
| **1 Total**     |                            | **6-8 hours**   | \_\_\_ |
| 2               | Database migration         | 3 hours         | \_\_\_ |
| 2               | Test file migration        | 2 hours         | \_\_\_ |
| 2               | pytest configuration       | 1 hour          | \_\_\_ |
| 2               | Update imports             | 2 hours         | \_\_\_ |
| **2 Total**     |                            | **8-10 hours**  | \_\_\_ |
| 3               | Utils subcategories        | 2 hours         | \_\_\_ |
| 3               | Scripts folder             | 1 hour          | \_\_\_ |
| 3               | Update imports             | 2-3 hours       | \_\_\_ |
| 3               | Verification               | 1 hour          | \_\_\_ |
| **3 Total**     |                            | **6-8 hours**   | \_\_\_ |
| 4               | Strategy organization      | 2 hours         | \_\_\_ |
| 4               | Engine organization        | 1 hour          | \_\_\_ |
| 4               | Config management          | 1-2 hours       | \_\_\_ |
| **4 Total**     |                            | **4-6 hours**   | \_\_\_ |
|                 |                            |                 |        |
| **GRAND TOTAL** |                            | **24-32 hours** | \_\_\_ |

---

**Generated:** March 25, 2026  
**For Questions:** Refer to STRUCTURE_AUDIT_REPORT.md and AUDIT_EXECUTIVE_SUMMARY.md
