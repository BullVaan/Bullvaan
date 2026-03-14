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

    def __init__(self, get_signal_fn, get_option_ltp_fn, get_entry_snapshot_fn=None):
        """
        get_signal_fn(symbol) -> dict with: consensus, signal_strength, india_vix
        get_option_ltp_fn(index_prefix, opt_type, strike=None) -> float LTP or None
        get_entry_snapshot_fn(prefix, opt_type) -> (atm_strike, ltp) atomic read
        """
        self.get_signal = get_signal_fn
        self.get_option_ltp = get_option_ltp_fn
        self.get_entry_snapshot = get_entry_snapshot_fn
        self.enabled = False
        self.running = False

        # Per-index state
        self._cooldowns = {}      # {prefix: datetime when cooldown expires}
        self._pending_entries = {} # {prefix: {"price": float, "opt_type": str, "strike": float}} — price confirmation

        self._daily_trade_count = 0
        self._daily_pnl = 0.0
        self._last_reset_date = None
        self._task = None

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

    # ─── Kill switch ──────────────────────────────

    def _is_killed(self):
        """Check if daily loss limit hit"""
        return self._daily_pnl <= -MAX_DAILY_LOSS

    # ─── Trade execution (paper) ──────────────────

    def _execute_buy(self, prefix, option_name, buy_price, lots, lot_size, signal_strength, rule, sig=None):
        """Paper buy — writes to trades.json"""
        ist = _ist_now()
        quantity = lots * lot_size

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
            "target_pts": rule["target_pts"],
            "sl_pts": rule["sl_pts"],
            "india_vix": sig.get('india_vix', {}).get('value', '-') if sig else '-',
            "strategies": sig.get('signals', []) if sig else [],
        }

        trades.append(trade)
        _save_trades(trades)
        self._daily_trade_count += 1

        logger.info(
            f"AUTO BUY: {option_name} | {lots}L x {lot_size} = {quantity}qty | "
            f"₹{buy_price} | Strength={signal_strength} | "
            f"Target=+{rule['target_pts']} SL=-{rule['sl_pts']}"
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

        logger.info(
            f"AUTO SELL: {trade['name']} | ₹{sell_price} | "
            f"P&L=₹{pnl} | Reason={reason} | Day P&L=₹{self._daily_pnl}"
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
                    rule = SIGNAL_RULES.get(trade_strength, SIGNAL_RULES["STRONG"])
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

                # Get rule for this signal strength
                rule = SIGNAL_RULES.get(strength)
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
        }
