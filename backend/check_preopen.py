import json, sys

target_date = sys.argv[1] if len(sys.argv) > 1 else '2026-07-22'

with open('data/premarket_snapshots.jsonl') as f:
    entries = [json.loads(l) for l in f]

for snap in entries:
    date = snap['snapshot_taken_at'][:10]
    if date != target_date:
        continue

    kite     = snap['kite']
    taken_at = snap['snapshot_taken_at']

    nifty     = kite['indian_indices']['NIFTY']
    banknifty = kite['indian_indices']['BANKNIFTY']
    sensex    = kite['indian_indices']['SENSEX']
    gift      = kite['gift_nifty']

    nifty_prev_close = nifty['ohlc']['close']
    gift_price       = gift['last_price']
    gift_gap         = gift_price - nifty_prev_close

    # Pre-open equilibrium = ohlc.open of the index at time of snapshot
    nifty_preopen     = nifty['ohlc'].get('open', 'N/A')
    banknifty_preopen = banknifty['ohlc'].get('open', 'N/A')
    sensex_preopen    = sensex['ohlc'].get('open', 'N/A')

    nifty_preopen_gap     = (nifty_preopen - nifty_prev_close) if isinstance(nifty_preopen, float) else 'N/A'
    banknifty_prev_close  = banknifty['ohlc']['close']
    sensex_prev_close     = sensex['ohlc']['close']
    banknifty_preopen_gap = (banknifty_preopen - banknifty_prev_close) if isinstance(banknifty_preopen, float) else 'N/A'
    sensex_preopen_gap    = (sensex_preopen - sensex_prev_close) if isinstance(sensex_preopen, float) else 'N/A'

    print('=' * 60)
    print(f'Date: {date}  |  Snapshot at: {taken_at}')
    print('=' * 60)
    print(f'\nGIFT NIFTY last price : {gift_price}')
    print(f'NIFTY prev close      : {nifty_prev_close}')
    print(f'GIFT NIFTY gap        : {gift_gap:+.1f}  --> {"BULL" if gift_gap > 30 else "BEAR" if gift_gap < -30 else "FLAT"}')

    print(f'\n--- Pre-open auction prices (ohlc.open at {taken_at}) ---')
    print(f'NIFTY     preopen: {nifty_preopen}  (prev close: {nifty_prev_close})  gap: {nifty_preopen_gap if isinstance(nifty_preopen_gap, str) else f"{nifty_preopen_gap:+.1f}"}')
    print(f'BANKNIFTY preopen: {banknifty_preopen}  (prev close: {banknifty_prev_close})  gap: {banknifty_preopen_gap if isinstance(banknifty_preopen_gap, str) else f"{banknifty_preopen_gap:+.1f}"}')
    print(f'SENSEX    preopen: {sensex_preopen}  (prev close: {sensex_prev_close})  gap: {sensex_preopen_gap if isinstance(sensex_preopen_gap, str) else f"{sensex_preopen_gap:+.1f}"}')

    print(f'\n--- Full NIFTY raw data ---')
    print(json.dumps(nifty, indent=2))
