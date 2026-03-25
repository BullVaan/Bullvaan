"""
Bullvaan Auto-Trading Engine (Paper Trading)
=============================================
Watches live signals + KiteTicker prices and auto-executes trades
based on signal strength rules defined in ENGINE_README.md
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from kiteconnect import KiteConnect

from strategies.strategy_9_adx import ADXStrategy
from utils.auto_trader_db import (
    set_auto_trader_user_id, clear_auto_trader_user_id, get_auto_trader_user_id,
    load_trades_for_autotrader, save_auto_trade, update_auto_trade_sell, delete_auto_trade
)

logger = logging.getLogger("auto_trader")

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
# Load config from trading_rules.json
_CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'trading_rules.json')

def _load_config():
    with open(_CONFIG_FILE, 'r') as f:
        return json.load(f)

_config = _load_config()

TRADES_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'trades.json')

SYMBOL_MAP_REVERSE = {
    "^NSEI": "NIFTY",
    "^NSEBANK": "BANKNIFTY",
    "^BSESN": "SENSEX",
}

LOT_SIZES = _config["lot_sizes"]
INDEX_PRIORITY = _config["index_priority"]
SIGNAL_RULES = _config["signal_rules"]
SL_COOLDOWN_MINUTES = _config["sl_cooldown_minutes"]
NEUTRAL_COOLDOWN_MINUTES = _config["neutral_cooldown_minutes"]
MAX_TRADES_PER_DAY = _config["max_trades_per_day"]
MAX_DAILY_LOSS = _config["max_daily_loss"]
MAX_LOTS_PER_TRADE = _config["max_lots_per_trade"]
TOTAL_CAPITAL = _config["total_capital"]
MARKET_OPEN = tuple(_config["market_open"])
MARKET_CLOSE = tuple(_config["market_close"])
EOD_EXIT = tuple(_config["eod_exit"])
TEST_MODE = _config.get("test_mode", False)
ADX_THRESHOLD = _config.get("adx_threshold", 25)

def _get_signal_rule(index_name, signal_strength):
    """Get SL/TP rule for specific index and signal strength"""
    # Try to get index-specific rule
    if index_name in SIGNAL_RULES and signal_strength in SIGNAL_RULES[index_name]:
        return SIGNAL_RULES[index_name][signal_strength]
    # Fallback: try NIFTY defaults
    if "NIFTY" in SIGNAL_RULES and signal_strength in SIGNAL_RULES["NIFTY"]:
        return SIGNAL_RULES["NIFTY"][signal_strength]
    # Ultimate fallback
    return {"target_pts": 20, "sl_pts": 25, "allow_reentry": True, "cooldown_minutes": 3}

def _ist_now():
    """Get current IST datetime"""
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


def _ist_time_tuple():
    """Get (hour, minute) in IST"""
    now = _ist_now()
    return (now.hour, now.minute)


def _is_market_hours():
    if TEST_MODE:
        return True
    h, m = _ist_time_tuple()
    after_open = (h > MARKET_OPEN[0]) or (h == MARKET_OPEN[0] and m >= MARKET_OPEN[1])
    before_close = (h < MARKET_CLOSE[0]) or (h == MARKET_CLOSE[0] and m <= MARKET_CLOSE[1])
    return after_open and before_close


def _is_eod_exit_time():
    if TEST_MODE:
        return False
    h, m = _ist_time_tuple()
    return (h > EOD_EXIT[0]) or (h == EOD_EXIT[0] and m >= EOD_EXIT[1])


# ========== MULTI-USER CONTEXT ==========
# Track the current user_id so auto_trader can tag generated trades
_current_user_id = None

_trades_cache = None

def _load_trades():
    global _trades_cache
    if _trades_cache is not None:
        return _trades_cache
    os.makedirs(os.path.dirname(TRADES_FILE), exist_ok=True)
    if not os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, 'w') as f:
            json.dump([], f)
    try:
        with open(TRADES_FILE, 'r') as f:
            content = f.read().strip()
            if not content:  # File is empty
                _trades_cache = []
            else:
                _trades_cache = json.loads(content)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading trades.json: {e}. Resetting to empty list.")
        _trades_cache = []
        # Write valid empty array back
        with open(TRADES_FILE, 'w') as f:
            json.dump([], f)
    return _trades_cache


def _save_trades(trades):
    global _trades_cache, _current_user_id
    # Inject user_id into auto-generated trades if user context is set
    if _current_user_id:
        for trade in trades:
            if not trade.get('user_id') and trade.get('auto'):
                trade['user_id'] = _current_user_id
    
    os.makedirs(os.path.dirname(TRADES_FILE), exist_ok=True)
    with open(TRADES_FILE, 'w') as f:
        json.dump(trades, f, indent=2)
    _trades_cache = trades


def _invalidate_trades_cache():
    """Call when trades.json is modified outside auto_trader (e.g. manual trade via API)"""
    global _trades_cache
    _trades_cache = None


class AutoTrader:
    """
    Auto-trading engine supporting both paper and real trading modes.
    Monitors signals and auto-executes trades based on risk management.
    Runs as an async background task inside the FastAPI server.
    """

    def __init__(self, get_signal_fn, get_option_ltp_fn, get_entry_snapshot_fn=None, kite=None, user_id=None):
        """
        get_signal_fn(symbol) -> dict with: consensus, signal_strength, india_vix
        get_option_ltp_fn(index_prefix, opt_type, strike=None) -> float LTP or None
        get_entry_snapshot_fn(prefix, opt_type) -> (atm_strike, ltp) atomic read
        kite: KiteConnect instance for admin/default (used for market data)
        user_id: User ID for per-user Kite credentials support
        """
        self.get_signal = get_signal_fn
        self.get_option_ltp = get_option_ltp_fn
        self.get_entry_snapshot = get_entry_snapshot_fn
        self.kite = kite  # Admin Kite instance (for market data)
        self.user_id = user_id  # Store user_id for multi-session trading
        
        # Try to load and initialize per-user Kite credentials
        self.user_kite = None  # Per-user Kite connection (for trading orders)
        if user_id:
            try:
                from utils.user_credentials import get_user_credentials
                creds = get_user_credentials(user_id)
                if creds:
                    # Create per-user Kite connection
                    user_kite = KiteConnect(api_key=self.kite.api_key)  # Use app's API key
                    user_kite.set_access_token(creds['access_token'])
                    self.user_kite = user_kite
                    logger.info(f"Loaded per-user Kite credentials for user {user_id}")
                else:
                    logger.warning(f"No saved Kite credentials for user {user_id} - will use admin credentials for trading")
            except Exception as e:
                logger.error(f"Error loading user credentials for {user_id}: {e}")
                logger.warning(f"Falling back to admin credentials for user {user_id}")
        
        self.enabled = False
        self.running = False
        
        # Trading mode: "paper" or "real"
        self.trading_mode = "paper"

        # Per-index state
        self._cooldowns = {}      # {prefix: datetime when cooldown expires}
        self._pending_entries = {} # {prefix: {"price": float, "opt_type": str, "strike": float}} — price confirmation

        self._daily_trade_count = 0
        self._daily_pnl = 0.0
        self._last_reset_date = None
        self._task = None
        
        # Real trading state
        self._account_cache = {}  # Cache for account info
        self._real_order_ids = {} # Map from trade_id to order_id for real trades
        self._max_position_size = 1  # Max 1 open trade at a time in real mode

    # ─── State helpers ────────────────────────────

    def _reset_daily(self):
        """Reset daily counters at start of new day"""
        today = _ist_now().date()
        if self._last_reset_date != today:
            self._daily_trade_count = 0
            self._daily_pnl = 0.0
            self._cooldowns = {}

            self._last_reset_date = today
            logger.info("Auto-trader: daily counters reset")

    def _get_kite_instance(self):
        """Get appropriate Kite instance for trading
        
        Returns per-user Kite connection if available,
        otherwise falls back to admin Kite instance
        """
        if self.user_kite:
            return self.user_kite
        return self.kite

    def _get_open_trades(self):
        """Get all open trades from database"""
        trades = load_trades_for_autotrader()
        return [t for t in trades if t.get('status') == 'open']

    def _get_open_trade_for(self, prefix):
        """Get open trade for a specific index (NIFTY/BANKNIFTY/SENSEX)"""
        for t in self._get_open_trades():
            if t['name'].upper().startswith(prefix):
                return t
        return None

    def _used_capital(self):
        """Capital currently locked in open positions"""
        total = 0
        for t in self._get_open_trades():
            qty = int(t.get('quantity', t.get('lot', 1)))
            total += t['buy_price'] * qty
        return total

    def _available_capital(self):
        return TOTAL_CAPITAL - self._used_capital()

    def _max_lots(self, atm_price, lot_size):
        """Calculate max affordable lots"""
        if atm_price <= 0:
            return 0
        cost_per_lot = atm_price * lot_size
        affordable = int(self._available_capital() // cost_per_lot)
        return min(affordable, MAX_LOTS_PER_TRADE)

    def _is_on_cooldown(self, prefix):
        """Check if index is on cooldown after SL hit"""
        exp = self._cooldowns.get(prefix)
        if exp and _ist_now() < exp:
            return True
        return False

    def _set_cooldown(self, prefix, minutes):
        if minutes > 0:
            self._cooldowns[prefix] = _ist_now() + timedelta(minutes=minutes)

    def _is_trend_strong(self, prefix):
        """Check if ADX > threshold (indicates strong trend, not consolidation)"""
        try:
            if not self.get_candles:
                return True  # Assume trend is strong if we can't get candles
            
            # Get 15-min candles for the index
            df = self.get_candles(prefix, "15minute", count=30)
            if df is None or len(df) < 15:
                logger.warning(f"Not enough candles for {prefix} ADX check")
                return True  # Allow trade if insufficient data
            
            # Calculate ADX
            adx_strategy = ADXStrategy(period=14, adx_threshold=ADX_THRESHOLD)
            signal = adx_strategy.calculate(df)
            
            # Signal NEUTRAL means ADX < 25 (consolidation)
            is_strong_trend = signal != "NEUTRAL"
            
            if not is_strong_trend:
                logger.info(f"ADX < {ADX_THRESHOLD} for {prefix} (consolidation detected)")
            
            return is_strong_trend
        except Exception as e:
            logger.error(f"Error checking ADX trend for {prefix}: {e}")
            return True  # Allow trade on error (fail-safe)

    # ─── Real Trading Functions ────────────────────

    def _get_kite_account_balance(self):
        """Fetch available margin from Kite account (cached for 1 min)"""
        if not self.kite:
            return None
        
        try:
            # Check cache
            cached = self._account_cache.get("balance")
            if cached:
                age = datetime.now() - cached["time"]
                if age.total_seconds() < 60:  # Cache for 1 minute
                    return cached["value"]
            
            # Fetch fresh - using per-user Kite if available, otherwise admin kite
            kite_instance = self._get_kite_instance()
            margins = kite_instance.margins()
            
            logger.info(f"DEBUG: Full Kite margins response: {margins}")
            
            available = 0
            
            # Priority: use equity segment (main trading account)
            if "equity" in margins and isinstance(margins["equity"], dict):
                equity_data = margins["equity"]
                logger.info(f"DEBUG: Equity data: {equity_data}")
                
                # Try to get live_balance first (actual trading power)
                if isinstance(equity_data.get("available"), dict):
                    available_dict = equity_data["available"]
                    # Use live_balance if available (actual balance including holdings)
                    if available_dict.get("live_balance"):
                        available = available_dict["live_balance"]
                        logger.info(f"DEBUG: Found equity.available.live_balance = {available}")
                    # Fallback to opening_balance
                    elif available_dict.get("opening_balance"):
                        available = available_dict["opening_balance"]
                        logger.info(f"DEBUG: Found equity.available.opening_balance = {available}")
                    # Fallback to cash
                    else:
                        available = available_dict.get("cash", 0)
                        logger.info(f"DEBUG: Found equity.available.cash = {available}")
                # If available is not a dict, try net (total available margin)
                elif equity_data.get("net"):
                    available = equity_data.get("net", 0)
                    logger.info(f"DEBUG: Found equity.net = {available}")
                else:
                    available = equity_data.get("available", 0)
                    logger.info(f"DEBUG: Found equity.available = {available}")
            # Fallback to commodity segment
            elif "commodity" in margins and isinstance(margins["commodity"], dict):
                commodity_data = margins["commodity"]
                logger.info(f"DEBUG: Commodity data: {commodity_data}")
                
                if isinstance(commodity_data.get("available"), dict):
                    available_dict = commodity_data["available"]
                    available = available_dict.get("live_balance") or available_dict.get("cash", 0)
                    logger.info(f"DEBUG: Found commodity.available = {available}")
                else:
                    available = commodity_data.get("available", 0)
                    logger.info(f"DEBUG: Found commodity.available = {available}")
            else:
                available = margins.get("available", 0)
                logger.info(f"DEBUG: Found margins.available = {available}")
            
            # Ensure available is a number
            if isinstance(available, dict):
                available = available.get("live_balance") or available.get("cash", 0)
                logger.info(f"DEBUG: Converted dict to numeric value: {available}")
            
            available = float(available) if available else 0
            
            self._account_cache["balance"] = {
                "value": available,
                "time": datetime.now()
            }
            logger.info(f"Real account available margin: ₹{available}")
            return available
        except Exception as e:
            logger.error(f"Cannot fetch Kite account balance: {e}", exc_info=True)
            return None

    def _get_available_capital(self):
        """Get available capital - real or paper based on trading mode"""
        if self.trading_mode == "real" and self.kite:
            cap = self._get_kite_account_balance()
            if cap is not None:
                return cap
        # Fallback to paper trading capital
        return TOTAL_CAPITAL - self._used_capital()

    def _max_lots(self, atm_price, lot_size):
        """Calculate max affordable lots"""
        if atm_price <= 0:
            return 0
        cost_per_lot = atm_price * lot_size
        
        # In real mode, allow only 1 lot (1 trade at a time as per user request)
        # In paper mode, allow multiple lots based on capital
        if self.trading_mode == "real":
            max_allowed = 1
        else:
            max_allowed = MAX_LOTS_PER_TRADE
        
        affordable = int(self._get_available_capital() // cost_per_lot)
        return min(affordable, max_allowed)

    # ─── Kill switch ──────────────────────────────

    def _is_killed(self):
        """Check if daily loss limit hit"""
        return self._daily_pnl <= -MAX_DAILY_LOSS

    # ─── Trade execution (paper & real) ────────────────────

    def _get_option_tradingsymbol(self, prefix, strike, opt_type):
        """Get Zerodha trading symbol for an option (e.g. NIFTY24RUL18500CE)"""
        try:
            # Get config for this index
            symbol_config = {
                "NIFTY": {"exchange": "NFO", "name": "NIFTY"},
                "BANKNIFTY": {"exchange": "NFO", "name": "BANKNIFTY"},
                "SENSEX": {"exchange": "BFO", "name": "SENSEX"},
            }
            cfg = symbol_config.get(prefix)
            if not cfg:
                return None
            
            # Get near expiry from cache or fresh
            from api.server import get_near_expiry_options, SYMBOL_CONFIG
            zerodha_symbol = cfg["name"]
            expiry_opts, expiry_date = get_near_expiry_options(zerodha_symbol)
            
            if not expiry_opts:
                return None
            
            # Find the option with matching strike and type
            matching = [
                opt for opt in expiry_opts 
                if opt['strike'] == strike and opt['instrument_type'] == opt_type
            ]
            
            if matching:
                return matching[0]['tradingsymbol']
            return None
        except Exception as e:
            logger.error(f"Error getting option tradingsymbol: {e}")
            return None

    def _execute_buy(self, prefix, option_name, buy_price, lots, lot_size, signal_strength, rule):
        """Execute buy — saves to database, real places Kite order"""
        ist = _ist_now()
        quantity = lots * lot_size
        
        # Generate unique trade ID (timestamp-based)
        trade_id = str(int(ist.timestamp() * 1000))

        trade = {
            "id": trade_id,
            "name": option_name,
            "lot": lots,
            "quantity": quantity,
            "buy_price": round(buy_price, 2),
            "sell_price": 0,
            "pnl": 0,
            "status": "open",
            "date": ist.strftime('%Y-%m-%d'),
            "buy_time": ist.strftime('%H:%M'),
            "sell_time": "",
            "auto": True,
            "signal_strength": signal_strength,
            "target_pts": rule["target_pts"],
            "sl_pts": rule["sl_pts"],
            "mode": self.trading_mode,
        }

        # Real trading: place actual order via Kite
        if self.trading_mode == "real" and self.kite:
            try:
                parts = option_name.split()
                strike = float(parts[1])
                opt_type = parts[2]
                
                tradingsymbol = self._get_option_tradingsymbol(prefix, strike, opt_type)
                if not tradingsymbol:
                    logger.error(f"Cannot get tradingsymbol for {option_name}")
                    return trade
                
                # Place BUY order via Kite API with Bracket Order (BO) for automatic SL/TP
                short_id = trade_id[-6:]
                
                # Calculate SL and TP amounts
                sl_pts = rule.get('sl_pts', 25)
                tp_pts = rule.get('target_pts', 20)
                
                # Use per-user Kite connection if available
                kite_instance = self._get_kite_instance()
                order_id = kite_instance.place_order(
                    variety=kite_instance.VARIETY_BO,
                    exchange="NFO" if prefix != "SENSEX" else "BFO",
                    tradingsymbol=tradingsymbol,
                    transaction_type=kite_instance.TRANSACTION_TYPE_BUY,
                    quantity=quantity,
                    order_type=kite_instance.ORDER_TYPE_MARKET,
                    product=kite_instance.PRODUCT_BO,
                    stoploss=sl_pts,
                    squareoff=tp_pts,
                    trailing_stoploss=0,
                    tag=f"buy_{short_id}"
                )
                
                self._real_order_ids[trade_id] = order_id
                trade["order_id"] = order_id
                trade["kite_tradingsymbol"] = tradingsymbol
                trade["is_bo_trade"] = True
                
                logger.info(
                    f"REAL AUTO BUY (BO): {option_name} | {quantity}qty | "
                    f"₹{buy_price} | OrderID={order_id} | Strength={signal_strength} | "
                    f"Target=+{rule['target_pts']} SL=-{rule['sl_pts']}"
                )
            except Exception as e:
                logger.error(f"Failed to place real buy order for {option_name}: {e}")
                trade["error"] = str(e)
                trade["status"] = "error"

        # Save to database (pass user_id for multi-session support)
        save_auto_trade(trade, user_id=self.user_id)
        self._daily_trade_count += 1

        logger.info(
            f"AUTO BUY: {option_name} | {lots}L x {lot_size} = {quantity}qty | "
            f"₹{buy_price} | Strength={signal_strength} | "
            f"Target=+{rule['target_pts']} SL=-{rule['sl_pts']} | Mode={self.trading_mode}"
        )
        return trade

    def _execute_sell(self, trade, sell_price, reason=""):
        """
        Execute sell — updates database, real places Kite order (or skips for BO).
        
        For Bracket Orders (BO): Broker auto-exits at SL/TP, so we just log the close.
        For regular orders: We place the manual SELL order.
        """
        ist = _ist_now()
        qty = int(trade.get('quantity', trade.get('lot', 1)))
        pnl = round((sell_price - trade['buy_price']) * qty, 2)

        # Real trading: place sell order via Kite (but NOT for BO — broker already exited)
        if trade.get("mode") == "real" and self.kite and "order_id" in trade:
            # Check if this was a BO trade
            is_bo_order = trade.get("is_bo_trade", False)
            
            if not is_bo_order:
                # Regular order: place manual SELL (paper or old MIS trades)
                try:
                    tradingsymbol = trade.get("kite_tradingsymbol")
                    if tradingsymbol:
                        exchange = "NFO" if "SENSEX" not in tradingsymbol else "BFO"
                        
                        # Place SELL order via Kite API (using per-user credentials if available)
                        short_id = str(trade['id'])[-4:]
                        kite_instance = self._get_kite_instance()
                        sell_order_id = kite_instance.place_order(
                            variety=kite_instance.VARIETY_REGULAR,
                            exchange=exchange,
                            tradingsymbol=tradingsymbol,
                            transaction_type=kite_instance.TRANSACTION_TYPE_SELL,
                            quantity=qty,
                            order_type=kite_instance.ORDER_TYPE_MARKET,
                            product=kite_instance.PRODUCT_MIS,
                            tag=f"sell_{short_id}"
                        )
                        
                        logger.info(
                            f"REAL MANUAL SELL: {trade['name']} | OrderID={sell_order_id} | "
                            f"₹{sell_price} | P&L=₹{pnl} | Reason={reason}"
                        )
                except Exception as e:
                    logger.error(f"Failed to place real sell order for {trade['name']}: {e}")
            else:
                # BO order: Broker already auto-exited at SL/TP, just log it
                logger.info(
                    f"BO AUTO-EXIT: {trade['name']} | "
                    f"₹{sell_price} | P&L=₹{pnl} | Reason={reason} "
                    f"(Broker-side exit, no manual SELL placed)"
                )

        # Update in database (pass user_id for multi-session support)
        update_auto_trade_sell(trade['id'], sell_price, ist.strftime('%H:%M'), reason, user_id=self.user_id)
        self._daily_pnl += pnl

        logger.info(
            f"AUTO SELL: {trade['name']} | ₹{sell_price} | "
            f"P&L=₹{pnl} | Reason={reason} | Day P&L=₹{self._daily_pnl} | Mode={trade.get('mode', 'paper')}"
        )
        return pnl

    # ─── Core loop ────────────────────────────────

    async def _tick(self):
        """Single tick of the auto-trading engine"""
        self._reset_daily()

        # Kill switch check
        if self._is_killed():
            # Close all open positions — use buy_price as fallback if LTP unavailable
            for t in self._get_open_trades():
                ltp = self._get_trade_ltp(t)
                sell_price = ltp if ltp else t['buy_price']  # fallback: flat exit
                self._execute_sell(t, sell_price, reason="KILL_SWITCH")
            logger.warning(f"AUTO TRADER KILLED: Daily loss ₹{self._daily_pnl} >= ₹{MAX_DAILY_LOSS}")
            return

        # EOD exit — close all positions and stop engine
        if _is_eod_exit_time():
            for t in self._get_open_trades():
                ltp = self._get_trade_ltp(t)
                sell_price = ltp if ltp else t['buy_price']
                self._execute_sell(t, sell_price, reason="EOD_EXIT")
            logger.info("Market about to get closed — auto-trader stopping automatically")
            self.enabled = False
            return

        # Not market hours? Skip
        if not _is_market_hours():
            return

        # Process each index in priority order
        for symbol in INDEX_PRIORITY:
            prefix = SYMBOL_MAP_REVERSE.get(symbol, "NIFTY")
            lot_size = LOT_SIZES.get(prefix, 65)

            # Get signal for this index
            try:
                sig = self.get_signal(symbol)
                if not sig or 'error' in sig:
                    continue
            except Exception as e:
                logger.error(f"Auto-trader signal fetch error for {symbol}: {e}")
                continue

            consensus = sig.get('consensus', 'NEUTRAL')
            strength = sig.get('signal_strength', 'NONE')
            vix = sig.get('india_vix', {}).get('value', 0)
            if isinstance(vix, str):
                vix = 0

            open_trade = self._get_open_trade_for(prefix)

            # ── EXIT LOGIC ──
            if open_trade:
                ltp = self._get_trade_ltp(open_trade)
                if not ltp:
                    continue

                buy_price = open_trade['buy_price']
                target_pts = open_trade.get('target_pts', 20)
                sl_pts = open_trade.get('sl_pts', 10)
                trade_strength = open_trade.get('signal_strength', 'STRONG')

                # Stop loss
                if ltp <= buy_price - sl_pts:
                    pnl = self._execute_sell(open_trade, ltp, reason="STOP_LOSS")
                    # Longer cooldown after SL — market went against you
                    self._set_cooldown(prefix, SL_COOLDOWN_MINUTES)
                    continue

                # Target hit
                if ltp >= buy_price + target_pts:
                    self._execute_sell(open_trade, ltp, reason="TARGET_HIT")
                    # Set cooldown after target hit to prevent rapid re-entry
                    rule = _get_signal_rule(prefix, trade_strength)
                    self._set_cooldown(prefix, rule["cooldown_minutes"])
                    continue

                # Signal reversal (BUY trade but signal now SELL, or vice versa)
                trade_type = 'CE' if 'CE' in open_trade['name'].upper() else 'PE'
                trade_direction = 'BUY' if trade_type == 'CE' else 'SELL'
                if consensus != 'NEUTRAL' and consensus != trade_direction:
                    self._execute_sell(open_trade, ltp, reason="SIGNAL_REVERSAL")
                    # Will enter new direction in next tick
                    continue

                # Signal goes NEUTRAL
                if consensus == 'NEUTRAL':
                    self._execute_sell(open_trade, ltp, reason="SIGNAL_NEUTRAL")
                    self._set_cooldown(prefix, NEUTRAL_COOLDOWN_MINUTES)
                    continue

            # ── ENTRY LOGIC ──
            else:
                # Skip if NEUTRAL or no strength
                if consensus == 'NEUTRAL' or strength == 'NONE':
                    self._pending_entries.pop(prefix, None)  # clear stale pending
                    continue

                # ── ADX FILTER: Skip entry during consolidation (ADX < 25) ──
                # ADX < 25 means weak/consolidating market — trade has poor odds
                if not self._is_trend_strong(prefix):
                    logger.info(f"ENTRY BLOCKED: {prefix} consolidation detected (ADX < {ADX_THRESHOLD}) → waiting for trend")
                    continue

                # Get rule for this signal strength (index-specific)
                rule = _get_signal_rule(prefix, strength)
                if not rule:
                    continue

                # Trade count check
                if self._daily_trade_count >= MAX_TRADES_PER_DAY:
                    continue

                # Cooldown check
                if self._is_on_cooldown(prefix):
                    continue

                # Get ATM strike + LTP in one atomic read (no race condition)
                opt_type = 'CE' if consensus == 'BUY' else 'PE'
                atm_strike = None
                atm_price = None

                # ONLY use atomic snapshot — strike + price guaranteed from same moment.
                # NEVER fall back to separate reads: get_option_ltp calculates its own ATM
                # from spot, while get_atm_strike reads from dashboard — these can be
                # DIFFERENT strikes, causing catastrophic price/strike mismatch
                # (e.g., buying "79900 CE" at 80800 CE's price of ₹900).
                if self.get_entry_snapshot:
                    atm_strike, atm_price = self.get_entry_snapshot(prefix, opt_type)

                if not atm_price or not atm_strike:
                    # No fresh atomic snapshot — skip entry, wait for next cycle
                    continue

                # Capital check
                lots = self._max_lots(atm_price, lot_size)
                if lots <= 0:
                    continue

                option_name = f"{prefix} {atm_strike} {opt_type}"

                # ── PRICE CONFIRMATION: require 2 consecutive similar readings ──
                # Prevents buying at stale/spike prices. If the price moved more
                # than SL_PTS between two consecutive readings, wait for stability.
                pending = self._pending_entries.get(prefix)
                sl_pts = rule["sl_pts"]
                if pending and pending["opt_type"] == opt_type and pending["strike"] == atm_strike:
                    price_diff = abs(atm_price - pending["price"])
                    if price_diff > sl_pts:
                        # Price moved too much between readings — update and wait
                        self._pending_entries[prefix] = {"price": atm_price, "opt_type": opt_type, "strike": atm_strike}
                        logger.warning(
                            f"PRICE UNSTABLE: {option_name} prev=₹{pending['price']} now=₹{atm_price} "
                            f"diff=₹{price_diff:.2f} > SL={sl_pts} → WAITING"
                        )
                        continue
                    else:
                        # Price confirmed — safe to enter
                        logger.info(
                            f"PRICE CONFIRMED: {option_name} prev=₹{pending['price']} now=₹{atm_price} "
                            f"diff=₹{price_diff:.2f} ≤ SL={sl_pts} → ENTERING"
                        )
                        del self._pending_entries[prefix]
                else:
                    # First reading for this option — store and wait for confirmation
                    self._pending_entries[prefix] = {"price": atm_price, "opt_type": opt_type, "strike": atm_strike}
                    logger.info(f"PRICE PENDING: {option_name} = ₹{atm_price} → waiting for confirmation next cycle")
                    continue

                # Execute!
                self._execute_buy(prefix, option_name, atm_price, lots, lot_size, strength, rule)

    def _get_trade_ltp(self, trade):
        """Get live LTP for an open trade's specific instrument"""
        try:
            parts = trade['name'].split()
            prefix = parts[0]
            opt_type = parts[2]
            return self.get_option_ltp(prefix, opt_type, strike=float(parts[1]))
        except Exception:
            return None


    # ─── Start / Stop ─────────────────────────────

    async def run(self):
        """Main loop — runs every ~2 seconds"""
        self.running = True
        logger.info("Auto-trader engine STARTED (paper mode)")
        try:
            while self.enabled:
                try:
                    await self._tick()
                except Exception as e:
                    logger.error(f"Auto-trader tick error: {e}", exc_info=True)
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            pass
        finally:
            self.running = False
            if not self.enabled:
                logger.info("Auto-trader engine STOPPED")

    def start(self, loop=None):
        """Start the engine as an async task"""
        if self.enabled:
            return
        self.enabled = True
        self._reset_daily()
        if loop:
            self._task = loop.create_task(self.run())
        else:
            self._task = asyncio.ensure_future(self.run())

    def stop(self):
        """Stop the engine — close all open auto trades"""
        # Close all open auto-traded positions before stopping
        for t in self._get_open_trades():
            if t.get('auto'):
                ltp = self._get_trade_ltp(t)
                sell_price = ltp if ltp else t['buy_price']
                self._execute_sell(t, sell_price, reason="MANUAL_STOP")
        self.enabled = False
        if self._task:
            self._task.cancel()
            self._task = None

    def set_trading_mode(self, mode):
        """Switch between paper and real trading modes
        
        Args:
            mode: "paper" or "real"
            
        Returns:
            dict with status and message
        """
        if mode not in ["paper", "real"]:
            return {"status": "error", "message": "Invalid mode. Use 'paper' or 'real'"}
        
        if self.trading_mode == mode:
            if mode == "real":
                balance = self._get_kite_account_balance()
                if balance is not None:
                    return {
                        "status": "ok",
                        "message": f"Already in {mode} mode",
                        "trading_mode": mode,
                        "account_balance": round(balance, 2)
                    }
            return {"status": "ok", "message": f"Already in {mode} mode", "trading_mode": mode}
        
        # Close all open positions before switching modes
        if self._get_open_trades():
            logger.warning(f"Closing all open positions before switching to {mode} mode")
            for t in self._get_open_trades():
                if t.get('auto'):
                    ltp = self._get_trade_ltp(t)
                    sell_price = ltp if ltp else t['buy_price']
                    self._execute_sell(t, sell_price, reason=f"MODE_SWITCH_TO_{mode.upper()}")
        
        self.trading_mode = mode
        
        # In real mode, verify Kite connection
        if mode == "real":
            if not self.kite:
                self.trading_mode = "paper"  # Revert
                return {
                    "status": "error",
                    "message": "Kite API not configured",
                    "trading_mode": self.trading_mode
                }
            
            # Try to get account balance to verify connection
            balance = self._get_kite_account_balance()
            if balance is None:
                self.trading_mode = "paper"  # Revert
                logger.error(f"Balance fetch returned None")
                return {
                    "status": "error",
                    "message": "Cannot fetch balance from Kite account. Check API credentials.",
                    "trading_mode": self.trading_mode
                }
            
            logger.info(f"Switched to REAL trading mode. Account balance: ₹{balance}")
            return {
                "status": "ok",
                "message": f"Switched to REAL trading mode",
                "trading_mode": mode,
                "account_balance": round(balance, 2)
            }
        else:
            logger.info(f"Switched to PAPER trading mode")
            return {
                "status": "ok",
                "message": f"Switched to PAPER trading mode",
                "trading_mode": mode
            }

    def get_status(self):
        """Return engine status for API"""
        status = {
            "enabled": self.enabled,
            "running": self.running,
            "trading_mode": self.trading_mode,
            "capital": TOTAL_CAPITAL,
            "available_capital": round(self._get_available_capital(), 2),
            "used_capital": round(self._used_capital(), 2),
            "daily_trade_count": self._daily_trade_count,
            "max_trades_per_day": MAX_TRADES_PER_DAY,
            "daily_pnl": round(self._daily_pnl, 2),
            "max_daily_loss": MAX_DAILY_LOSS,
            "killed": self._is_killed(),
            "market_hours": _is_market_hours(),
            "test_mode": TEST_MODE,
            "cooldowns": {
                k: v.strftime('%H:%M:%S') for k, v in self._cooldowns.items()
                if v > _ist_now()
            },
            "open_positions": len(self._get_open_trades()),
            "max_position_size": self._max_position_size,  # Max 1 in real mode
        }
        return status
