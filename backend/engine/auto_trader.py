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

# ─── Signal Log ───────────────────────────────
SIGNAL_LOGS_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'signal_logs')
os.makedirs(SIGNAL_LOGS_DIR, exist_ok=True)

# ─── Daily state persistence (survives mid-day restart) ───────────────────────
DAILY_STATE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'daily_state.json')

def _append_signal_log(record: dict):
    """Append one tick's signal record to today's JSONL file (timestamps in IST)."""
    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    date_str = now_ist.strftime("%Y-%m-%d")
    path = os.path.join(SIGNAL_LOGS_DIR, f"{date_str}.jsonl")
    with open(path, 'a') as f:
        f.write(json.dumps(record) + '\n')

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
INDEX_RULES = _config.get("index_rules", {})
MAX_DAILY_LOSS = _config["max_daily_loss"]
MAX_LOTS_PER_TRADE = _config["max_lots_per_trade"]
TOTAL_CAPITAL = _config["total_capital"]
MARKET_OPEN = tuple(_config["market_open"])
MARKET_CLOSE = tuple(_config["market_close"])
EOD_EXIT = tuple(_config["eod_exit"])
TEST_MODE = _config.get("test_mode", False)

# Protection settings
PROFIT_PROTECT_THRESHOLD = _config.get("profit_protect_threshold", 3000)
PROFIT_PROTECT_DRAWDOWN = _config.get("profit_protect_drawdown", 2000)
MAX_PREMIUM = _config.get("max_premium", {})
LOSS_STREAK = _config.get("loss_streak", {})
ENTRY_SKIP_WINDOW = _config.get("entry_skip_window")  # ["10:00", "10:30"] or None
AFTERNOON_SELL_ONLY = _config.get("afternoon_sell_only")  # "12:30" cutoff or None
ADAPTIVE_CONFIG = _config.get("adaptive_config", {})  # adaptive choppy/trending switching

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


_trades_cache = None

def _load_trades():
    global _trades_cache
    if _trades_cache is not None:
        return _trades_cache
    os.makedirs(os.path.dirname(TRADES_FILE), exist_ok=True)
    if not os.path.exists(TRADES_FILE):
        with open(TRADES_FILE, 'w') as f:
            json.dump([], f)
    with open(TRADES_FILE, 'r') as f:
        _trades_cache = json.load(f)
    return _trades_cache


def _save_trades(trades):
    global _trades_cache
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
    Paper-trading engine that monitors signals and auto-executes trades.
    Runs as an async background task inside the FastAPI server.
    """

    def __init__(self, get_signal_fn, get_option_ltp_fn, get_entry_snapshot_fn=None, get_oi_volume_fn=None, get_adjacent_fn=None, get_expiry_fn=None):
        """
        get_signal_fn(symbol) -> dict with: consensus, signal_strength, india_vix
        get_option_ltp_fn(index_prefix, opt_type, strike=None) -> float LTP or None
        get_entry_snapshot_fn(prefix, opt_type) -> (atm_strike, ltp) atomic read
        get_oi_volume_fn(prefix) -> dict with ce_oi, pe_oi, ce_volume, pe_volume, etc. or None
        get_adjacent_fn(prefix) -> dict with atm_m1/p1 strike prices or None
        get_expiry_fn(prefix) -> dict with expiry date + is_expiry_day flag, or None
        """
        self.get_signal = get_signal_fn
        self.get_option_ltp = get_option_ltp_fn
        self.get_entry_snapshot = get_entry_snapshot_fn
        self.get_oi_volume = get_oi_volume_fn
        self.get_adjacent = get_adjacent_fn
        self.get_expiry = get_expiry_fn
        self.enabled = False
        self.running = False

        # Per-index state
        self._price_hist = {}      # {prefix: [last N prices]} — rolling window for anti-spike

        self._daily_trade_count = 0
        self._daily_pnl = 0.0
        self._peak_pnl = 0.0       # highest P&L reached today (profit protection)
        self._profit_protected = False  # True = profit protection triggered, stop trading
        self._daily_closed = {}    # {prefix: [pnl, pnl, ...]} for loss streak check
        self._all_closed_pnls = []  # global across indices for adaptive trigger
        self._adaptive_switched = False  # True after switching to trending config
        self._active_index_rules = self._get_starting_index_rules()
        self._last_reset_date = None
        self._task = None
        self._spot_cache = {}          # latest spot price per index for signal log

        self._expiry_cache = {}        # {prefix: {expiry, is_expiry_day}} — fetched once per day, not per tick

    # ─── State helpers ────────────────────────────

    def _save_state(self):
        """Persist daily risk state to disk so a mid-day restart can restore it."""
        try:
            state = {
                'date':              str(_ist_now().date()),
                'daily_trade_count': self._daily_trade_count,
                'daily_pnl':         self._daily_pnl,
                'peak_pnl':          self._peak_pnl,
                'profit_protected':  self._profit_protected,
                'daily_closed':      self._daily_closed,
                'adaptive_switched': self._adaptive_switched,
            }
            with open(DAILY_STATE_PATH, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            logger.error(f"Auto-trader: failed to save daily state: {e}")

    def _load_state(self):
        """Load persisted daily state if it belongs to today. Returns True on success."""
        if not os.path.exists(DAILY_STATE_PATH):
            return False
        try:
            with open(DAILY_STATE_PATH) as f:
                state = json.load(f)
            if state.get('date') != str(_ist_now().date()):
                return False
            self._daily_trade_count = state.get('daily_trade_count', 0)
            self._daily_pnl         = state.get('daily_pnl', 0.0)
            self._peak_pnl          = state.get('peak_pnl', 0.0)
            self._profit_protected  = state.get('profit_protected', False)
            self._daily_closed      = state.get('daily_closed', {})
            self._adaptive_switched = state.get('adaptive_switched', False)
            if self._adaptive_switched:
                self._active_index_rules = dict(ADAPTIVE_CONFIG.get('trending', {}))
            self._last_reset_date = _ist_now().date()
            logger.info(
                f"Auto-trader: restored daily state from disk — "
                f"P&L=₹{self._daily_pnl} trades={self._daily_trade_count} "
                f"adaptive_switched={self._adaptive_switched}"
            )
            return True
        except Exception as e:
            logger.error(f"Auto-trader: failed to load daily state: {e}")
            return False

    def _reset_daily(self):
        """Reset daily counters at start of new day (or restore from disk on mid-day restart)."""
        today = _ist_now().date()
        if self._last_reset_date != today:
            if self._load_state():
                # Successfully restored today's state from disk — skip full reset
                self._prefill_price_hist()
                return
            # No valid saved state for today — genuine new day, reset everything
            self._daily_trade_count = 0
            self._daily_pnl = 0.0
            self._peak_pnl = 0.0
            self._profit_protected = False
            self._daily_closed = {}
            self._all_closed_pnls = []
            self._adaptive_switched = False
            self._active_index_rules = self._get_starting_index_rules()
            self._price_hist = {}
            self._expiry_cache = {}

            self._last_reset_date = today
            self._prefill_price_hist()
            logger.info("Auto-trader: daily counters reset")

    def _prefill_price_hist(self):
        """Pre-fill anti-spike price history from today's signal log.

        On engine start/restart, _price_hist is empty so the anti-spike
        filter has no data and lets the first 3 entries per index through
        unfiltered.  This reads the most recent option prices from today's
        signal log so the filter is immediately active.
        """
        today_str = _ist_now().strftime("%Y-%m-%d")
        log_path = os.path.join(SIGNAL_LOGS_DIR, f"{today_str}.jsonl")
        if not os.path.exists(log_path):
            return

        # Read last ~100 lines (enough to get 10 prices per index)
        try:
            with open(log_path, 'rb') as f:
                # Seek to end, read last chunk
                f.seek(0, 2)
                fsize = f.tell()
                read_size = min(fsize, 100_000)  # ~100KB = ~200 lines
                f.seek(max(0, fsize - read_size))
                tail = f.read().decode('utf-8', errors='ignore')

            lines = tail.strip().split('\n')
            # Parse recent records per index
            for prefix in ["NIFTY", "BANKNIFTY", "SENSEX"]:
                # First pass: find the most recent ATM strike for this index
                latest_strike = None
                for line in reversed(lines):
                    try:
                        rec = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    if rec.get('index') == prefix and rec.get('atm_strike'):
                        latest_strike = rec['atm_strike']
                        break

                if not latest_strike:
                    continue

                # Second pass: collect prices only from the same ATM strike
                prices = []
                for line in reversed(lines):
                    if len(prices) >= 10:
                        break
                    try:
                        rec = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    if rec.get('index') != prefix:
                        continue
                    if rec.get('atm_strike') != latest_strike:
                        continue  # different strike → skip (prices not comparable)
                    # Collect any available option price (CE or PE)
                    ce = rec.get('ce_price')
                    pe = rec.get('pe_price')
                    # Prefer the price matching consensus, fallback to either
                    consensus = rec.get('consensus')
                    if consensus == 'BUY' and ce and ce > 0:
                        prices.append(ce)
                    elif consensus == 'SELL' and pe and pe > 0:
                        prices.append(pe)
                    elif ce and ce > 0:
                        prices.append(ce)
                    elif pe and pe > 0:
                        prices.append(pe)

                if prices:
                    prices.reverse()  # oldest first
                    self._price_hist[prefix] = prices
                    logger.info(f"Anti-spike prefill {prefix}: {len(prices)} prices from signal log")

        except Exception as e:
            logger.warning(f"Anti-spike prefill failed: {e}")

    def _warmup_price_hist(self):
        """Collect live option prices during 9:15-9:20 pre-trade window.

        F&O opens at 9:15 but the engine doesn't trade until 9:20.
        Use this 5-minute window to fill the anti-spike rolling window
        so the filter is fully ready when trading begins.
        """
        for symbol in INDEX_PRIORITY:
            prefix = SYMBOL_MAP_REVERSE.get(symbol, "NIFTY")
            if not self.get_entry_snapshot:
                continue
            # Try CE first, then PE — we just need any live option price
            for opt_type in ('CE', 'PE'):
                try:
                    atm_strike, atm_price = self.get_entry_snapshot(prefix, opt_type)
                    if atm_price and atm_price > 0:
                        hist = self._price_hist.setdefault(prefix, [])
                        hist.append(atm_price)
                        if len(hist) > 10:
                            hist.pop(0)
                        break  # got a price for this index, move on
                except Exception:
                    continue

    def _get_open_trades(self):
        """Get all open trades"""
        trades = _load_trades()
        return [t for t in trades if t.get('status') == 'open']

    def _get_open_trade_for(self, prefix):
        """Get open trade for a specific index (NIFTY/BANKNIFTY/SENSEX)"""
        for t in self._get_open_trades():
            if t['name'].upper().startswith(prefix):
                return t
        return None

    def _is_streak_blocked(self, prefix):
        """Check if this index is blocked due to a consecutive loss streak.

        Rules (configurable via trading_rules.json → loss_streak):
        - Block if N consecutive losses (default 3) regardless of amount
        - Block if M+ consecutive losses (default 2) totaling >= threshold (default ₹3000)
        - Resets on any winning trade (pnl >= 0)
        """
        if not LOSS_STREAK:
            return False

        closed = self._daily_closed.get(prefix, [])
        if not closed:
            return False

        max_consec = LOSS_STREAK.get('max_consecutive_losses', 3)
        max_amount = LOSS_STREAK.get('max_streak_amount', 3000)
        min_for_amount = LOSS_STREAK.get('min_losses_for_amount', 2)

        streak_count = 0
        streak_loss = 0
        for pnl in reversed(closed):
            if pnl >= 0:
                break
            streak_count += 1
            streak_loss += abs(pnl)

        if streak_count >= max_consec:
            logger.info(
                f"STREAK-BLOCK: {prefix} {streak_count} consecutive losses → SKIP"
            )
            return True
        if streak_count >= min_for_amount and streak_loss >= max_amount:
            logger.info(
                f"STREAK-BLOCK: {prefix} {streak_count} losses totaling ₹{streak_loss:,.0f} >= ₹{max_amount:,.0f} → SKIP"
            )
            return True
        return False

    # ─── Adaptive Approach ────────────────────────────────────────────────────
    #
    #  ADAPTIVE APPROACH — DAILY FLOW
    #  ═══════════════════════════════════════════════════════════════════════
    #
    #    DAY START
    #       │
    #       ▼
    #    CHOPPY MODE  (default every morning)
    #    ┌──────────────────────────────────────────────────────────┐
    #    │  NIFTY    : Target +5 pts  │  SL -5 pts  │  BE lock @+3 │
    #    │  BANKNIFTY: Target +12 pts │  SL -10 pts │              │
    #    │  SENSEX   : Target +12 pts │  SL -10 pts │              │
    #    └──────────────────────────────────────────────────────────┘
    #       │
    #       ▼
    #    [Each trade closes]
    #       │
    #       ├─ WIN  → consecutive win counter +1
    #       │         ├─ counter < 2  → stay CHOPPY
    #       │         └─ counter ≥ 2  → SWITCH ──────────────────────┐
    #       │                                                          │
    #       └─ LOSS → reset consecutive counter to 0                  │
    #                 → stay CHOPPY                                    │
    #                                                                  ▼
    #                                                     TRENDING MODE (rest of day)
    #                                                     ┌────────────────────────────────────────────┐
    #                                                     │  NIFTY    : Target +10 │ SL -8  │ BE @+5  │
    #                                                     │  BANKNIFTY: Target +15 │ SL -18 │         │
    #                                                     │  SENSEX   : Target +6  │ SL -12 │         │
    #                                                     │  neutral_exit : False               │
    #                                                     └────────────────────────────────────────────┘
    #                                                          ↑
    #                                            Stays TRENDING for remainder of day.
    #                                            Resets to CHOPPY at next day start.
    #  ═══════════════════════════════════════════════════════════════════════

    def _get_starting_index_rules(self):
        """Return initial index rules based on adaptive config.
        If adaptive is enabled, starts with choppy config.
        Otherwise returns the standard INDEX_RULES."""
        if not ADAPTIVE_CONFIG.get('enabled'):
            return dict(INDEX_RULES)
        mode = ADAPTIVE_CONFIG.get('start_mode', 'choppy')
        adaptive_rules = ADAPTIVE_CONFIG.get(mode, {})
        if adaptive_rules:
            return dict(adaptive_rules)
        return dict(INDEX_RULES)

    def _check_adaptive_switch(self, pnl):
        """After each trade closes, check if we should switch from choppy to trending.
        Tracks consecutive wins across all indices. Once triggered, switches for rest of day."""
        if not ADAPTIVE_CONFIG.get('enabled') or self._adaptive_switched:
            return
        self._all_closed_pnls.append(pnl)
        consec_wins = 0
        for p in reversed(self._all_closed_pnls):
            if p > 0:
                consec_wins += 1
            else:
                break
        # switch_trigger format: "2_consecutive_wins"
        trigger_str = ADAPTIVE_CONFIG.get('switch_trigger', '2_consecutive_wins')
        trigger_count = int(trigger_str.split('_')[0])
        if consec_wins >= trigger_count:
            self._adaptive_switched = True
            self._active_index_rules = dict(ADAPTIVE_CONFIG.get('trending', {}))
            logger.info(
                f"ADAPTIVE SWITCH: {consec_wins} consecutive wins → switching to TRENDING config | "
                f"NIFTY T{self._active_index_rules.get('NIFTY', {}).get('target_pts')}/SL{self._active_index_rules.get('NIFTY', {}).get('sl_pts')} "
                f"BN T{self._active_index_rules.get('BANKNIFTY', {}).get('target_pts')}/SL{self._active_index_rules.get('BANKNIFTY', {}).get('sl_pts')} "
                f"SENSEX T{self._active_index_rules.get('SENSEX', {}).get('target_pts')}/SL{self._active_index_rules.get('SENSEX', {}).get('sl_pts')}"
            )

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

    def _update_peak_pnl(self):
        """Track peak P&L and check profit protection trigger"""
        if self._daily_pnl > self._peak_pnl:
            self._peak_pnl = self._daily_pnl
        # If peaked above threshold and dropped by drawdown amount, stop
        # TEMPORARILY DISABLED FOR TESTING
        # if (self._peak_pnl >= PROFIT_PROTECT_THRESHOLD and
        #         self._daily_pnl <= self._peak_pnl - PROFIT_PROTECT_DRAWDOWN and
        #         not self._profit_protected):
        #     self._profit_protected = True
        #     logger.warning(
        #         f"PROFIT PROTECTION: Peak P&L was ₹{self._peak_pnl}, "
        #         f"now ₹{self._daily_pnl} (dropped ₹{self._peak_pnl - self._daily_pnl}) → STOP TRADING"
        #     )

    # ─── Kill switch ──────────────────────────────

    def _is_killed(self):
        """Check if daily loss limit hit"""
        return self._daily_pnl <= -MAX_DAILY_LOSS

    # ─── Trade execution (paper) ──────────────────

    def _execute_buy(self, prefix, option_name, buy_price, lots, lot_size, signal_strength, rule, sig=None):
        """Paper buy — writes to trades.json"""
        ist = _ist_now()
        quantity = lots * lot_size

        # Per-index target/SL override (uses adaptive rules if enabled)
        idx_rule = self._active_index_rules.get(prefix, INDEX_RULES.get(prefix, {}))
        target_pts = idx_rule.get("target_pts", rule["target_pts"])
        sl_pts = idx_rule.get("sl_pts", rule["sl_pts"])
        breakeven_lock_pts = idx_rule.get("breakeven_lock_pts", 0)

        trades = _load_trades()
        trade_id = max((t.get('id', 0) for t in trades), default=0) + 1

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
            "target_pts": target_pts,
            "sl_pts": sl_pts,
            "breakeven_lock_pts": breakeven_lock_pts,
            "breakeven_locked": False,
            "india_vix": sig.get('india_vix', {}).get('value', '-') if sig else '-',
            "strategies": sig.get('signals', []) if sig else [],
        }

        trades.append(trade)
        _save_trades(trades)
        self._daily_trade_count += 1
        self._save_state()

        logger.info(
            f"AUTO BUY: {option_name} | {lots}L x {lot_size} = {quantity}qty | "
            f"₹{buy_price} | Strength={signal_strength} | "
            f"Target=+{target_pts} SL=-{sl_pts}"
        )
        return trade

    def _execute_sell(self, trade, sell_price, reason=""):
        """Paper sell — updates trades.json"""
        ist = _ist_now()
        qty = int(trade.get('quantity', trade.get('lot', 1)))
        pnl = round((sell_price - trade['buy_price']) * qty, 2)

        trades = _load_trades()
        for t in trades:
            if t['id'] == trade['id']:
                t['sell_price'] = round(sell_price, 2)
                t['sell_time'] = ist.strftime('%H:%M')
                t['pnl'] = pnl
                t['status'] = 'closed'
                t['exit_reason'] = reason
                break
        _save_trades(trades)

        self._daily_pnl += pnl

        # Track closed trade PnL for loss streak (per-index)
        trade_prefix = trade['name'].split()[0]
        self._daily_closed.setdefault(trade_prefix, []).append(pnl)

        # Adaptive config switch check (choppy → trending)
        self._check_adaptive_switch(pnl)

        # Update peak P&L and check profit protection
        self._update_peak_pnl()
        self._save_state()

        logger.info(
            f"AUTO SELL: {trade['name']} | ₹{sell_price} | "
            f"P&L=₹{pnl} | Reason={reason} | Day P&L=₹{self._daily_pnl} | Peak=₹{self._peak_pnl}"
        )
        return pnl

    # ─── Core loop ────────────────────────────────

    async def _tick(self):
        """Single tick of the auto-trading engine"""
        self._reset_daily()

        # Kill switch check — TEMPORARILY DISABLED FOR TESTING
        # if self._is_killed():
        #     # Close all open positions — use buy_price as fallback if LTP unavailable
        #     for t in self._get_open_trades():
        #         ltp = self._get_trade_ltp(t)
        #         sell_price = ltp if ltp else t['buy_price']  # fallback: flat exit
        #         self._execute_sell(t, sell_price, reason="KILL_SWITCH")
        #     logger.warning(f"AUTO TRADER KILLED: Daily loss ₹{self._daily_pnl} >= ₹{MAX_DAILY_LOSS}")
        #     return

        # Profit protection — stop new entries if profit eroded too much
        if self._profit_protected:
            # Still manage open positions (exit logic runs), but no new entries
            open_trades = self._get_open_trades()
            if not open_trades:
                return
            # Fall through to process exits for open positions only

        # EOD exit — close all positions and stop engine
        if _is_eod_exit_time():
            for t in self._get_open_trades():
                if not t.get('auto'):
                    continue
                ltp = self._get_trade_ltp(t)
                sell_price = ltp if ltp else t['buy_price']
                self._execute_sell(t, sell_price, reason="EOD_EXIT")
            logger.info("Market about to get closed — auto-trader stopping automatically")
            self.enabled = False
            return

        # Not market hours? Warm up anti-spike if F&O is open (9:15+)
        if not _is_market_hours():
            h, m = _ist_time_tuple()
            fo_open = (h > 9) or (h == 9 and m >= 15)
            if fo_open:
                self._warmup_price_hist()
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

            # Update spot cache so every log record carries all 3 index levels
            if sig.get('price'):
                self._spot_cache[prefix] = sig.get('price')

            # ── SIGNAL LOG ── record every tick for post-market analysis
            try:
                log_strike, log_ce_price, log_pe_price = None, None, None
                if self.get_entry_snapshot:
                    try:
                        log_strike, log_ce_price = self.get_entry_snapshot(prefix, 'CE')
                        _,          log_pe_price = self.get_entry_snapshot(prefix, 'PE')
                    except Exception:
                        pass

                # OI / Volume snapshot from tick store
                log_oi_vol = None
                if self.get_oi_volume:
                    try:
                        log_oi_vol = self.get_oi_volume(prefix)
                    except Exception:
                        pass

                # Adjacent strike prices (ATM±1) for backtester accuracy
                log_adjacent = None
                if self.get_adjacent:
                    try:
                        log_adjacent = self.get_adjacent(prefix)
                    except Exception:
                        pass

                log_expiry = self._expiry_cache.get(prefix)
                if log_expiry is None and self.get_expiry:
                    try:
                        log_expiry = self.get_expiry(prefix)
                        if log_expiry:
                            self._expiry_cache[prefix] = log_expiry  # fetch once per day, reuse on every later tick
                    except Exception:
                        pass

                # Open trade details — track held position tick by tick
                log_open_trade = None
                _ot = self._get_open_trade_for(prefix)
                if _ot:
                    _cur_ltp = self._get_trade_ltp(_ot)
                    _qty = _ot.get('quantity', 0)
                    _bp  = _ot.get('buy_price', 0)
                    log_open_trade = {
                        "name":           _ot.get('name'),
                        "buy_price":      _bp,
                        "current_price":  _cur_ltp,
                        "unrealized_pnl": round((_cur_ltp - _bp) * _qty, 2) if _cur_ltp else None,
                        "breakeven_locked": _ot.get('breakeven_locked', False),
                    }

                log_record = {
                    "ts":           _ist_now().strftime("%H:%M:%S"),
                    "index":        prefix,
                    "consensus":    consensus,
                    "strength":     strength,
                    "vix":          vix,
                    "spot_price":   sig.get('price'),   # this index level
                    "market":       dict(self._spot_cache),  # all 3: {NIFTY, BANKNIFTY, SENSEX}
                    "atm_strike":   log_strike,          # nearest ATM strike
                    "ce_price":     log_ce_price,        # ATM CE LTP
                    "pe_price":     log_pe_price,        # ATM PE LTP
                    "strategies":   sig.get('signals', []),
                    "open_trade":   log_open_trade,      # None if no open position
                    "cooldown":     False,
                    "blocked":      self._is_streak_blocked(prefix),
                    "daily_pnl":    self._daily_pnl,
                    "trade_count":  self._daily_trade_count,
                    "adaptive_mode": "trending" if self._adaptive_switched else ("choppy" if ADAPTIVE_CONFIG.get('enabled') else None),
                }
                # Merge OI/volume fields at top level (ce_oi, pe_oi, ce_volume, etc.)
                if log_oi_vol:
                    log_record.update(log_oi_vol)
                # Merge adjacent strike prices (atm_m1_ce, atm_p1_pe, etc.)
                if log_adjacent:
                    log_record.update(log_adjacent)
                # Merge expiry info (expiry, is_expiry_day)
                if log_expiry:
                    log_record.update(log_expiry)
                _append_signal_log(log_record)
            except Exception:
                pass  # never let logging crash the engine

            open_trade = _ot  # reuse lookup from signal log above

            # ── EXIT LOGIC ──
            if open_trade:
                ltp = self._get_trade_ltp(open_trade)
                if not ltp:
                    continue

                buy_price = open_trade['buy_price']
                target_pts = open_trade.get('target_pts', 20)
                sl_pts = open_trade.get('sl_pts', 10)
                be_lock_pts = open_trade.get('breakeven_lock_pts', 0)

                # Breakeven lock — once price goes +N pts, move SL to breakeven
                if be_lock_pts and not open_trade.get('breakeven_locked') and ltp >= buy_price + be_lock_pts:
                    open_trade['breakeven_locked'] = True
                    # Update trade in file
                    trades = _load_trades()
                    for t in trades:
                        if t.get('id') == open_trade['id']:
                            t['breakeven_locked'] = True
                            break
                    _save_trades(trades)
                    logger.info(
                        f"BREAKEVEN LOCK: {open_trade['name']} | LTP ₹{ltp} >= "
                        f"buy ₹{buy_price} + {be_lock_pts} → SL moved to breakeven"
                    )

                # Effective SL — use breakeven if locked
                effective_sl = buy_price if open_trade.get('breakeven_locked') else (buy_price - sl_pts)

                # Stop loss (or breakeven exit)
                if ltp <= effective_sl:
                    reason = "BREAKEVEN_EXIT" if open_trade.get('breakeven_locked') else "STOP_LOSS"
                    pnl = self._execute_sell(open_trade, ltp, reason=reason)
                    continue

                # Target hit
                if ltp >= buy_price + target_pts:
                    self._execute_sell(open_trade, ltp, reason="TARGET_HIT")
                    continue

                # Signal reversal (BUY trade but signal now SELL, or vice versa)
                trade_type = 'CE' if 'CE' in open_trade['name'].upper() else 'PE'
                trade_direction = 'BUY' if trade_type == 'CE' else 'SELL'
                if consensus != 'NEUTRAL' and consensus != trade_direction:
                    self._execute_sell(open_trade, ltp, reason="SIGNAL_REVERSAL")
                    # Will enter new direction in next tick
                    continue

                # Signal goes NEUTRAL — exit
                if consensus == 'NEUTRAL':
                    neutral_exit = True  # always exit on neutral (adaptive disabled)
                    if ADAPTIVE_CONFIG.get('enabled') and self._adaptive_switched:
                        neutral_exit = ADAPTIVE_CONFIG.get('trending', {}).get('neutral_exit', True)
                    if neutral_exit:
                        self._execute_sell(open_trade, ltp, reason="SIGNAL_NEUTRAL")
                        continue

            # ── ENTRY LOGIC ──
            else:
                # Skip if NEUTRAL or no strength
                if consensus == 'NEUTRAL' or strength == 'NONE':
                    continue

                # Get rule for this signal strength
                rule = SIGNAL_RULES.get(strength)
                if not rule:
                    continue

                # Entry skip window — avoid dead zone (e.g. 10:00-10:30)
                if ENTRY_SKIP_WINDOW:
                    now_hm = _ist_now().strftime('%H:%M')
                    if ENTRY_SKIP_WINDOW[0] <= now_hm < ENTRY_SKIP_WINDOW[1]:
                        continue

                # Loss streak — block new entries for this index
                if self._is_streak_blocked(prefix):
                    continue

                # Afternoon SELL-only — block BUY entries after cutoff (e.g. 12:30)
                if AFTERNOON_SELL_ONLY and consensus == 'BUY':
                    now_hm = _ist_now().strftime('%H:%M')
                    if now_hm >= AFTERNOON_SELL_ONLY:
                        continue

                # Profit protection — no new entries
                if self._profit_protected:
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

                # Update rolling price history for anti-spike
                hist = self._price_hist.setdefault(prefix, [])
                hist.append(atm_price)
                if len(hist) > 10:
                    hist.pop(0)

                # Premium cap: skip entry if option premium too expensive
                prem_cap = MAX_PREMIUM.get(prefix)
                if prem_cap and atm_price >= prem_cap:
                    option_name = f"{prefix} {atm_strike} {opt_type}"
                    logger.info(
                        f"PREMIUM-CAP: {option_name} ₹{atm_price} >= cap ₹{prem_cap} → SKIP"
                    )
                    continue

                # Anti-spike: need at least 3 prices before allowing any entry
                if len(hist) < 3:
                    logger.info(f"ANTI-SPIKE: {prefix} warming up ({len(hist)}/3 prices) → SKIP")
                    continue
                window = hist[-5:] if len(hist) >= 5 else hist
                avg = sum(window) / len(window)
                if atm_price > avg + 1:
                    option_name = f"{prefix} {atm_strike} {opt_type}"
                    logger.info(
                        f"ANTI-SPIKE: {option_name} ₹{atm_price} > avg ₹{avg:.2f} + 1pt → SKIP"
                    )
                    continue

                # Capital check — use full available capital up to max lots
                affordable_lots = self._max_lots(atm_price, lot_size)
                lots = min(affordable_lots, MAX_LOTS_PER_TRADE)
                if lots <= 0:
                    continue

                option_name = f"{prefix} {atm_strike} {opt_type}"

                # Execute!
                self._execute_buy(prefix, option_name, atm_price, lots, lot_size, strength, rule, sig=sig)

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
        # Always prefill anti-spike on start (handles mid-day restart)
        if not self._price_hist:
            self._prefill_price_hist()
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

    def get_status(self):
        """Return engine status for API"""
        return {
            "enabled": self.enabled,
            "running": self.running,
            "mode": "paper",
            "capital": TOTAL_CAPITAL,
            "available_capital": round(self._available_capital(), 2),
            "used_capital": round(self._used_capital(), 2),
            "daily_trade_count": self._daily_trade_count,
            "daily_pnl": round(self._daily_pnl, 2),
            "peak_pnl": round(self._peak_pnl, 2),
            "max_daily_loss": MAX_DAILY_LOSS,
            "killed": self._is_killed(),
            "profit_protected": self._profit_protected,
            "market_hours": _is_market_hours(),
            "test_mode": TEST_MODE,
            "open_positions": len(self._get_open_trades()),
        }
