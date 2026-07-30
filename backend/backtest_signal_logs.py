#!/usr/bin/env python3
"""
Signal Log Backtester
=====================
Replays historical signal_log data through different engine configurations
and compares results — without touching the live engine.

Usage:
    cd backend
    python3 backtest_signal_logs.py              # today's date (IST)
    python3 backtest_signal_logs.py 2026-06-08   # specific date

Output:
    Summary table + detailed trade log for every variant.

NOTE: Simulation is limited to the signal log window. If the server was
      started mid-day (e.g. 13:11), morning trades are not simulated.

Add new variants by copying an existing entry in VARIANTS and changing
the parameters. No other code needs to change.
"""

import json
import sys
import os
from datetime import datetime, timedelta

# ── paths ─────────────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
SIGNAL_LOGS_DIR = os.path.join(BASE_DIR, 'data', 'signal_logs')

# ── lot sizes (matching live engine: NIFTY=65, BANKNIFTY=30, SENSEX=20) ────────
LOT_SIZE = {"NIFTY": 65, "BANKNIFTY": 30, "SENSEX": 20}

# ══════════════════════════════════════════════════════════════════════════════
# VARIANTS — add / edit configurations here
# ══════════════════════════════════════════════════════════════════════════════
#
# Parameter reference:
#   time_cutoff    "HH:MM"  — no new entries at or after this time | None
#   min_vix/max_vix float   — skip if VIX outside this band | None
#   min_strength   int      — min strategies agreeing with consensus (inclusive)
#   sl_pts         dict     — stop-loss points per index
#   target_pts     dict     — target points per index
#   be_lock_pts    dict     — breakeven lock threshold per index | None per index
#   no_move_abort  dict     — {"pts": N, "sec": S} exit if peak < N after S sec | None
#   anti_spike_pts float    — skip entry if price > 5-tick avg + N pts | None
#   neutral_exit   bool     — exit trade when consensus flips to NEUTRAL | False
#   consec_sl_block int     — block index after N consecutive SLs | None (disabled)
#   momentum_guard bool     — skip re-entry if premium < last buy on same strike | False
#   max_premium    dict     — skip entry if option premium >= N per index | None
#   kill_switch_loss float  — stop all trading when cumulative daily PnL hits -N | None
#   oi_confirm     bool     — require OI buildup in trade direction (skip if OI declining) | False
#   vol_spike_mult float    — require option volume > N× rolling average (e.g. 1.5) | None
#   imbalance_ratio float   — require buy/sell qty ratio > N for entry (e.g. 1.3) | None
#   pcr_filter     dict     — {"min_for_buy": 0.7, "max_for_sell": 1.3} PCR range filter | None
#
# NOTE: No cooldown or max-trades limits — backtester trades freely on every
#       qualifying signal (one trade at a time per index).
#
VARIANTS = {
    "A_baseline": {
        "desc": "Current signal rules — no extra filters",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": None,
        "neutral_exit": False,
    },
    "B_time_1200": {
        "desc": "No new trades after 12:00 (all indices)",
        "time_cutoff":  "12:00",
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": None,
    },
    "C_strength_5": {
        "desc": "Require 5+ strategies agreeing (vs current 4+)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 5,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": None,
    },
    "D_no_move_abort_60s": {
        "desc": "Abort trade if peak gain < 3pts within 60 seconds of entry",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": {"pts": 3, "sec": 60},
        "anti_spike_pts": None,
    },
    "E_anti_spike_2pts": {
        "desc": "Skip entry if price spiked > 2pts above 5-tick average",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 2,
    },
    "F_vix_filter": {
        "desc": "Skip if VIX < 12 (too calm) or > 22 (too wild)",
        "time_cutoff":  None,
        "min_vix":      12,
        "max_vix":      22,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": None,
    },
    "G_combined": {
        "desc": "Combined: time 12:00 + strength 5 + no-move abort 60s",
        "time_cutoff":  "12:00",
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 5,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": {"pts": 3, "sec": 60},
        "anti_spike_pts": None,
    },
    "H_anti_spike_1pt": {
        "desc": "Anti-spike 1pt threshold (tightest filter)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "neutral_exit": False,
    },
    "I_anti_spike_3pt": {
        "desc": "Anti-spike 3pt threshold",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 3,
    },
    "J_anti_spike_5pt": {
        "desc": "Anti-spike 5pt threshold (loosest filter)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 5,
    },
    "K_best_combo": {
        "desc": "Best combo: anti-spike 2pt + no-move abort 60s",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": {"pts": 3, "sec": 60},
        "anti_spike_pts": 2,
    },
    "L_neutral_exit": {
        "desc": "Baseline + exit on neutral signal",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": None,
        "neutral_exit": True,
    },
    "M_antispike1_neutral": {
        "desc": "Anti-spike 1pt + exit on neutral signal",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "neutral_exit": True,
    },
    # ── COOLDOWN VARIANTS ──
    "N_cd_15m_sl": {
        "desc": "Anti-spike 1pt + 15-min cooldown after SL (current real engine)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "cooldown_sl_min": 15,
        "cooldown_other_min": 0,
    },
    "O_cd_5m_all": {
        "desc": "Anti-spike 1pt + 5-min cooldown after every exit",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "cooldown_sl_min": 5,
        "cooldown_other_min": 5,
    },
    "P_cd_5m_sl": {
        "desc": "Anti-spike 1pt + 5-min cooldown only after SL",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "cooldown_sl_min": 5,
        "cooldown_other_min": 0,
    },
    "Q_cd_2m_sl": {
        "desc": "Anti-spike 1pt + 2-min cooldown only after SL",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "cooldown_sl_min": 2,
        "cooldown_other_min": 0,
    },
    # ── MAX TRADES VARIANTS (all with anti-spike 1pt, no cooldown) ──
    "R_max9_trades": {
        "desc": "Anti-spike 1pt + max 9 trades/day (current real engine limit)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "max_trades": 9,
    },
    "S_max15_trades": {
        "desc": "Anti-spike 1pt + max 15 trades/day",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "max_trades": 15,
    },
    "T_max30_trades": {
        "desc": "Anti-spike 1pt + max 30 trades/day",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "max_trades": 30,
    },
    # ── FEATURE TEST VARIANTS (all with anti-spike 1pt base) ──
    "U_consec_sl_2": {
        "desc": "Anti-spike 1pt + block index after 2 consecutive SLs",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "consec_sl_block": 2,
    },
    "V_consec_sl_3": {
        "desc": "Anti-spike 1pt + block index after 3 consecutive SLs",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "consec_sl_block": 3,
    },
    "W_momentum_guard": {
        "desc": "Anti-spike 1pt + momentum guard (skip if premium < last buy)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "momentum_guard": True,
    },
    "X_no_breakeven": {
        "desc": "Anti-spike 1pt + NO breakeven lock (test breakeven impact)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": None, "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
    },
    "Y_all_features": {
        "desc": "Anti-spike 1pt + consec SL 2 + momentum guard + breakeven",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "consec_sl_block": 2,
        "momentum_guard": True,
    },
    # ── KILL SWITCH VARIANTS ──
    "Z_kill_5k": {
        "desc": "Anti-spike 1pt + kill switch ₹5K (matches live engine)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "kill_switch_loss": 5000,
    },
    "ZA_kill_3k": {
        "desc": "Anti-spike 1pt + kill switch ₹3K (tighter limit)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "kill_switch_loss": 3000,
    },
    "ZB_kill_7k": {
        "desc": "Anti-spike 1pt + kill switch ₹7K (wider limit)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "kill_switch_loss": 7000,
    },
    "ZC_premium_cap": {
        "desc": "Anti-spike 1pt + skip expensive options (BN<1000, SX<500)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
    },
    # ── Log-strength variants (use signal log's STRONG/MEDIUM instead of strategy count) ──
    "ZD_log_strength": {
        "desc": "Anti-spike 1pt + log strength (matches live engine signal logic)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
    },
    "ZE_log_strength_neutral": {
        "desc": "Anti-spike 1pt + log strength + neutral exit",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "neutral_exit": True,
    },
    "ZF_log_strength_premcap": {
        "desc": "Anti-spike 1pt + log strength + premium cap (closest to live engine)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
    },
    "ZG_log_str_neutral_premcap": {
        "desc": "Anti-spike 1pt + log strength + neutral exit + premium cap (full live engine)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
    },
    "ZH_full_live_engine": {
        "desc": "Full live engine: shared 1L capital + 5 lots + confirm + neutral + premcap",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5,
        "capital": 100000,
        "shared_capital": True,
    },
    "ZI_split_33k_5lots": {
        "desc": "Split ₹33K per index + 5 lots + neutral + premcap",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5,
        "capital": 33333,
    },
    "ZJ_live_4s_gap": {
        "desc": "REALISTIC LIVE: shared 1L + 5 lots + 4s tick gap (old engine with price confirm)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5,
        "capital": 100000,
        "shared_capital": True,
        "tick_gap_sec": 4,
    },
    "ZK_live_2s_gap": {
        "desc": "REALISTIC LIVE: shared 1L + 5 lots + 2s tick gap (new engine, no price confirm)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 8,  "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 10, "BANKNIFTY": 20, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5,
        "capital": 100000,
        "shared_capital": True,
        "tick_gap_sec": 2,
        "loss_streak": {"max_consecutive_losses": 3, "max_streak_amount": 3000, "min_losses_for_amount": 2},
        "entry_skip_window": ["10:00", "10:30"],
    },
    "ZK_adaptive": {
        "desc": "ADAPTIVE: Start choppy config, switch to trending after 2 consecutive wins",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 3,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5,
        "capital": 100000,
        "shared_capital": True,
        "tick_gap_sec": 2,
        "loss_streak": {"max_consecutive_losses": 3, "max_streak_amount": 3000, "min_losses_for_amount": 2},
        "entry_skip_window": None,
        "afternoon_sell_only": None,
        "adaptive": {
            "start_mode": "choppy",
            "switch_after_consecutive_wins": 2,
            "trending_target_pts": {"NIFTY": 10, "BANKNIFTY": 15, "SENSEX": 6},
            "trending_sl_pts":     {"NIFTY": 8,  "BANKNIFTY": 18, "SENSEX": 12},
            "trending_be_lock_pts": {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
            "trending_neutral_exit": False,
        },
    },
    # ── OI / VOLUME CONFIRMATION VARIANTS (require signal logs with OI data) ──
    "ZL_oi_confirm": {
        "desc": "Adaptive + OI confirmation (skip if OI declining for trade direction)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 3,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5,
        "capital": 100000,
        "shared_capital": True,
        "tick_gap_sec": 2,
        "loss_streak": {"max_consecutive_losses": 3, "max_streak_amount": 3000, "min_losses_for_amount": 2},
        "entry_skip_window": ["10:00", "10:30"],
        "afternoon_sell_only": "12:30",
        "oi_confirm": True,
        "adaptive": {
            "start_mode": "choppy",
            "switch_after_consecutive_wins": 2,
            "trending_target_pts": {"NIFTY": 10, "BANKNIFTY": 15, "SENSEX": 6},
            "trending_sl_pts":     {"NIFTY": 8,  "BANKNIFTY": 18, "SENSEX": 12},
            "trending_be_lock_pts": {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
            "trending_neutral_exit": False,
        },
    },
    "ZM_vol_spike": {
        "desc": "Adaptive + volume spike 1.5x (only enter on above-avg volume)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 3,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5,
        "capital": 100000,
        "shared_capital": True,
        "tick_gap_sec": 2,
        "loss_streak": {"max_consecutive_losses": 3, "max_streak_amount": 3000, "min_losses_for_amount": 2},
        "entry_skip_window": ["10:00", "10:30"],
        "afternoon_sell_only": "12:30",
        "vol_spike_mult": 1.5,
        "adaptive": {
            "start_mode": "choppy",
            "switch_after_consecutive_wins": 2,
            "trending_target_pts": {"NIFTY": 10, "BANKNIFTY": 15, "SENSEX": 6},
            "trending_sl_pts":     {"NIFTY": 8,  "BANKNIFTY": 18, "SENSEX": 12},
            "trending_be_lock_pts": {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
            "trending_neutral_exit": False,
        },
    },
    "ZN_imbalance": {
        "desc": "Adaptive + buy/sell qty imbalance 1.3x (buyers must dominate)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 3,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5,
        "capital": 100000,
        "shared_capital": True,
        "tick_gap_sec": 2,
        "loss_streak": {"max_consecutive_losses": 3, "max_streak_amount": 3000, "min_losses_for_amount": 2},
        "entry_skip_window": ["10:00", "10:30"],
        "afternoon_sell_only": "12:30",
        "imbalance_ratio": 1.3,
        "adaptive": {
            "start_mode": "choppy",
            "switch_after_consecutive_wins": 2,
            "trending_target_pts": {"NIFTY": 10, "BANKNIFTY": 15, "SENSEX": 6},
            "trending_sl_pts":     {"NIFTY": 8,  "BANKNIFTY": 18, "SENSEX": 12},
            "trending_be_lock_pts": {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
            "trending_neutral_exit": False,
        },
    },
    "ZO_pcr_filter": {
        "desc": "Adaptive + PCR filter (BUY only if PCR>0.7, SELL only if PCR<1.3)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 3,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5,
        "capital": 100000,
        "shared_capital": True,
        "tick_gap_sec": 2,
        "loss_streak": {"max_consecutive_losses": 3, "max_streak_amount": 3000, "min_losses_for_amount": 2},
        "entry_skip_window": ["10:00", "10:30"],
        "afternoon_sell_only": "12:30",
        "pcr_filter": {"min_for_buy": 0.7, "max_for_sell": 1.3},
        "adaptive": {
            "start_mode": "choppy",
            "switch_after_consecutive_wins": 2,
            "trending_target_pts": {"NIFTY": 10, "BANKNIFTY": 15, "SENSEX": 6},
            "trending_sl_pts":     {"NIFTY": 8,  "BANKNIFTY": 18, "SENSEX": 12},
            "trending_be_lock_pts": {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
            "trending_neutral_exit": False,
        },
    },
    "ZP_all_oi_vol": {
        "desc": "Adaptive + ALL OI/vol filters (OI confirm + vol spike + imbalance + PCR)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 3,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5,
        "capital": 100000,
        "shared_capital": True,
        "tick_gap_sec": 2,
        "loss_streak": {"max_consecutive_losses": 3, "max_streak_amount": 3000, "min_losses_for_amount": 2},
        "entry_skip_window": ["10:00", "10:30"],
        "afternoon_sell_only": "12:30",
        "oi_confirm": True,
        "vol_spike_mult": 1.5,
        "imbalance_ratio": 1.3,
        "pcr_filter": {"min_for_buy": 0.7, "max_for_sell": 1.3},
        "adaptive": {
            "start_mode": "choppy",
            "switch_after_consecutive_wins": 2,
            "trending_target_pts": {"NIFTY": 10, "BANKNIFTY": 15, "SENSEX": 6},
            "trending_sl_pts":     {"NIFTY": 8,  "BANKNIFTY": 18, "SENSEX": 12},
            "trending_be_lock_pts": {"NIFTY": 5,  "BANKNIFTY": None, "SENSEX": None},
            "trending_neutral_exit": False,
        },
    },
    # ── FILTER USEFULNESS TESTS: vol_spike base, toggle each existing filter ──
    "ZQ_volspike_no_antispike": {
        "desc": "Vol spike 1.5x WITHOUT anti-spike (test if anti-spike still needed)",
        "time_cutoff":  None, "min_vix": None, "max_vix": None, "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 3,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None, "anti_spike_pts": None,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5, "capital": 100000, "shared_capital": True, "tick_gap_sec": 2,
        "loss_streak": {"max_consecutive_losses": 3, "max_streak_amount": 3000, "min_losses_for_amount": 2},
        "vol_spike_mult": 1.5,
        "adaptive": {"start_mode": "choppy", "switch_after_consecutive_wins": 2,
            "trending_target_pts": {"NIFTY": 10, "BANKNIFTY": 15, "SENSEX": 6},
            "trending_sl_pts": {"NIFTY": 8, "BANKNIFTY": 18, "SENSEX": 12},
            "trending_be_lock_pts": {"NIFTY": 5, "BANKNIFTY": None, "SENSEX": None},
            "trending_neutral_exit": False},
    },
    "ZR_volspike_no_streak": {
        "desc": "Vol spike 1.5x WITHOUT loss streak (test if streak still needed)",
        "time_cutoff":  None, "min_vix": None, "max_vix": None, "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 3,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None, "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5, "capital": 100000, "shared_capital": True, "tick_gap_sec": 2,
        "vol_spike_mult": 1.5,
        "adaptive": {"start_mode": "choppy", "switch_after_consecutive_wins": 2,
            "trending_target_pts": {"NIFTY": 10, "BANKNIFTY": 15, "SENSEX": 6},
            "trending_sl_pts": {"NIFTY": 8, "BANKNIFTY": 18, "SENSEX": 12},
            "trending_be_lock_pts": {"NIFTY": 5, "BANKNIFTY": None, "SENSEX": None},
            "trending_neutral_exit": False},
    },
    "ZS_volspike_no_premcap": {
        "desc": "Vol spike 1.5x WITHOUT premium cap (test if premcap still needed)",
        "time_cutoff":  None, "min_vix": None, "max_vix": None, "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 3,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None, "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_lots": 5, "capital": 100000, "shared_capital": True, "tick_gap_sec": 2,
        "loss_streak": {"max_consecutive_losses": 3, "max_streak_amount": 3000, "min_losses_for_amount": 2},
        "vol_spike_mult": 1.5,
        "adaptive": {"start_mode": "choppy", "switch_after_consecutive_wins": 2,
            "trending_target_pts": {"NIFTY": 10, "BANKNIFTY": 15, "SENSEX": 6},
            "trending_sl_pts": {"NIFTY": 8, "BANKNIFTY": 18, "SENSEX": 12},
            "trending_be_lock_pts": {"NIFTY": 5, "BANKNIFTY": None, "SENSEX": None},
            "trending_neutral_exit": False},
    },
    "ZT_volspike_add_skip": {
        "desc": "Vol spike 1.5x + 10:00-10:30 skip (test if skip helps with vol_spike)",
        "time_cutoff":  None, "min_vix": None, "max_vix": None, "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 3,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None, "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5, "capital": 100000, "shared_capital": True, "tick_gap_sec": 2,
        "loss_streak": {"max_consecutive_losses": 3, "max_streak_amount": 3000, "min_losses_for_amount": 2},
        "entry_skip_window": ["10:00", "10:30"],
        "vol_spike_mult": 1.5,
        "adaptive": {"start_mode": "choppy", "switch_after_consecutive_wins": 2,
            "trending_target_pts": {"NIFTY": 10, "BANKNIFTY": 15, "SENSEX": 6},
            "trending_sl_pts": {"NIFTY": 8, "BANKNIFTY": 18, "SENSEX": 12},
            "trending_be_lock_pts": {"NIFTY": 5, "BANKNIFTY": None, "SENSEX": None},
            "trending_neutral_exit": False},
    },
    "ZU_volspike_add_pmsell": {
        "desc": "Vol spike 1.5x + PM SELL-only 12:30 (test if PM sell helps with vol_spike)",
        "time_cutoff":  None, "min_vix": None, "max_vix": None, "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 3,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None, "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5, "capital": 100000, "shared_capital": True, "tick_gap_sec": 2,
        "loss_streak": {"max_consecutive_losses": 3, "max_streak_amount": 3000, "min_losses_for_amount": 2},
        "afternoon_sell_only": "12:30",
        "vol_spike_mult": 1.5,
        "adaptive": {"start_mode": "choppy", "switch_after_consecutive_wins": 2,
            "trending_target_pts": {"NIFTY": 10, "BANKNIFTY": 15, "SENSEX": 6},
            "trending_sl_pts": {"NIFTY": 8, "BANKNIFTY": 18, "SENSEX": 12},
            "trending_be_lock_pts": {"NIFTY": 5, "BANKNIFTY": None, "SENSEX": None},
            "trending_neutral_exit": False},
    },
    "ZV_volspike_pcr": {
        "desc": "Vol spike 1.5x + PCR filter (best OI combo without imbalance/oi_confirm)",
        "time_cutoff":  None, "min_vix": None, "max_vix": None, "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 3,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None, "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5, "capital": 100000, "shared_capital": True, "tick_gap_sec": 2,
        "loss_streak": {"max_consecutive_losses": 3, "max_streak_amount": 3000, "min_losses_for_amount": 2},
        "vol_spike_mult": 1.5,
        "pcr_filter": {"min_for_buy": 0.7, "max_for_sell": 1.3},
        "adaptive": {"start_mode": "choppy", "switch_after_consecutive_wins": 2,
            "trending_target_pts": {"NIFTY": 10, "BANKNIFTY": 15, "SENSEX": 6},
            "trending_sl_pts": {"NIFTY": 8, "BANKNIFTY": 18, "SENSEX": 12},
            "trending_be_lock_pts": {"NIFTY": 5, "BANKNIFTY": None, "SENSEX": None},
            "trending_neutral_exit": False},
    },
    "ZW_volspike_bare": {
        "desc": "Vol spike 1.5x ONLY — no anti-spike, no streak, no premcap, no skip, no PM sell",
        "time_cutoff":  None, "min_vix": None, "max_vix": None, "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 3,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None, "anti_spike_pts": None,
        "neutral_exit": True,
        "max_lots": 5, "capital": 100000, "shared_capital": True, "tick_gap_sec": 2,
        "vol_spike_mult": 1.5,
        "adaptive": {"start_mode": "choppy", "switch_after_consecutive_wins": 2,
            "trending_target_pts": {"NIFTY": 10, "BANKNIFTY": 15, "SENSEX": 6},
            "trending_sl_pts": {"NIFTY": 8, "BANKNIFTY": 18, "SENSEX": 12},
            "trending_be_lock_pts": {"NIFTY": 5, "BANKNIFTY": None, "SENSEX": None},
            "trending_neutral_exit": False},
    },
    # ── COMBINED OI FILTER TESTS ──
    "ZX_oi_pcr": {
        "desc": "Adaptive + OI confirm + PCR (best 2 filters together)",
        "time_cutoff":  None, "min_vix": None, "max_vix": None, "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 3,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None, "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5, "capital": 100000, "shared_capital": True, "tick_gap_sec": 2,
        "loss_streak": {"max_consecutive_losses": 3, "max_streak_amount": 3000, "min_losses_for_amount": 2},
        "oi_confirm": True,
        "pcr_filter": {"min_for_buy": 0.7, "max_for_sell": 1.3},
        "adaptive": {"start_mode": "choppy", "switch_after_consecutive_wins": 2,
            "trending_target_pts": {"NIFTY": 10, "BANKNIFTY": 15, "SENSEX": 6},
            "trending_sl_pts": {"NIFTY": 8, "BANKNIFTY": 18, "SENSEX": 12},
            "trending_be_lock_pts": {"NIFTY": 5, "BANKNIFTY": None, "SENSEX": None},
            "trending_neutral_exit": False},
    },
    "ZY_oi_pcr_bare": {
        "desc": "OI confirm + PCR ONLY — no anti-spike, no streak, no premcap",
        "time_cutoff":  None, "min_vix": None, "max_vix": None, "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 3,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None, "anti_spike_pts": None,
        "neutral_exit": True,
        "max_lots": 5, "capital": 100000, "shared_capital": True, "tick_gap_sec": 2,
        "oi_confirm": True,
        "pcr_filter": {"min_for_buy": 0.7, "max_for_sell": 1.3},
        "adaptive": {"start_mode": "choppy", "switch_after_consecutive_wins": 2,
            "trending_target_pts": {"NIFTY": 10, "BANKNIFTY": 15, "SENSEX": 6},
            "trending_sl_pts": {"NIFTY": 8, "BANKNIFTY": 18, "SENSEX": 12},
            "trending_be_lock_pts": {"NIFTY": 5, "BANKNIFTY": None, "SENSEX": None},
            "trending_neutral_exit": False},
    },
    # ── ATR-BASED TARGET/SL VARIANT ──
    "ATR_base": {
        "desc": "ATR-based SL/target: 14-period 5-min ATR, SL=1.0×ATR, Target=1.5×ATR, risk-sized lots",
        "time_cutoff":  None, "min_vix": None, "max_vix": None, "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": None, "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None, "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5, "capital": 100000, "shared_capital": True, "tick_gap_sec": 2,
        "loss_streak": {"max_consecutive_losses": 3, "max_streak_amount": 3000, "min_losses_for_amount": 2},
        "entry_skip_window": None,
        "afternoon_sell_only": None,
        "atr_config": {
            "period": 14,
            "candle_minutes": 5,
            "sl_multiplier": 1.0,
            "target_multiplier": 1.5,
            "max_risk_per_trade": 1500,
        },
    },
    "ATR_no_neutral": {
        "desc": "ATR-based, neutral_exit OFF — test if signal noise is the cause",
        "time_cutoff":  None, "min_vix": None, "max_vix": None, "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": None, "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None, "anti_spike_pts": 1,
        "neutral_exit": False,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5, "capital": 100000, "shared_capital": True, "tick_gap_sec": 2,
        "loss_streak": {"max_consecutive_losses": 3, "max_streak_amount": 3000, "min_losses_for_amount": 2},
        "entry_skip_window": None,
        "afternoon_sell_only": None,
        "atr_config": {
            "period": 14,
            "candle_minutes": 5,
            "sl_multiplier": 1.0,
            "target_multiplier": 1.5,
            "max_risk_per_trade": 1500,
        },
    },
    # ── TEST 1: ZK_adaptive minus adaptive switch, always choppy, with v2 gate+sizing ──
    "V2_revised": {
        "desc": "Test1: No adaptive (always choppy), + regime gate + risk-equalized lots + afternoon reduction",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 3,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5,
        "capital": 100000,
        "shared_capital": True,
        "tick_gap_sec": 2,
        "loss_streak": {"max_consecutive_losses": 3, "max_streak_amount": 3000, "min_losses_for_amount": 2},
        "entry_skip_window": None,
        "afternoon_sell_only": None,
        "v2_config": {
            "risk_cap_morning":    {"NIFTY": 1500, "BANKNIFTY": 1500, "SENSEX": 1500},
            "risk_cap_afternoon":  {"NIFTY": 1500, "BANKNIFTY": 1500, "SENSEX": 1500},
            "afternoon_start":     "23:59",
            "regime_gate": {
                "min_signal_pct": 60,
                "max_flips": 2,
                "window_minutes": 15,
            },
            "first_trade_after": "09:30",
        },
    },
    # ── ROLLING GATE VARIANT: same as V2 but gate re-evaluates every tick on a sliding 15-min window ──
    "V2_rolling_gate": {
        "desc": "V2 with rolling-window gate (re-evaluates every tick on last 15 min, not fixed clock buckets)",
        "time_cutoff":  None,
        "min_vix":      None,
        "max_vix":      None,
        "min_strength": 4,
        "use_log_strength": True,
        "sl_pts":       {"NIFTY": 5,  "BANKNIFTY": 10, "SENSEX": 10},
        "target_pts":   {"NIFTY": 5,  "BANKNIFTY": 12, "SENSEX": 12},
        "be_lock_pts":  {"NIFTY": 3,  "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None,
        "anti_spike_pts": 1,
        "neutral_exit": True,
        "max_premium":  {"BANKNIFTY": 1000, "SENSEX": 500},
        "max_lots": 5,
        "capital": 100000,
        "shared_capital": True,
        "tick_gap_sec": 2,
        "loss_streak": {"max_consecutive_losses": 3, "max_streak_amount": 3000, "min_losses_for_amount": 2},
        "entry_skip_window": None,
        "afternoon_sell_only": None,
        "v2_config": {
            "risk_cap_morning":    {"NIFTY": 1500, "BANKNIFTY": 1500, "SENSEX": 1500},
            "risk_cap_afternoon":  {"NIFTY": 1500, "BANKNIFTY": 1500, "SENSEX": 1500},
            "afternoon_start":     "23:59",
            "first_trade_after":   "09:30",
            "regime_gate": {
                "min_signal_pct": 60,
                "max_flips": 2,
                "window_minutes": 15,
                "rolling": True,       # KEY DIFFERENCE: rolling window instead of fixed bucket
            },
        },
    },
    # ── OLD LEGACY CONFIG (user's previous trading_rules.json, before this diagnostic pass) ──
    "OLD_legacy": {
        "desc": "User's old config: per-strength STRONG/MEDIUM targets, no gate/adaptive/risk-cap",
        "time_cutoff":  None, "min_vix": None, "max_vix": None, "min_strength": 4,
        "use_log_strength": True,
        # Fallback sl/target (won't normally be used since sl_target_by_strength covers STRONG/MEDIUM)
        "sl_pts":       {"NIFTY": 10, "BANKNIFTY": 15, "SENSEX": 10},
        "target_pts":   {"NIFTY": 18, "BANKNIFTY": 20, "SENSEX": 20},
        "be_lock_pts":  {"NIFTY": None, "BANKNIFTY": None, "SENSEX": None},
        "no_move_abort": None, "anti_spike_pts": None,
        "neutral_exit": False,
        "max_lots": 5, "capital": 100000, "shared_capital": True, "tick_gap_sec": 180,
        "sl_target_by_strength": {
            "NIFTY": {
                "STRONG": {"target_pts": 20, "sl_pts": 15},
                "MEDIUM": {"target_pts": 18, "sl_pts": 10},
            },
            "BANKNIFTY": {
                "STRONG": {"target_pts": 40, "sl_pts": 20},
                "MEDIUM": {"target_pts": 20, "sl_pts": 15},
            },
            "SENSEX": {
                "STRONG": {"target_pts": 30, "sl_pts": 10},
                "MEDIUM": {"target_pts": 20, "sl_pts": 10},
            },
        },
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# SHARED-CAPITAL SIMULATION (all indices together, one capital pool)
# ══════════════════════════════════════════════════════════════════════════════

def simulate_shared_capital(records: list, cfg: dict) -> dict:
    """
    Simulate all indices together with shared capital, matching live engine.
    Processes records in timestamp order across all indices.
    Returns {index: [trades]} same as the per-index approach.
    """
    indices = ["NIFTY", "BANKNIFTY", "SENSEX"]
    lot_sizes = LOT_SIZE

    # Config
    sl_pts_cfg  = cfg['sl_pts']
    tgt_pts_cfg = cfg['target_pts']
    be_lock_cfg = cfg['be_lock_pts']
    min_str     = cfg['min_strength']
    spike_th    = cfg.get('anti_spike_pts')
    neut_exit   = cfg.get('neutral_exit', False)
    max_prem    = cfg.get('max_premium', {})
    use_log_str = cfg.get('use_log_strength', False)
    price_confirm_on = cfg.get('price_confirm', False)
    max_lots    = cfg.get('max_lots', 1)
    capital     = cfg.get('capital', 100000)
    tick_gap    = cfg.get('tick_gap_sec', 0)  # min seconds between exit and next entry
    loss_streak = cfg.get('loss_streak')       # {max_consecutive_losses, max_streak_amount, min_losses_for_amount}
    skip_window = cfg.get('entry_skip_window')  # ["10:00", "10:30"] or None
    pm_sell_only = cfg.get('afternoon_sell_only')  # "12:30" cutoff or None — block BUY entries after this time

    # OI / Volume confirmation filters (new fields from signal log)
    oi_confirm      = cfg.get('oi_confirm', False)       # require OI buildup to confirm direction
    vol_spike_mult  = cfg.get('vol_spike_mult')          # require volume > N× rolling avg (e.g. 1.5)
    imbalance_ratio = cfg.get('imbalance_ratio')         # require buy/sell qty ratio > N for BUY (e.g. 1.3)
    pcr_filter      = cfg.get('pcr_filter')              # {"min": 0.7, "max": 1.3} — skip if PCR outside range for BUY/SELL

    # V2 config: risk-equalized sizing + afternoon reduction + regime gate
    v2 = cfg.get('v2_config')
    v2_gate_open = {}  # {index: bool} — per-index gate state from last 15-min bucket
    v2_gate_ticks = {idx: [] for idx in indices}  # rolling ticks for gate evaluation
    v2_last_bucket = ''  # last evaluated 15-min bucket

    # Adaptive config switching (start choppy, switch to trending after N consecutive wins)
    adaptive    = cfg.get('adaptive')
    adaptive_switched = False
    all_closed_pnls = []  # global across indices for adaptive trigger

    # Make mutable copies so we can switch mid-day
    sl_pts_cfg  = dict(sl_pts_cfg)
    tgt_pts_cfg = dict(tgt_pts_cfg)
    be_lock_cfg = dict(be_lock_cfg)

    # Per-index state
    open_trades   = {}  # {index: trade_dict or None}
    price_hist    = {}  # {index: [prices]}
    pending_entry = {}  # {index: {price, opt, strike}}
    skip_until    = {}  # {index: ts}
    closed_pnls   = {idx: [] for idx in indices}  # {index: [pnl, ...]} for streak check
    trades_out    = {idx: [] for idx in indices}
    strike_entry_count = {idx: {} for idx in indices}  # {index: {(opt, strike): count}} -- for max_entries_per_strike
    strike_last_exit = {idx: {} for idx in indices}  # {index: {(opt, strike): exit_ts}} -- for strike_cooldown_min
    strike_last_exit_spot = {idx: {} for idx in indices}  # {index: {(opt, strike): spot_price}} -- for strike_reentry_min_spot_move
    last_price_change = {}  # {index: ts} — last time price changed (stale tick detection)

    # ATR state (per-index, per-option-type candle building)
    atr_cfg = cfg.get('atr_config')
    atr_candles   = {idx: {'CE': [], 'PE': []} for idx in indices}  # completed 5-min candles
    atr_current   = {idx: {'CE': None, 'PE': None} for idx in indices}  # in-progress candle
    atr_values    = {idx: {'CE': None, 'PE': None} for idx in indices}  # current ATR-14 value
    atr_candle_min = atr_cfg['candle_minutes'] if atr_cfg else 5
    atr_period     = atr_cfg['period'] if atr_cfg else 14

    # OI/Volume tracking state (per-index rolling history)
    oi_hist       = {idx: {"ce": [], "pe": []} for idx in indices}   # last N OI readings
    vol_hist      = {idx: {"ce": [], "pe": []} for idx in indices}   # last N volume readings

    avail_capital = capital

    for r in records:
        ts = r.get('ts', '')
        if not ts:
            continue
        index = r.get('index')
        if index not in indices:
            continue

        consensus = r.get('consensus')
        lot = lot_sizes[index]
        sl_pts = sl_pts_cfg[index]
        tgt_pts = tgt_pts_cfg[index]
        be_pts = be_lock_cfg.get(index)

        # Per-strength SL/target override (e.g. old config: STRONG vs MEDIUM different targets)
        by_strength = cfg.get('sl_target_by_strength')
        if by_strength:
            log_str = r.get('strength', '')
            idx_rules = by_strength.get(index, {})
            str_rule = idx_rules.get(log_str)
            if str_rule:
                sl_pts = str_rule.get('sl_pts', sl_pts)
                tgt_pts = str_rule.get('target_pts', tgt_pts)

        # V2 regime gate: fixed-bucket OR rolling-window evaluation
        if v2:
            gate_cfg = v2.get('regime_gate', {})
            window_min = gate_cfg.get('window_minutes', 15)
            rolling_gate = gate_cfg.get('rolling', False)  # True = rolling window, False = fixed bucket

            if rolling_gate:
                # Rolling window: append this tick with its timestamp, then evaluate the last
                # window_min minutes worth of ticks on every single tick.
                # v2_gate_ticks[idx] is a list of (ts, consensus) pairs for the rolling window.
                v2_gate_ticks[index].append((ts, consensus))
                # Trim to only ticks within the last window_min minutes
                cutoff = _add_minutes(ts, -window_min)
                v2_gate_ticks[index] = [(t, c) for t, c in v2_gate_ticks[index] if t >= cutoff]
                # Evaluate gate for THIS index on every tick (not just at bucket boundary)
                ticks_here = [c for _, c in v2_gate_ticks[index]]
                if ticks_here:
                    non_neutral = sum(1 for c in ticks_here if c and c != 'NEUTRAL')
                    signal_pct = non_neutral / len(ticks_here) * 100
                    flips = 0
                    prev_dir = None
                    for c in ticks_here:
                        if c and c != 'NEUTRAL':
                            if prev_dir and c != prev_dir:
                                flips += 1
                            prev_dir = c
                    # Only allow gate to open after first_trade_after time
                    first_trade = v2.get('first_trade_after', '09:30')
                    if ts[:5] >= first_trade:
                        v2_gate_open[index] = (signal_pct >= gate_cfg.get('min_signal_pct', 60)
                                               and flips < gate_cfg.get('max_flips', 2))
                    else:
                        v2_gate_open[index] = False
                else:
                    v2_gate_open[index] = False
            else:
                # Original fixed-bucket logic (unchanged)
                ts_parts = ts.split(':')
                if len(ts_parts) >= 2:
                    minute = int(ts_parts[1])
                    bucket = f"{ts_parts[0]}:{(minute // window_min) * window_min:02d}"

                    # At bucket boundary, evaluate gate BEFORE appending new tick
                    if bucket != v2_last_bucket and v2_last_bucket != '':
                        for gidx in indices:
                            ticks = v2_gate_ticks[gidx]
                            if not ticks:
                                v2_gate_open[gidx] = False
                                continue
                            non_neutral = sum(1 for c in ticks if c and c != 'NEUTRAL')
                            signal_pct = non_neutral / len(ticks) * 100
                            flips = 0
                            prev_dir = None
                            for c in ticks:
                                if c and c != 'NEUTRAL':
                                    if prev_dir and c != prev_dir:
                                        flips += 1
                                    prev_dir = c
                            v2_gate_open[gidx] = (signal_pct >= gate_cfg.get('min_signal_pct', 60)
                                                  and flips < gate_cfg.get('max_flips', 2))
                            v2_gate_ticks[gidx] = []  # reset for next bucket
                        v2_last_bucket = bucket
                    elif v2_last_bucket == '':
                        v2_last_bucket = bucket

                    # Collect tick for gate evaluation (after evaluation, for next bucket)
                    v2_gate_ticks[index].append(consensus)

        # Strength
        if use_log_str:
            log_strength = r.get('strength', '')
            strength = 99 if log_strength in ('STRONG', 'MEDIUM') else 0
        else:
            strat_list = r.get('strategies') or []
            strength = sum(1 for s in strat_list if s.get('signal') == consensus) if strat_list else 0

        opt = 'CE' if consensus == 'BUY' else ('PE' if consensus == 'SELL' else None)
        price_key = ('ce_price' if opt == 'CE' else 'pe_price') if opt else None
        price = r.get(price_key) if price_key else None

        # Update price history for anti-spike
        if price is not None:
            hist = price_hist.setdefault(index, [])
            # Track when price last changed (for stale tick detection)
            if not hist or abs(price - hist[-1]) > 0.01:
                last_price_change[index] = ts
            hist.append(price)
            if len(hist) > 10:
                hist.pop(0)

        # Build ATR candles from CE and PE prices
        if atr_cfg:
            for ot in ['CE', 'PE']:
                pk = 'ce_price' if ot == 'CE' else 'pe_price'
                p = r.get(pk)
                if p is None or p <= 0:
                    continue
                # Determine 5-min bucket
                ts_parts = ts.split(':')
                if len(ts_parts) >= 2:
                    minute = int(ts_parts[1])
                    bucket = f"{ts_parts[0]}:{(minute // atr_candle_min) * atr_candle_min:02d}"
                    cur = atr_current[index][ot]
                    if cur is None or cur.get('bucket') != bucket:
                        # Close previous candle
                        if cur is not None:
                            candle_list = atr_candles[index][ot]
                            candle_list.append(cur)
                            # Compute True Range
                            if len(candle_list) == 1:
                                tr = cur['high'] - cur['low']
                            else:
                                prev_c = candle_list[-2]['close']
                                tr = max(cur['high'] - cur['low'],
                                         abs(cur['high'] - prev_c),
                                         abs(cur['low'] - prev_c))
                            cur['tr'] = tr
                            # Update rolling ATR
                            if len(candle_list) >= atr_period:
                                prev_atr = atr_values[index][ot]
                                if prev_atr is None:
                                    atr_values[index][ot] = sum(c['tr'] for c in candle_list[-atr_period:]) / atr_period
                                else:
                                    atr_values[index][ot] = (prev_atr * (atr_period - 1) + tr) / atr_period
                        # Start new candle
                        atr_current[index][ot] = {'bucket': bucket, 'open': p, 'high': p, 'low': p, 'close': p}
                    else:
                        cur['high'] = max(cur['high'], p)
                        cur['low'] = min(cur['low'], p)
                        cur['close'] = p

        # Update OI / Volume history (new fields — absent in old logs)
        ce_oi = r.get('ce_oi', 0)
        pe_oi = r.get('pe_oi', 0)
        ce_vol = r.get('ce_volume', 0)
        pe_vol = r.get('pe_volume', 0)
        if ce_oi or pe_oi:
            oh = oi_hist[index]
            oh["ce"].append(ce_oi)
            oh["pe"].append(pe_oi)
            if len(oh["ce"]) > 20:
                oh["ce"].pop(0)
                oh["pe"].pop(0)
        if ce_vol or pe_vol:
            vh = vol_hist[index]
            vh["ce"].append(ce_vol)
            vh["pe"].append(pe_vol)
            if len(vh["ce"]) > 20:
                vh["ce"].pop(0)
                vh["pe"].pop(0)

        # ── EXIT CHECK ────────────────────────────────────────────────────
        ot = open_trades.get(index)
        if ot:
            rec_strike = r.get('atm_strike')
            strike_match = (rec_strike == ot.get('strike'))

            # Get price: ATM match → use ce/pe_price; adjacent → use atm_m1/p1; blind → open_trade.current_price
            cur = None
            if strike_match:
                ot_key = 'ce_price' if ot['opt'] == 'CE' else 'pe_price'
                cur = r.get(ot_key)
            else:
                # Try adjacent strike prices (ATM±1) logged since v2.0
                ot_strike = ot.get('strike')
                ot_opt_lower = ot['opt'].lower()  # 'ce' or 'pe'
                atm_m1_strike = r.get('atm_m1_strike')
                atm_p1_strike = r.get('atm_p1_strike')
                if atm_m1_strike == ot_strike:
                    cur = r.get(f'atm_m1_{ot_opt_lower}')
                elif atm_p1_strike == ot_strike:
                    cur = r.get(f'atm_p1_{ot_opt_lower}')

                # Fallback: use real engine's held contract LTP if it matches our simulated trade
                if cur is None:
                    log_ot = r.get('open_trade')
                    if log_ot and log_ot.get('current_price'):
                        log_name = log_ot.get('name', '')
                        # e.g. 'BANKNIFTY 57800 CE' → check strike + opt match
                        parts = log_name.split()
                        if len(parts) >= 3:
                            log_strike = int(parts[-2])
                            log_opt = parts[-1]
                            if log_strike == ot.get('strike') and log_opt == ot['opt']:
                                cur = log_ot['current_price']

            bp = ot['buy_price']

            # Use per-trade SL/target if stored (ATR-based), otherwise fall back to config
            trade_sl = ot.get('sl_pts', sl_pts)
            trade_tgt = ot.get('tgt_pts', tgt_pts)
            trade_be = ot.get('be_lock_pts', be_pts)

            # Price-based updates only when we have a valid price
            if cur is not None:
                move = cur - bp
                if move > ot['peak_gain']:
                    ot['peak_gain'] = move
                if trade_be and not ot['be_locked'] and move >= trade_be:
                    ot['be_locked'] = True
            else:
                move = 0.0  # no price available at all — assume flat

            eff_sl = 0.0 if ot['be_locked'] else -trade_sl
            exit_reason = None

            # Consensus-based exits work regardless of strike
            if neut_exit and consensus == 'NEUTRAL':
                exit_reason = 'SIGNAL_NEUTRAL'

            if exit_reason is None:
                trade_dir = 'BUY' if ot['opt'] == 'CE' else 'SELL'
                if consensus is not None and consensus != 'NEUTRAL' and consensus != trade_dir:
                    exit_reason = 'SIGNAL_REVERSAL'

            # Price-based exits only when strike matches
            if exit_reason is None and cur is not None:
                if move >= trade_tgt:
                    exit_reason = 'TARGET_HIT'
                elif move <= eff_sl:
                    exit_reason = 'BREAKEVEN_EXIT' if ot['be_locked'] else 'STOP_LOSS'

            if exit_reason:
                # Use actual price if available, else buy_price (flat exit)
                sell_price = cur if cur is not None else bp
                actual_move = sell_price - bp
                trade_lots = ot.get('lots', 1)
                pnl = round(actual_move * lot * trade_lots, 2)
                ot.update({
                    'exit_ts': ts,
                    'sell_price': round(sell_price, 2),
                    'pnl': pnl,
                    'exit_reason': exit_reason,
                    'peak_gain': round(ot['peak_gain'], 2),
                })
                trades_out[index].append(dict(ot))
                avail_capital += ot.get('cost', 0) + pnl
                closed_pnls[index].append(pnl)
                strike_last_exit[index][(ot['opt'], ot['strike'])] = ts
                strike_last_exit_spot[index][(ot['opt'], ot['strike'])] = r.get('spot_price')
                open_trades[index] = None
                gap_min = tick_gap / 60 if tick_gap > 0 else 4/60
                skip_until[index] = _add_minutes(ts, gap_min)

                # Adaptive config switch: after trade closes, check consecutive wins
                if adaptive and not adaptive_switched:
                    all_closed_pnls.append(pnl)
                    consec_wins = 0
                    for p in reversed(all_closed_pnls):
                        if p > 0:
                            consec_wins += 1
                        else:
                            break
                    trigger = adaptive.get('switch_after_consecutive_wins', 2)
                    if consec_wins >= trigger:
                        adaptive_switched = True
                        tgt_pts_cfg = dict(adaptive['trending_target_pts'])
                        sl_pts_cfg  = dict(adaptive['trending_sl_pts'])
                        be_lock_cfg = dict(adaptive['trending_be_lock_pts'])
                        neut_exit   = adaptive.get('trending_neutral_exit', neut_exit)

            continue  # position open or just closed — no new entry on same tick

        # ── ENTRY CHECK ───────────────────────────────────────────────────
        if opt is None or price is None:
            continue

        if index in skip_until and ts < skip_until[index]:
            continue

        if strength < min_str:
            continue

        # Entry skip window (e.g. 10:00-10:30 dead zone)
        if skip_window and skip_window[0] <= ts[:5] < skip_window[1]:
            continue

        # Afternoon SELL-only: block BUY entries after cutoff (e.g. 12:30)
        if pm_sell_only and ts[:5] >= pm_sell_only and opt == 'CE':
            continue

        # Loss streak block (per-index, resets on win)
        # loss_streak_disable_for: optional list of indices to exempt from the block,
        # used for isolated counterfactual testing (keeps block active for other indices)
        if loss_streak and index not in (cfg.get('loss_streak_disable_for') or []):
            cp = closed_pnls.get(index, [])
            s_count, s_loss = 0, 0
            for p in reversed(cp):
                if p >= 0:
                    break
                s_count += 1
                s_loss += abs(p)
            if s_count >= loss_streak.get('max_consecutive_losses', 3):
                continue
            if (s_count >= loss_streak.get('min_losses_for_amount', 2)
                    and s_loss >= loss_streak.get('max_streak_amount', 3000)):
                continue

        # No-repeat-strike / max-entries-per-strike: once a specific (opt, strike) has been
        # ENTERED N times for this index today, block further entries into that exact same
        # strike+direction (regardless of win/loss on those prior entries).
        # no_repeat_strike_opt=True is shorthand for max_entries_per_strike=1 (legacy name).
        max_entries = cfg.get('max_entries_per_strike')
        if max_entries is None and cfg.get('no_repeat_strike_opt'):
            max_entries = 1
        if max_entries is not None:
            candidate_strike = r.get('atm_strike')
            key = (opt, candidate_strike)
            if strike_entry_count[index].get(key, 0) >= max_entries:
                continue

        # Strike cooldown: allow re-entry into the same (opt, strike) again, but only
        # after strike_cooldown_min minutes have passed since it was last closed.
        strike_cooldown = cfg.get('strike_cooldown_min')
        if strike_cooldown is not None:
            candidate_strike = r.get('atm_strike')
            key = (opt, candidate_strike)
            last_exit = strike_last_exit[index].get(key)
            if last_exit is not None and ts < _add_minutes(last_exit, strike_cooldown):
                continue

        # Spot-move re-entry filter: allow re-entry into the same (opt, strike) again,
        # but only if the underlying spot has moved at least N points since that
        # strike/direction was last closed -- avoids re-entering into a whipsaw where
        # the option premium is noisy but the underlying hasn't genuinely moved.
        min_spot_move = cfg.get('strike_reentry_min_spot_move')
        if min_spot_move is not None:
            candidate_strike = r.get('atm_strike')
            key = (opt, candidate_strike)
            last_exit_spot = strike_last_exit_spot[index].get(key)
            current_spot = r.get('spot_price')
            if last_exit_spot is not None and current_spot is not None:
                if abs(current_spot - last_exit_spot) < min_spot_move:
                    continue

        prem_cap = max_prem.get(index)
        if prem_cap is not None and price is not None and price >= prem_cap:
            continue

        hist = price_hist.get(index, [])

        # 3-price warmup — need at least 3 prices before allowing entry
        # (matches live engine: anti-spike requires len(hist) >= 3)
        if len(hist) < 3:
            continue

        # Stale tick detection — skip if price hasn't changed in >5 seconds
        # (matches live engine: _auto_get_entry_snapshot rejects ticks with trade_age > 5s)
        last_change_ts = last_price_change.get(index, '')
        if last_change_ts and ts > last_change_ts:
            # Parse HH:MM:SS to compare seconds
            try:
                lc_parts = last_change_ts.split(':')
                ts_parts = ts.split(':')
                lc_sec = int(lc_parts[0])*3600 + int(lc_parts[1])*60 + int(lc_parts[2])
                ts_sec = int(ts_parts[0])*3600 + int(ts_parts[1])*60 + int(ts_parts[2])
                if ts_sec - lc_sec > 5:
                    continue  # stale tick — price hasn't changed in >5s
            except (ValueError, IndexError):
                pass

        if spike_th is not None and len(hist) >= 3:
            window = hist[-5:] if len(hist) >= 5 else hist
            avg = sum(window) / len(window)
            if price > avg + spike_th:
                continue

        # ── OI / Volume Confirmation Filters (skip gracefully if data absent) ──

        # OI Confirmation: for BUY(CE), CE OI should be rising (fresh longs building)
        #                  for SELL(PE), PE OI should be rising (fresh shorts building)
        # OI falling + price rising = short covering (weak rally) → skip
        if oi_confirm:
            oh = oi_hist[index]
            relevant_oi = oh["ce"] if opt == 'CE' else oh["pe"]
            if len(relevant_oi) >= 3:
                # Compare latest OI vs average of previous readings
                recent_oi = relevant_oi[-1]
                prev_avg = sum(relevant_oi[-5:-1]) / len(relevant_oi[-5:-1]) if len(relevant_oi) >= 4 else relevant_oi[-2]
                if recent_oi < prev_avg * 0.98:  # OI declining by >2% → weak move
                    continue

        # Volume Spike: require option volume > N× rolling average
        if vol_spike_mult is not None:
            vh = vol_hist[index]
            relevant_vol = vh["ce"] if opt == 'CE' else vh["pe"]
            if len(relevant_vol) >= 5:
                avg_vol = sum(relevant_vol[-10:-1]) / len(relevant_vol[-10:-1]) if len(relevant_vol) >= 10 else sum(relevant_vol[:-1]) / len(relevant_vol[:-1])
                cur_vol = relevant_vol[-1]
                if avg_vol > 0 and cur_vol < avg_vol * vol_spike_mult:
                    continue

        # Buy/Sell Qty Imbalance: buy_qty >> sell_qty confirms BUY, vice versa
        if imbalance_ratio is not None:
            ce_bq = r.get('ce_buy_qty', 0)
            ce_sq = r.get('ce_sell_qty', 0)
            pe_bq = r.get('pe_buy_qty', 0)
            pe_sq = r.get('pe_sell_qty', 0)
            if opt == 'CE' and ce_bq and ce_sq:
                if ce_sq > 0 and ce_bq / ce_sq < imbalance_ratio:
                    continue  # buyers not dominant enough for CE entry
            elif opt == 'PE' and pe_bq and pe_sq:
                if pe_sq > 0 and pe_bq / pe_sq < imbalance_ratio:
                    continue  # buyers not dominant enough for PE entry

        # PCR Filter: Put OI / Call OI ratio
        # PCR > 1 = more puts = bullish (supports BUY/CE)
        # PCR < 1 = more calls = bearish (supports SELL/PE)
        if pcr_filter is not None:
            _ce_oi = r.get('ce_oi', 0)
            _pe_oi = r.get('pe_oi', 0)
            if _ce_oi > 0 and _pe_oi > 0:
                pcr = _pe_oi / _ce_oi
                if opt == 'CE' and pcr < pcr_filter.get('min_for_buy', 0.7):
                    continue  # PCR too low for bullish entry
                if opt == 'PE' and pcr > pcr_filter.get('max_for_sell', 1.3):
                    continue  # PCR too high for bearish entry

        if price_confirm_on:
            pend = pending_entry.get(index)
            strike = r.get('atm_strike')
            if pend and pend['opt'] == opt and pend['strike'] == strike:
                pdiff = abs(price - pend['price'])
                if pdiff > sl_pts:
                    pending_entry[index] = {'price': price, 'opt': opt, 'strike': strike}
                    continue
                else:
                    pending_entry[index] = None
            else:
                pending_entry[index] = {'price': price, 'opt': opt, 'strike': strike}
                continue

        # Capital check — shared across all indices
        # V2: risk-equalized lots + regime gate + afternoon reduction
        if v2:
            # No trading before first gate check
            first_trade = v2.get('first_trade_after', '09:30')
            if ts[:5] < first_trade:
                continue
            
            # Regime gate: skip if gate is closed for this index
            if not v2_gate_open.get(index, False):
                continue
            
            # Risk-equalized lot sizing
            afternoon_start = v2.get('afternoon_start', '11:30')
            is_afternoon = ts[:5] >= afternoon_start
            if is_afternoon:
                risk_cap = v2['risk_cap_afternoon'].get(index, 1000)
            else:
                risk_cap = v2['risk_cap_morning'].get(index, 1500)
            
            risk_per_lot = sl_pts * lot
            if risk_per_lot <= 0:
                continue
            risk_lots = int(risk_cap // risk_per_lot)
            if risk_lots < 1:
                continue
            
            cost_per_lot = price * lot
            if cost_per_lot <= 0:
                continue
            affordable = int(avail_capital // cost_per_lot)
            num_lots = min(risk_lots, affordable, max_lots)
            if num_lots <= 0:
                continue
            # Log which constraint bound the lot count
            if num_lots == affordable and affordable < risk_lots and affordable < max_lots:
                lot_bound = 'capital'
            elif num_lots == risk_lots and risk_lots < max_lots:
                lot_bound = 'risk_cap'
            elif num_lots == max_lots:
                lot_bound = 'max_lots'
            else:
                lot_bound = 'multiple'
        elif atr_cfg:
            current_atr = atr_values[index].get(opt)
            if current_atr is None or current_atr <= 0:
                continue  # not enough candles to compute ATR yet
            atr_sl = round(current_atr * atr_cfg['sl_multiplier'], 2)
            atr_tgt = round(current_atr * atr_cfg['target_multiplier'], 2)
            max_risk = atr_cfg['max_risk_per_trade']
            risk_per_lot = atr_sl * lot
            if risk_per_lot <= 0:
                continue
            risk_lots = int(max_risk // risk_per_lot)
            if risk_lots < 1:
                continue  # ATR too high — skip trade, don't force
            cost_per_lot = price * lot
            if cost_per_lot <= 0:
                continue
            affordable = int(avail_capital // cost_per_lot)
            num_lots = min(risk_lots, affordable, max_lots)
            if num_lots <= 0:
                continue
            # Override SL/target for this trade
            sl_pts = atr_sl
            tgt_pts = atr_tgt
            be_pts = None  # no breakeven lock with ATR (let the trade breathe)
        else:
            cost_per_lot = price * lot
            if cost_per_lot <= 0:
                continue
            affordable = int(avail_capital // cost_per_lot)
            num_lots = min(affordable, max_lots)
            if num_lots <= 0:
                continue

        trade_cost = price * lot * num_lots
        avail_capital -= trade_cost

        open_trades[index] = {
            'index': index,
            'opt': opt,
            'strike': r.get('atm_strike'),
            'entry_ts': ts,
            'buy_price': round(price, 2),
            'peak_gain': 0.0,
            'be_locked': False,
            'lots': num_lots,
            'cost': trade_cost,
            'mode': 'trending' if adaptive_switched else ('choppy' if adaptive else None),
            'sl_pts': sl_pts,      # store per-trade SL (may be ATR-based)
            'tgt_pts': tgt_pts,    # store per-trade target (may be ATR-based)
            'be_lock_pts': be_pts, # store per-trade breakeven lock
            'lot_bound': lot_bound if v2 else None,  # what capped lot count
        }
        strike_entry_count[index][(opt, r.get('atm_strike'))] = strike_entry_count[index].get((opt, r.get('atm_strike')), 0) + 1

    # End of data — close open trades
    for index in indices:
        ot = open_trades.get(index)
        if ot and records:
            lot = lot_sizes[index]
            ot_key = 'ce_price' if ot['opt'] == 'CE' else 'pe_price'
            trade_strike = ot.get('strike')
            # Try ATM-match price first, then open_trade.current_price, then buy_price
            last_price = next(
                (r[ot_key] for r in reversed(records) if r.get('index') == index and r.get(ot_key) is not None and r.get('atm_strike') == trade_strike),
                None
            )
            if last_price is None:
                last_price = next(
                    (r['open_trade']['current_price'] for r in reversed(records)
                     if r.get('index') == index and r.get('open_trade') and r['open_trade'].get('current_price')
                     and r['open_trade'].get('name', '').split()[-2:] == [str(trade_strike), ot['opt']]),
                    ot['buy_price']
                )
            move = last_price - ot['buy_price']
            trade_lots = ot.get('lots', 1)
            pnl = round(move * lot * trade_lots, 2)
            ot.update({
                'exit_ts': records[-1]['ts'],
                'sell_price': round(last_price, 2),
                'pnl': pnl,
                'exit_reason': 'END_OF_DATA',
                'peak_gain': round(ot['peak_gain'], 2),
            })
            trades_out[index].append(dict(ot))

    return trades_out


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _ts_to_sec(ts: str) -> int:
    """HH:MM:SS → total seconds since midnight."""
    parts = ts.split(':')
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
    return h * 3600 + m * 60 + s


def _add_minutes(ts: str, minutes: float) -> str:
    """Add minutes to HH:MM:SS, return HH:MM:SS."""
    total = _ts_to_sec(ts) + int(minutes * 60)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _time_diff_sec(ts1: str, ts2: str) -> int:
    """Seconds elapsed from ts1 to ts2 (HH:MM:SS strings)."""
    return _ts_to_sec(ts2) - _ts_to_sec(ts1)


# ══════════════════════════════════════════════════════════════════════════════
# SIMULATION ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def simulate_index(recs: list, index: str, cfg: dict) -> list:
    """
    Simulate one index with given config.
    No cooldown or max-trades limit — purely signal driven.
    Only constraint: one open trade at a time per index.

    Returns list of simulated trade dicts.
    """
    lot      = LOT_SIZE[index]
    sl_pts   = cfg['sl_pts'][index]
    tgt_pts  = cfg['target_pts'][index]
    be_pts   = cfg['be_lock_pts'].get(index)
    min_str  = cfg['min_strength']
    cutoff   = cfg.get('time_cutoff')
    min_vix  = cfg.get('min_vix')
    max_vix  = cfg.get('max_vix')
    no_move  = cfg.get('no_move_abort')     # {"pts": N, "sec": S} or None
    spike_th = cfg.get('anti_spike_pts')    # float or None
    neut_exit = cfg.get('neutral_exit', False)  # exit on neutral signal
    cd_sl    = cfg.get('cooldown_sl_min', 0)     # cooldown minutes after SL/BE
    cd_other = cfg.get('cooldown_other_min', 0)  # cooldown minutes after target/other
    max_trades = cfg.get('max_trades')           # max trades per index (None = unlimited)
    consec_sl_max = cfg.get('consec_sl_block')   # block after N consecutive SLs (None = disabled)
    mom_guard = cfg.get('momentum_guard', False) # skip if premium < last buy on same strike
    max_prem = cfg.get('max_premium', {})           # {index: max_price} skip if premium >= N
    use_log_str = cfg.get('use_log_strength', False)  # use signal log's strength field instead of counting
    price_confirm = cfg.get('price_confirm', False)   # require 2 consecutive stable prices before entry
    max_lots   = cfg.get('max_lots', 1)               # max lots per trade (1 = current, 5 = live engine)
    capital    = cfg.get('capital', 100000)            # starting capital for lot calculation
    tick_gap   = cfg.get('tick_gap_sec', 0)            # min seconds between exit and next entry (0 = use default 4s)
    loss_streak = cfg.get('loss_streak')                 # streak combo filter config
    skip_window = cfg.get('entry_skip_window')             # ["10:00", "10:30"] or None

    # OI / Volume confirmation filters
    oi_confirm      = cfg.get('oi_confirm', False)
    vol_spike_mult  = cfg.get('vol_spike_mult')
    imbalance_ratio = cfg.get('imbalance_ratio')
    pcr_filter      = cfg.get('pcr_filter')

    open_trade    = None
    skip_until_ts = None   # minimum gap after exit (prevents same-tick re-entry)
    price_hist    = []     # rolling window (last 10) for anti-spike
    trades        = []
    closed_pnls   = []     # [pnl, ...] for loss streak check
    last_price_change_ts = ''  # last time price changed (stale tick detection)
    consec_sl_count = 0    # consecutive SL counter
    index_blocked   = False
    last_buy_price  = {}   # {(strike, opt): price} — for momentum guard
    pending_entry   = None # {price, opt, strike} — for price confirmation
    avail_capital  = capital  # track available capital

    # OI/Volume tracking state
    oi_hist_ce, oi_hist_pe = [], []
    vol_hist_ce, vol_hist_pe = [], []

    for r in recs:
        ts        = r.get('ts', '')
        if not ts:
            continue
        consensus = r.get('consensus')
        # strength: either use log field or count strategies
        if use_log_str:
            log_strength = r.get('strength', '')
            strength = 99 if log_strength in ('STRONG', 'MEDIUM') else 0
        else:
            strat_list = r.get('strategies') or []
            strength   = sum(1 for s in strat_list if s.get('signal') == consensus) if strat_list else 0
        vix       = r.get('vix')

        opt       = 'CE' if consensus == 'BUY' else ('PE' if consensus == 'SELL' else None)
        price_key = ('ce_price' if opt == 'CE' else 'pe_price') if opt else None
        price     = r.get(price_key) if price_key else None

        # keep rolling option-price history for anti-spike check
        if price is not None:
            # Track when price last changed (for stale tick detection)
            if not price_hist or abs(price - price_hist[-1]) > 0.01:
                last_price_change_ts = ts
            price_hist.append(price)
            if len(price_hist) > 10:
                price_hist.pop(0)

        # Update OI / Volume history (new fields — absent in old logs)
        _ce_oi_val = r.get('ce_oi', 0)
        _pe_oi_val = r.get('pe_oi', 0)
        _ce_vol_val = r.get('ce_volume', 0)
        _pe_vol_val = r.get('pe_volume', 0)
        if _ce_oi_val or _pe_oi_val:
            oi_hist_ce.append(_ce_oi_val)
            oi_hist_pe.append(_pe_oi_val)
            if len(oi_hist_ce) > 20:
                oi_hist_ce.pop(0)
                oi_hist_pe.pop(0)
        if _ce_vol_val or _pe_vol_val:
            vol_hist_ce.append(_ce_vol_val)
            vol_hist_pe.append(_pe_vol_val)
            if len(vol_hist_ce) > 20:
                vol_hist_ce.pop(0)
                vol_hist_pe.pop(0)

        # ── EXIT CHECK ────────────────────────────────────────────────────────
        if open_trade:
            rec_strike = r.get('atm_strike')
            strike_match = (rec_strike == open_trade.get('strike'))

            # Get price: ATM match → use ce/pe_price; adjacent → use atm_m1/p1; blind → open_trade.current_price
            cur = None
            if strike_match:
                ot_key = 'ce_price' if open_trade['opt'] == 'CE' else 'pe_price'
                cur = r.get(ot_key)
            else:
                # Try adjacent strike prices (ATM±1) logged since v2.0
                ot_strike = open_trade.get('strike')
                ot_opt_lower = open_trade['opt'].lower()
                atm_m1_strike = r.get('atm_m1_strike')
                atm_p1_strike = r.get('atm_p1_strike')
                if atm_m1_strike == ot_strike:
                    cur = r.get(f'atm_m1_{ot_opt_lower}')
                elif atm_p1_strike == ot_strike:
                    cur = r.get(f'atm_p1_{ot_opt_lower}')

                # Fallback: use real engine's held contract LTP if it matches our simulated trade
                if cur is None:
                    log_ot = r.get('open_trade')
                    if log_ot and log_ot.get('current_price'):
                        log_name = log_ot.get('name', '')
                        parts = log_name.split()
                        if len(parts) >= 3:
                            log_strike = int(parts[-2])
                            log_opt = parts[-1]
                            if log_strike == open_trade.get('strike') and log_opt == open_trade['opt']:
                                cur = log_ot['current_price']

            bp = open_trade['buy_price']

            # Price-based updates only when we have a valid price
            if cur is not None:
                move = cur - bp
                if move > open_trade['peak_gain']:
                    open_trade['peak_gain'] = move
                if be_pts and not open_trade['be_locked'] and move >= be_pts:
                    open_trade['be_locked'] = True
            else:
                move = 0.0  # no price available at all — assume flat

            eff_sl = 0.0 if open_trade['be_locked'] else -sl_pts

            exit_reason = None

            # Consensus-based exits work regardless of strike
            if neut_exit and consensus == 'NEUTRAL':
                exit_reason = 'SIGNAL_NEUTRAL'

            # no-move abort: if elapsed > sec and peak never reached pts → exit flat
            if no_move:
                elapsed = _time_diff_sec(open_trade['entry_ts'], ts)
                if elapsed >= no_move['sec'] and open_trade['peak_gain'] < no_move['pts']:
                    exit_reason = 'NO_MOVE_ABORT'

            if exit_reason is None:
                trade_dir = 'BUY' if open_trade['opt'] == 'CE' else 'SELL'
                if consensus is not None and consensus != 'NEUTRAL' and consensus != trade_dir:
                    exit_reason = 'SIGNAL_REVERSAL'

            # Price-based exits only when strike matches
            if exit_reason is None and cur is not None:
                if move >= tgt_pts:
                    exit_reason = 'TARGET_HIT'
                elif move <= eff_sl:
                    exit_reason = 'BREAKEVEN_EXIT' if open_trade['be_locked'] else 'STOP_LOSS'

            if exit_reason:
                # Use actual price if available, else buy_price (flat exit)
                sell_price = cur if cur is not None else bp
                actual_move = sell_price - bp
                trade_lots = open_trade.get('lots', 1)
                pnl = round(actual_move * lot * trade_lots, 2)
                open_trade.update({
                    'exit_ts':     ts,
                    'sell_price':  round(sell_price, 2),
                    'pnl':         pnl,
                    'exit_reason': exit_reason,
                    'peak_gain':   round(open_trade['peak_gain'], 2),
                })
                trades.append(dict(open_trade))
                # return capital: cost of position + pnl
                avail_capital += open_trade.get('cost', 0) + pnl
                closed_pnls.append(pnl)
                # track consecutive SLs
                if exit_reason == 'STOP_LOSS':
                    consec_sl_count += 1
                    if consec_sl_max and consec_sl_count >= consec_sl_max:
                        index_blocked = True
                elif exit_reason in ('TARGET_HIT', 'BREAKEVEN_EXIT') and pnl > 0:
                    consec_sl_count = 0  # reset on win
                open_trade    = None
                # cooldown: use tick_gap if set, else configured minutes, else 4-second default
                if tick_gap > 0:
                    skip_until_ts = _add_minutes(ts, tick_gap / 60)
                elif exit_reason in ('STOP_LOSS', 'BREAKEVEN_EXIT') and cd_sl > 0:
                    skip_until_ts = _add_minutes(ts, cd_sl)
                elif exit_reason not in ('STOP_LOSS', 'BREAKEVEN_EXIT') and cd_other > 0:
                    skip_until_ts = _add_minutes(ts, cd_other)
                else:
                    skip_until_ts = _add_minutes(ts, 4/60)  # 4-second gap

            continue   # no new entry on same tick as exit

        # ── ENTRY CHECK ───────────────────────────────────────────────────────
        if opt is None or price is None:
            continue

        # minimum gap after previous exit (4 seconds = ~2 ticks)
        if skip_until_ts and ts < skip_until_ts:
            continue

        # max trades per index
        if max_trades is not None and len(trades) >= max_trades:
            continue

        # time cutoff
        if cutoff and ts[:5] >= cutoff:
            continue

        # VIX filter
        if min_vix is not None and vix is not None and vix < min_vix:
            continue
        if max_vix is not None and vix is not None and vix > max_vix:
            continue

        # consecutive SL block
        if index_blocked:
            continue

        # signal strength
        if strength < min_str:
            continue

        # entry skip window (e.g. 10:00-10:30 dead zone)
        if skip_window and skip_window[0] <= ts[:5] < skip_window[1]:
            continue

        # loss streak block (resets on win)
        if loss_streak:
            s_count, s_loss = 0, 0
            for p in reversed(closed_pnls):
                if p >= 0:
                    break
                s_count += 1
                s_loss += abs(p)
            if s_count >= loss_streak.get('max_consecutive_losses', 3):
                continue
            if (s_count >= loss_streak.get('min_losses_for_amount', 2)
                    and s_loss >= loss_streak.get('max_streak_amount', 3000)):
                continue

        # momentum guard: skip if premium < last buy on same strike+opt
        if mom_guard and price is not None:
            strike = r.get('atm_strike')
            key = (strike, opt)
            prev = last_buy_price.get(key)
            if prev is not None and price < prev:
                continue

        # premium cap: skip if option premium too high for this index
        prem_cap = max_prem.get(index)
        if prem_cap is not None and price is not None and price >= prem_cap:
            continue

        # 3-price warmup — need at least 3 prices before allowing entry
        if len(price_hist) < 3:
            continue

        # Stale tick detection — skip if price hasn't changed in >5 seconds
        if last_price_change_ts and ts > last_price_change_ts:
            try:
                lc_parts = last_price_change_ts.split(':')
                ts_parts = ts.split(':')
                lc_sec = int(lc_parts[0])*3600 + int(lc_parts[1])*60 + int(lc_parts[2])
                ts_sec = int(ts_parts[0])*3600 + int(ts_parts[1])*60 + int(ts_parts[2])
                if ts_sec - lc_sec > 5:
                    continue  # stale tick
            except (ValueError, IndexError):
                pass

        # anti-spike: skip if current price is more than N pts above recent average
        if spike_th is not None and len(price_hist) >= 3:
            window = price_hist[-5:] if len(price_hist) >= 5 else price_hist
            avg    = sum(window) / len(window)
            if price > avg + spike_th:
                continue

        # ── OI / Volume Confirmation Filters (skip gracefully if data absent) ──

        if oi_confirm:
            relevant_oi = oi_hist_ce if opt == 'CE' else oi_hist_pe
            if len(relevant_oi) >= 3:
                recent_oi = relevant_oi[-1]
                prev_avg = sum(relevant_oi[-5:-1]) / len(relevant_oi[-5:-1]) if len(relevant_oi) >= 4 else relevant_oi[-2]
                if recent_oi < prev_avg * 0.98:
                    continue

        if vol_spike_mult is not None:
            relevant_vol = vol_hist_ce if opt == 'CE' else vol_hist_pe
            if len(relevant_vol) >= 5:
                avg_vol = sum(relevant_vol[-10:-1]) / len(relevant_vol[-10:-1]) if len(relevant_vol) >= 10 else sum(relevant_vol[:-1]) / len(relevant_vol[:-1])
                cur_vol = relevant_vol[-1]
                if avg_vol > 0 and cur_vol < avg_vol * vol_spike_mult:
                    continue

        if imbalance_ratio is not None:
            ce_bq = r.get('ce_buy_qty', 0)
            ce_sq = r.get('ce_sell_qty', 0)
            pe_bq = r.get('pe_buy_qty', 0)
            pe_sq = r.get('pe_sell_qty', 0)
            if opt == 'CE' and ce_bq and ce_sq:
                if ce_sq > 0 and ce_bq / ce_sq < imbalance_ratio:
                    continue
            elif opt == 'PE' and pe_bq and pe_sq:
                if pe_sq > 0 and pe_bq / pe_sq < imbalance_ratio:
                    continue

        if pcr_filter is not None:
            _ce_oi_f = r.get('ce_oi', 0)
            _pe_oi_f = r.get('pe_oi', 0)
            if _ce_oi_f > 0 and _pe_oi_f > 0:
                pcr = _pe_oi_f / _ce_oi_f
                if opt == 'CE' and pcr < pcr_filter.get('min_for_buy', 0.7):
                    continue
                if opt == 'PE' and pcr > pcr_filter.get('max_for_sell', 1.3):
                    continue

        # price confirmation: require 2 consecutive readings with price diff ≤ SL
        if price_confirm:
            strike = r.get('atm_strike')
            if pending_entry and pending_entry['opt'] == opt and pending_entry['strike'] == strike:
                pdiff = abs(price - pending_entry['price'])
                if pdiff > sl_pts:
                    # price moved too much — reset and wait
                    pending_entry = {'price': price, 'opt': opt, 'strike': strike}
                    continue
                else:
                    # confirmed — clear pending, proceed to entry
                    pending_entry = None
            else:
                # first reading — store and wait
                pending_entry = {'price': price, 'opt': opt, 'strike': strike}
                continue

        # ENTER TRADE
        # calculate lots based on available capital
        cost_per_lot = price * lot
        if cost_per_lot <= 0:
            continue
        affordable = int(avail_capital // cost_per_lot)
        num_lots = min(affordable, max_lots)
        if num_lots <= 0:
            continue  # can't afford even 1 lot

        # track last buy for momentum guard
        if mom_guard:
            strike = r.get('atm_strike')
            last_buy_price[(strike, opt)] = price

        trade_cost = price * lot * num_lots
        avail_capital -= trade_cost

        open_trade = {
            'index':     index,
            'opt':       opt,
            'strike':    r.get('atm_strike'),
            'entry_ts':  ts,
            'buy_price': round(price, 2),
            'peak_gain': 0.0,
            'be_locked': False,
            'lots':      num_lots,
            'cost':      trade_cost,
        }

    # end of data — close any still-open trade at last known price
    if open_trade and recs:
        ot_key     = 'ce_price' if open_trade['opt'] == 'CE' else 'pe_price'
        trade_strike = open_trade.get('strike')
        # Try ATM-match price first, then open_trade.current_price, then buy_price
        last_price = next(
            (r[ot_key] for r in reversed(recs) if r.get(ot_key) is not None and r.get('atm_strike') == trade_strike),
            None
        )
        if last_price is None:
            last_price = next(
                (r['open_trade']['current_price'] for r in reversed(recs)
                 if r.get('open_trade') and r['open_trade'].get('current_price')
                 and r['open_trade'].get('name', '').split()[-2:] == [str(trade_strike), open_trade['opt']]),
                open_trade['buy_price']
            )
        move = last_price - open_trade['buy_price']
        trade_lots = open_trade.get('lots', 1)
        pnl  = round(move * lot * trade_lots, 2)
        open_trade.update({
            'exit_ts':     recs[-1]['ts'],
            'sell_price':  round(last_price, 2),
            'pnl':         pnl,
            'exit_reason': 'END_OF_DATA',
            'peak_gain':   round(open_trade['peak_gain'], 2),
        })
        trades.append(dict(open_trade))

    return trades


# ══════════════════════════════════════════════════════════════════════════════
# KILL SWITCH (cross-index post-processing)
# ══════════════════════════════════════════════════════════════════════════════

def apply_kill_switch(vtrades: dict, kill_limit: float) -> dict:
    """
    Simulate daily loss kill switch across all indices.

    Once cumulative *realized* PnL (across all closed trades, all indices)
    reaches -kill_limit, no new entries are allowed.

    Works by:
      1. Merging all trades, sorting by exit_ts (PnL realized at close)
      2. Accumulating PnL until it hits -kill_limit → record kill_time
      3. Removing trades that entered after kill_time
    """
    all_trades = []
    for idx, trades in vtrades.items():
        for t in trades:
            all_trades.append(t)

    if not all_trades:
        return vtrades

    # Sort by exit_ts — PnL is realized when trade closes
    all_trades.sort(key=lambda t: t['exit_ts'])

    cumulative = 0.0
    kill_time = None
    for t in all_trades:
        cumulative += t['pnl']
        if cumulative <= -kill_limit:
            kill_time = t['exit_ts']
            break

    if kill_time is None:
        return vtrades  # kill switch never triggered

    # Remove trades that ENTERED after kill_time
    filtered = {}
    for idx, trades in vtrades.items():
        filtered[idx] = [t for t in trades if t['entry_ts'] <= kill_time]

    return filtered


# ══════════════════════════════════════════════════════════════════════════════
# REPORTING
# ══════════════════════════════════════════════════════════════════════════════

def summarize(trades: list) -> dict:
    total  = len(trades)
    wins   = sum(1 for t in trades if t['pnl'] > 0)
    losses = sum(1 for t in trades if t['pnl'] < 0)
    flat   = total - wins - losses
    pnl    = sum(t['pnl'] for t in trades)
    wr     = (wins / total * 100) if total else 0.0
    return {"total": total, "wins": wins, "losses": losses, "flat": flat, "pnl": pnl, "win_rate": wr}


def print_trade_rows(trades: list):
    for t in sorted(trades, key=lambda x: x['entry_ts']):
        move = t['sell_price'] - t['buy_price']
        be   = " [BE-locked]" if t.get('be_locked') else ""
        flag = " ✓" if t['pnl'] > 0 else (" ✗" if t['pnl'] < 0 else "")
        print(f"      {t['entry_ts']}→{t['exit_ts']} | {t['index']:10s} {t['opt']}"
              f" | ₹{t['buy_price']:>7.1f} → ₹{t['sell_price']:>7.1f} ({move:+.1f})"
              f" | PnL ₹{t['pnl']:>+7.0f} | peak +{t['peak_gain']:>4.1f}"
              f" | {t['exit_reason']}{be}{flag}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        ist_now  = datetime.utcnow() + timedelta(hours=5, minutes=30)
        date_str = ist_now.strftime("%Y-%m-%d")

    log_path = os.path.join(SIGNAL_LOGS_DIR, f"{date_str}.jsonl")
    if not os.path.exists(log_path):
        print(f"\nNo signal log found for {date_str}")
        print(f"Expected: {log_path}")
        sys.exit(1)

    # load records
    records = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if not records:
        print(f"Signal log is empty for {date_str}")
        sys.exit(1)

    indices  = ["NIFTY", "BANKNIFTY", "SENSEX"]
    start_ts = records[0].get('ts', '?')
    end_ts   = records[-1].get('ts', '?')

    print(f"\n{'='*72}")
    print(f"  SIGNAL LOG BACKTEST — {date_str}")
    print(f"  Window: {start_ts} – {end_ts} IST   ({len(records):,} records)")
    if start_ts > "09:45":
        print(f"  NOTE: Log starts after 09:45 — morning session not simulated.")
    print(f"{'='*72}\n")

    # run all variants
    results = {}
    for vname, cfg in VARIANTS.items():
        if cfg.get('shared_capital'):
            # Shared capital simulation — all indices together
            vtrades = simulate_shared_capital(records, cfg)
        else:
            vtrades = {}
            for idx in indices:
                idx_recs     = [r for r in records if r.get('index') == idx]
                vtrades[idx] = simulate_index(idx_recs, idx, cfg)
        # apply kill switch if configured (cross-index daily loss limit)
        kill_limit = cfg.get('kill_switch_loss')
        if kill_limit is not None:
            vtrades = apply_kill_switch(vtrades, kill_limit)
        results[vname] = vtrades

    # ── SUMMARY TABLE ─────────────────────────────────────────────────────────
    print(f"{'Variant':<24} {'#':>3} {'W':>3} {'L':>3} {'WR%':>6} {'PnL (₹)':>10}  Description")
    print('─' * 80)
    for vname, vtrades in results.items():
        all_t = [t for idx_t in vtrades.values() for t in idx_t]
        s     = summarize(all_t)
        print(f"{vname:<24} {s['total']:>3} {s['wins']:>3} {s['losses']:>3} "
              f"{s['win_rate']:>5.0f}%  {s['pnl']:>+10.0f}  {VARIANTS[vname]['desc']}")

    # ── PER-VARIANT DETAIL ────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print("  DETAILED TRADE LOG")
    print(f"{'='*72}")

    for vname, vtrades in results.items():
        all_t = [t for idx_t in vtrades.values() for t in idx_t]
        s     = summarize(all_t)
        print(f"\n── {vname}")
        print(f"   {VARIANTS[vname]['desc']}")
        print(f"   {s['total']} trades | {s['wins']}W {s['losses']}L | "
              f"WR {s['win_rate']:.0f}% | PnL ₹{s['pnl']:+.0f}")

        if not all_t:
            print("   (no trades in this window)")
            continue

        for idx in indices:
            idx_t = vtrades[idx]
            if not idx_t:
                continue
            idx_s = summarize(idx_t)
            print(f"   {idx}: {idx_s['total']} trades | ₹{idx_s['pnl']:+.0f} | WR {idx_s['win_rate']:.0f}%")
            print_trade_rows(idx_t)

    print(f"\n{'='*72}")
    print("  Tip: add new variants to the VARIANTS dict at the top of this file.")
    print(f"{'='*72}\n")


if __name__ == '__main__':
    main()
