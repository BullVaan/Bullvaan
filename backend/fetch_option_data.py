"""
fetch_option_data.py
====================
Run this every evening after 15:30 to save option candle data for all 3 indices.

Usage:
    python fetch_option_data.py              # fetches today's data
    python fetch_option_data.py 2026-07-28   # fetches a specific date

Saves to:
    data/nifty_option_history.json
    data/banknifty_option_history.json
    data/sensex_option_history.json
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from kiteconnect import KiteConnect

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger(__name__)

load_dotenv()
IST = timezone(timedelta(hours=5, minutes=30))

# ── Index config ─────────────────────────────────────────────────────────────
INDEX_CONFIGS = {
    'NIFTY': {
        'exchange':        'NFO',
        'strike_interval': 50,
        'lot_size':        65,
        'file':            'data/nifty_option_history.json',
        'pe_file':         'data/nifty_pe_history.json',
    },
    'BANKNIFTY': {
        'exchange':        'NFO',
        'strike_interval': 100,
        'lot_size':        30,
        'file':            'data/banknifty_option_history.json',
        'pe_file':         'data/banknifty_pe_history.json',
    },
    'SENSEX': {
        'exchange':        'BFO',
        'strike_interval': 100,
        'lot_size':        20,
        'file':            'data/sensex_option_history.json',
        'pe_file':         'data/sensex_pe_history.json',
    },
}


def get_direction_from_snapshot(trade_date: str) -> str:
    """Read premarket snapshot and compute GIFT NIFTY gap direction."""
    try:
        with open('data/premarket_snapshots.jsonl') as f:
            for line in f:
                d = json.loads(line)
                ts = d.get('snapshot_taken_at', '')
                if trade_date in ts:
                    gift = d['kite']['gift_nifty']['last_price']
                    nifty_prev = d['kite']['indian_indices']['NIFTY']['ohlc']['close']
                    gap = gift - nifty_prev
                    if gap > 30:
                        return 'BULLISH'
                    elif gap < -30:
                        return 'BEARISH'
                    else:
                        return 'FLAT'
    except Exception as e:
        log.warning(f'Could not read snapshot for {trade_date}: {e}')
    return 'UNKNOWN'


def get_spot_opens(trade_date: str) -> dict:
    """Read signal log and get first-candle spot price for each index."""
    opens = {}
    try:
        with open(f'data/signal_logs/{trade_date}.jsonl') as f:
            seen = set()
            for line in f:
                e = json.loads(line)
                idx = e.get('index')
                if idx and idx not in seen:
                    opens[idx] = e['spot_price']
                    seen.add(idx)
                if len(seen) >= 3:
                    break
    except FileNotFoundError:
        log.warning(f'No signal log for {trade_date}')
    return opens


def find_nearest_expiry(insts, index_name: str, opt_type: str, trade_date: str) -> str:
    """Find the nearest upcoming expiry for this index on the trade date."""
    td = datetime.strptime(trade_date, '%Y-%m-%d').date()
    expiries = sorted(set(
        i['expiry'] for i in insts
        if i['name'] == index_name
        and i['instrument_type'] == opt_type
        and i['expiry'] >= td
    ))
    if not expiries:
        return None
    return str(expiries[0])


def fetch_strikes(kite, insts, index_name: str, trade_date: str,
                  spot_open: float, expiry: str, opt_type: str, strike_interval: int, lot_size: int) -> dict:
    """Fetch 5-min candles for 5 strikes (OTM_50, ATM, ITM_50, ITM_100, ITM_150)."""
    from_dt = datetime.strptime(trade_date + ' 09:15', '%Y-%m-%d %H:%M')
    to_dt   = datetime.strptime(trade_date + ' 15:30', '%Y-%m-%d %H:%M')

    atm = round(spot_open / strike_interval) * strike_interval
    # CE: ITM = lower strike; PE: ITM = higher strike
    if opt_type == 'PE':
        strikes_map = {
            'OTM_50':  atm - strike_interval,
            'ATM':     atm,
            'ITM_50':  atm + strike_interval,
            'ITM_100': atm + 2 * strike_interval,
            'ITM_150': atm + 3 * strike_interval,
        }
    else:
        strikes_map = {
            'OTM_50':  atm + strike_interval,
            'ATM':     atm,
            'ITM_50':  atm - strike_interval,
            'ITM_100': atm - 2 * strike_interval,
            'ITM_150': atm - 3 * strike_interval,
        }

    token_map = {
        i['strike']: i for i in insts
        if i['name'] == index_name
        and str(i['expiry']) == expiry
        and i['instrument_type'] == opt_type
    }

    result = {
        'pm_direction': None,
        'spot_open':    spot_open,
        'atm':          atm,
        'opt_type':     opt_type,
        'lot_size':     lot_size,
        'expiry':       expiry,
        'strikes':      {},
    }

    for label, strike in strikes_map.items():
        inst = token_map.get(strike)
        if not inst:
            log.warning(f'  {label} ({strike} {opt_type}): NOT FOUND in instruments')
            continue
        candles = kite.historical_data(inst['instrument_token'], from_dt, to_dt, '5minute')
        result['strikes'][label] = {
            'strike':        strike,
            'tradingsymbol': inst['tradingsymbol'],
            'candles': [
                {'ts': str(c['date']), 'o': c['open'], 'h': c['high'],
                 'l': c['low'], 'c': c['close'], 'v': c['volume']}
                for c in candles
            ],
        }
        log.info(f'  {label:8} {strike} {opt_type}: {len(candles)} candles  '
                 f'open={candles[0]["open"]}  close={candles[-1]["close"]}')

    return result


def load_history(filepath: str) -> dict:
    try:
        with open(filepath) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_history(filepath: str, data: dict):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def main():
    trade_date = sys.argv[1] if len(sys.argv) > 1 else datetime.now(IST).strftime('%Y-%m-%d')
    log.info(f'Fetching option data for {trade_date}')

    # Auth
    kite = KiteConnect(api_key=os.getenv('API_KEY'))
    kite.set_access_token(os.getenv('ACCESS_TOKEN'))

    # Direction from premarket snapshot
    direction = get_direction_from_snapshot(trade_date)
    log.info(f'Direction: {direction}')

    # Spot opens from signal log
    spot_opens = get_spot_opens(trade_date)
    log.info(f'Spot opens: {spot_opens}')

    if not spot_opens:
        log.error('No spot data found. Is the signal log present? Aborting.')
        return

    # Always fetch both CE and PE regardless of direction

    # Load instruments once per exchange
    log.info('Loading NFO instruments...')
    nfo = kite.instruments('NFO')
    log.info('Loading BFO instruments...')
    bfo = kite.instruments('BFO')

    exchange_insts = {'NFO': nfo, 'BFO': bfo}

    for index_name, cfg in INDEX_CONFIGS.items():
        spot = spot_opens.get(index_name)
        if spot is None:
            log.warning(f'{index_name}: no spot open found in signal log, skipping')
            continue

        insts = exchange_insts[cfg['exchange']]

        for opt_type in ('CE', 'PE'):
            expiry = find_nearest_expiry(insts, index_name, opt_type, trade_date)
            if not expiry:
                log.warning(f'{index_name} {opt_type}: no expiry found, skipping')
                continue

            log.info(f'\n=== {index_name} | spot={spot} | expiry={expiry} | {opt_type} ===')

            result = fetch_strikes(
                kite, insts, index_name, trade_date,
                spot, expiry, opt_type,
                cfg['strike_interval'], cfg['lot_size']
            )
            result['pm_direction'] = direction

            out_file = cfg['pe_file'] if opt_type == 'PE' else cfg['file']
            history = load_history(out_file)
            history[trade_date] = result
            save_history(out_file, history)
            log.info(f'Saved to {out_file}  (total days: {len(history)})')

    log.info('\nDone.')


if __name__ == '__main__':
    main()
