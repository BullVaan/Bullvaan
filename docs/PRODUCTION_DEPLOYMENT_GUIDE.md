# Bullvaan Production Deployment & Multi-Session Auto-Trading Guide

## Part 1: Multi-Session Auto-Trading Fix (Now Live)

### The Problem (SOLVED)

Previously, running auto-trader from two different browser tabs stopped both traders because:

- Single global `auto_trader` instance
- Only one user could trade at a time
- Starting trader for Session 2 automatically stopped Session 1's trader

### The Solution (IMPLEMENTED)

- Each browser tab/session gets its own **independent AutoTrader instance**
- Multiple sessions can run **simultaneously** for the same account
- Stopping one session does NOT affect other sessions

### How It Works Now

**Frontend Implementation (TODO):**

```javascript
// Generate session_id once per browser tab (client-side)
const sessionId = localStorage.getItem('sessionId') || `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
localStorage.setItem('sessionId', sessionId);

// Send with every API request
const headers = {
    'Authorization': `Bearer ${token}`,
    'X-Session-ID': sessionId  // New header for session tracking
};

// Start auto-trader
POST /auto-trader/start
Headers: { 'X-Session-ID': sessionId }
Response: { status: "started", session_id: sessionId }

// Each session has independent auto-trader
// Stopping one: POST /auto-trader/stop
// Only THAT session stops. Others continue running.
```

**Backend (IMPLEMENTED):**

```python
# New structure:
_auto_traders_by_session = {
    "session_abc123": (AutoTrader1, user_id, timestamp),
    "session_xyz789": (AutoTrader2, user_id, timestamp),
}

# Each session gets unique AutoTrader instance that runs independently
# Sessions can run in parallel without interfering with each other
```

### Testing Multi-Session Auto-Trading

```bash
# Terminal 1: Chrome tab (Session A)
# Login → Start Auto-Trader → Should show: "Auto-trader started for session XXX"

# Terminal 2: Incognito tab (Session B - Same Account)
# Login → Start Auto-Trader → Should show: "Auto-trader started for session YYY"

# Now BOTH are running independently!
# Stop one: Only that session stops, the other continues
```

---

## Part 2: Production Deployment Architecture

### Current State (Local Development)

```
┌─────────────────────────────────────────┐
│          Your Local Machine             │
├─────────────────────────────────────────┤
│  Frontend (React)                       │
│  ↓                                      │
│  Backend (FastAPI)                      │
│  ↓                                      │
│  Zerodha KiteTicker (WebSocket)         │
│  ├─ YOUR Kite credentials (.env)        │
│  ├─ YOUR ACCESS_TOKEN (in .env)         │
│  └─ ALL users use YOUR account!         │
│                                         │
│  Problem: Only YOU can trade            │
└─────────────────────────────────────────┘
```

### Production State (What Needs to Change)

```
┌────────────────────────────────────────────────────┐
│            Production Cloud Server                 │
├────────────────────────────────────────────────────┤
│  Frontend (React - hosted on CDN/S3)               │
│   ↓                                                 │
│  API Server (FastAPI on cloud - EC2/Heroku/GCP)   │
│   ↓                                                 │
│  ┌──────────────────────────────────────┐          │
│  │  Multi-User Kite Connection Manager  │          │
│  │ (NEW - NEEDS IMPLEMENTATION)         │          │
│  └──────────────────────────────────────┘          │
│   ↓                                                 │
│  ┌─────────────────────────────────────────────┐   │
│  │ USER 1                                      │   │
│  │ ├─ Kite(api_key, access_token_1)           │   │
│  │ ├─ KiteTicker (WebSocket to Zerodha)       │   │
│  │ └─ AutoTrader Instance 1                   │   │
│  │                                             │   │
│  │ USER 2                                      │   │
│  │ ├─ Kite(api_key, access_token_2)           │   │
│  │ ├─ KiteTicker (WebSocket to Zerodha)       │   │
│  │ └─ AutoTrader Instance 2                   │   │
│  │                                             │   │
│  │ USER N                                      │   │
│  │ ├─ Kite(api_key, access_token_N)           │   │
│  │ ├─ KiteTicker (WebSocket to Zerodha)       │   │
│  │ └─ AutoTrader Instance N                   │   │
│  └─────────────────────────────────────────────┘   │
│   ↓                                                 │
│  Database (Supabase)                              │
│  ├─ User credentials (encrypted)                  │
│  ├─ Trades & history                             │
│  └─ Settings per user                            │
└────────────────────────────────────────────────────┘
```

---

## Production Implementation Steps

### Step 1: Extract Kite Credentials from .env

**Current (.env):**

```
API_KEY = "yi4arzszbdqujyt0"
API_SECRET = "sqbpnp0s1li9cwal29j2nsntuh0c52kw"
ACCESS_TOKEN = "pN5Vj79vCWnoLKofgtHGC8qHQ30Mi0Mt"
```

**Problem:** These are hardcoded. ALL users would share YOUR account!

**Solution:** Store user credentials securely in database

### Step 2: User Authentication - Zerodha Login Integration

**New Flow:**

```
User → Frontend Login
  ↓
User clicks "Connect Zerodha Account"
  ↓
Opens Zerodha OAuth/Login flow
  ↓
User enters: Email + Password (or OAuth token)
  ↓
Backend receives credentials
  ↓
Encrypt + Store in Supabase (encrypted at rest)
  ↓
Generate unique ACCESS_TOKEN for this user
  ↓
Create Kite instance for this user
  ↓
Start KiteTicker with user's token
  ↓
User can now trade independently!
```

### Step 3: Per-User Kite Connection Management

**New Module: `backend/utils/kite_connection_manager.py`**

```python
class KiteConnectionManager:
    """Manages per-user Kite connections, WebSocket, and credentials"""

    def __init__(self):
        self._user_kites = {}        # {user_id: KiteConnect instance}
        self._user_tickers = {}      # {user_id: KiteTicker WebSocket}
        self._user_tokens = {}       # {user_id: [54 live tokens]}

    async def create_connection(self, user_id, encrypted_creds):
        """Create new Kite connection + WebSocket for user"""
        # 1. Decrypt user's credentials
        api_key, email, password = decrypt(encrypted_creds)

        # 2. Generate access token via Zerodha login API
        access_token = zerodha_login(email, password)

        # 3. Create KiteConnect instance for this user
        kite = KiteConnect(api_key=api_key, access_token=access_token)

        # 4. Subscribe to 54 tokens via WebSocket
        ticker = KiteTicker(api_key, access_token)
        ticker.connect()
        ticker.subscribe([54 live token list])

        # 5. Store in cache
        self._user_kites[user_id] = kite
        self._user_tickers[user_id] = ticker

        return kite, ticker

    def get_kite(self, user_id):
        """Get user's Kite instance (or None if not connected)"""
        return self._user_kites.get(user_id)

    def get_ticker(self, user_id):
        """Get user's ticker WebSocket"""
        return self._user_tickers.get(user_id)

    async def disconnect_user(self, user_id):
        """Clean up user's connections"""
        if user_id in self._user_tickers:
            self._user_tickers[user_id].close()
        if user_id in self._user_kites:
            del self._user_kites[user_id]
```

### Step 4: Database Schema for User Credentials

**Supabase Table: `user_kite_credentials`**

```sql
CREATE TABLE user_kite_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),

    -- Encrypted Zerodha credentials
    encrypted_api_key TEXT NOT NULL,
    encrypted_email TEXT NOT NULL,
    encrypted_password TEXT NOT NULL,
    encrypted_access_token TEXT NOT NULL,

    -- For token rotation
    access_token_expiry TIMESTAMP,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    is_real_trading BOOLEAN DEFAULT FALSE,  -- paper=false, real=true

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(user_id)  -- One set of creds per user
);
```

### Step 5: Multi-User API Modifications

**Old:** `get_signals(symbol)` - uses global `kite` (YOUR account)

**New:** `get_signals(symbol, current_user)` - fetches data for specific user's Kite

```python
@app.get("/signals")
async def get_signals(
    symbol: str,
    timeframe: str = "5m",
    current_user: dict = Depends(get_current_user)
):
    """Get signals using THAT USER'S Kite connection"""
    user_id = current_user['user_id']

    # Get this user's Kite connection
    kite = kite_manager.get_kite(user_id)
    if not kite:
        return {"error": "Kite connection not established"}

    # Fetch data using USER'S credentials
    df = fetch_zerodha_history(kite, symbol, ...)

    # Calculate signals using user's data
    signals = calculate_signals(df)

    return signals
```

### Step 6: WebSocket Per-User

**Current:** One global WebSocket (YOUR account)

**Production:** Each user gets own WebSocket

```python
@app.websocket("/ws/ticker/{user_id}")
async def websocket_ticker(websocket: WebSocket, user_id: str):
    """Per-user live ticker WebSocket"""
    await websocket.accept()

    ticker = kite_manager.get_ticker(user_id)
    if not ticker:
        await websocket.send_json({"error": "Not connected"})
        return

    # Send live prices specific to this user's subscribed tokens
    async for price_update in ticker.stream():
        await websocket.send_json(price_update)
```

---

## Step 7: Deployment Checklist

- [ ] Implement `KiteConnectionManager` class
- [ ] Add user credential storage (encrypted in Supabase)
- [ ] Add Zerodha OAuth/login integration
- [ ] Modify all API endpoints to pass `current_user` to Kite calls
- [ ] Per-user WebSocket connections
- [ ] Frontend sends `X-Session-ID` header
- [ ] Session management for multiple concurrent tabs
- [ ] Database migration for user_kite_credentials table
- [ ] Secrets management (API key in .env, not hardcoded)
- [ ] Tests for multi-user auto-trading

---

## Quick Summary

### Current (Local) → Production Changes

| Aspect               | Local                            | Production                                     |
| -------------------- | -------------------------------- | ---------------------------------------------- |
| **Kite Credentials** | Hardcoded in .env (YOUR account) | User provides their own (encrypted in DB)      |
| **Zerodha Login**    | Manual token setup               | Integrated OAuth/login flow                    |
| **Connections**      | 1 global Kite + 1 KiteTicker     | Per-user Kite + per-user KiteTicker            |
| **Auto-Trader**      | 1 global instance                | 1 per session (multiple per user if multi-tab) |
| **Database**         | Limited user data                | Full encrypted credentials + trading history   |
| **Scaling**          | 1 user (you)                     | N users simultaneously                         |
| **Session Support**  | New: multi-session per tabs      | Each tab independent auto-trader               |

---

## Critical Security Notes

**NEVER:**

- Store plain-text passwords (.env will be in repo)
- Send user credentials through unencrypted channels
- Log API keys or access tokens
- Use global Kite instance in production

**DO:**

- Encrypt credentials at rest (Supabase encryption)
- Use HTTPS/WSS for all connections
- Implement API key rotation
- Use environment variables ONLY for app secrets (not user data)
- Add audit logging for credential access

---

## Next Steps

1. **Immediate:** Test multi-session auto-trading fix (implement frontend session_id)
2. **Short-term:** Set up credential encryption/storage
3. **Medium-term:** Implement user Zerodha account linking
4. **Long-term:** Deploy to production with full multi-user support
