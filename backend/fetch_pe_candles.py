"""
fetch_pe_candles.py
===================
Fetch PE option candles for a specific date and strike for simulation/analysis.

Usage:
    python fetch_pe_candles.py                        # today, ATM+100 PE
    python fetch_pe_candles.py 2026-08-05 24700       # specific date + strike
"""

import os, sys, json, logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from kiteconnect import KiteConnect

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger(__name__)

load_dotenv()
IST = timezone(timedelta(hours=5, minutes=30))

OUTPUT_FILE = 'data/nifty_pe_history.json'


def _kite():
    kite = KiteConnect(api_key=os.getenv('API_KEY'))
    kite.set_access_token(os.getenv('ACCESS_TOKEN'))
    return kite


def fetch_pe_strikes(trade_date: str, atm: int):
    kite = _kite()
    log.info(f"Loading instruments for NFO …")
    insts = kite.instruments('NFO')

    td = datetime.strptime(trade_date, '%Y-%m-%d').date()
    expiries = sorted(set(
        i['expiry'] for i in insts
        if i['name'] == 'NIFTY' and i['instrument_type'] == 'PE' and i['expiry'] >= td
    ))
    expiry = str(expiries[0])
    log.info(f"Nearest expiry: {expiry}  ATM={atm}")

    token_map = {
        i['strike']: i for i in insts
        if i['name'] == 'NIFTY' and str(i['expiry']) == expiry and i['instrument_type'] == 'PE'
    }

    strikes_map = {
        'OTM_50':  atm - 50,
        'ATM':     atm,
        'ITM_50':  atm + 50,
        'ITM_100': atm + 100,
        'ITM_150': atm + 150,
    }

    from_dt = datetime.strptime(trade_date + ' 09:15', '%Y-%m-%d %H:%M')
    to_dt   = datetime.strptime(trade_date + ' 15:30', '%Y-%m-%d %H:%M')

    result = {'strikes': {}}
    for label, strike in strikes_map.items():
        inst = token_map.get(strike)
        if not inst:
            log.warning(f"  {label} ({strike} PE): not found"); continue
        candles = kite.historical_data(inst['instrument_token'], from_dt, to_dt, '5minute')
        result['strikes'][label] = {
            'strike':        strike,
            'tradingsymbol': inst['tradingsymbol'],
            'opt_type':      'PE',
            'candles': [
                {'ts': str(c['date']), 'o': c['open'], 'h': c['high'],
                 'l': c['low'], 'c': c['close'], 'v': c['volume']}
                for c in candles
            ],
        }
        c0 = candles[0]
        log.info(f"  {label:8} {strike} PE: {len(candles)} candles  open={c0['open']}  close={candles[-1]['close']}")

    return result


def main():
    trade_date = sys.argv[1] if len(sys.argv) > 1 else datetime.now(IST).strftime('%Y-%m-%d')
    atm        = int(sys.argv[2]) if len(sys.argv) > 2 else 24600   # default ATM for Aug 5

    log.info(f"Fetching NIFTY PE candles for {trade_date}  ATM={atm}")
    data = fetch_pe_strikes(trade_date, atm)

    try:
        with open(OUTPUT_FILE) as f:
            existing = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        existing = {}

    existing[trade_date] = data
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(existing, f, indent=2)
    log.info(f"Saved to {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
