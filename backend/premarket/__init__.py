# backend/premarket/
# Isolated premarket directional trading module.
# Completely decoupled from auto_trader.py — no shared state, no imports between them.
#
# Files:
#   signal.py      — pure calculations (gap, IEP, confidence). No Kite dependency.
#   run_signal.py  — morning terminal script (9:00–9:10 AM). Prints direction + action.
#   executor.py    — trade placement + monitoring loop (9:15 or 9:20 AM).
