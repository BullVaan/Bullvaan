import json

with open('data/premarket_snapshots.jsonl') as f:
    snaps = [json.loads(l) for l in f]

with open('data/nifty_option_history.json') as f:
    opt = json.load(f)

skip = {'2026-07-16', '2026-07-20'}
snap_map = {s['snapshot_taken_at'][:10]: s for s in snaps}

print('%-12s %+8s %-5s  %8s %-5s %-4s  %-28s %-10s  %-18s %-12s' % (
    'Date','Gap','Sig','NIKKEI%','NK','NK?','Actual Open vs prev','IEP?','Source','Confidence'))
print('-' * 125)

for date in sorted(snap_map):
    if date in skip:
        continue
    s = snap_map[date]
    gn = s['kite']['gift_nifty']['last_price']
    ni = s['kite'].get('indian_indices', {}).get('NIFTY', {})
    prev_close = ni.get('ohlc', {}).get('close', 0)
    snap_iep   = ni.get('ohlc', {}).get('open', 0)
    if not prev_close:
        continue

    gap = round(gn - prev_close, 1)
    gift_sig = 'BULL' if gap > 30 else ('BEAR' if gap < -30 else 'FLAT')

    nk = s.get('global_indices', {}).get('nikkei', {})
    nk_price = nk.get('last_price', 0)
    nk_prev  = nk.get('previous_close', 0)
    nk_pct = round((nk_price - nk_prev) / nk_prev * 100, 2) if (nk_price and nk_prev) else 0
    nk_dir = 'UP' if nk_pct > 0.2 else ('DOWN' if nk_pct < -0.2 else 'FLAT')
    nk_ok  = (gift_sig == 'BULL' and nk_dir == 'UP') or (gift_sig == 'BEAR' and nk_dir == 'DOWN')
    nk_str = 'YES' if (gift_sig == 'FLAT' or nk_ok) else 'NO'

    # IEP: prefer snapshot open (late snapshots), else spot_open from option history
    if snap_iep != 0:
        iep_price  = snap_iep
        iep_source = 'from snapshot'
    elif date in opt:
        iep_price  = opt[date]['spot_open']
        iep_source = 'spot_open @9:15'
    else:
        iep_price  = None
        iep_source = 'not available'

    if iep_price is not None:
        iep_chg = round(iep_price - prev_close, 1)
        iep_dir  = 'BULL' if iep_chg > 0 else 'BEAR'
        iep_val  = '%+.1f (%.2f) %s' % (iep_chg, iep_price, iep_dir)
        if gift_sig == 'FLAT':
            iep_sig = 'N/A'
        else:
            iep_sig = 'CONFIRMS' if iep_dir == gift_sig else 'CONFLICTS'
    else:
        iep_val  = 'not available'
        iep_sig  = '—'

    # Overall confidence
    if gift_sig == 'FLAT':
        overall = 'SKIP'
    elif nk_ok and iep_sig == 'CONFIRMS':
        overall = 'HIGH (all 3)'
    elif nk_ok or iep_sig == 'CONFIRMS':
        overall = 'MEDIUM (2/3)'
    else:
        overall = 'LOWER (1/3)'

    print('%-12s %+8.1f %-5s  %+7.2f%% %-5s %-4s  %-28s %-10s  %-18s %-12s' % (
        date, gap, gift_sig, nk_pct, nk_dir, nk_str, iep_val, iep_sig, iep_source, overall))
