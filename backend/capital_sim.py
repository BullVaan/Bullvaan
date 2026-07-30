import json

CONFIGS = {
    'NIFTY':     {'file': 'data/nifty_option_history.json',     'lot': 65, 'interval': 50,  'sl': 50, 't': 60},
    'BANKNIFTY': {'file': 'data/banknifty_option_history.json', 'lot': 30, 'interval': 100, 'sl': 75, 't': 60},
    'SENSEX':    {'file': 'data/sensex_option_history.json',    'lot': 20, 'interval': 100, 'sl': 75, 't': 60},
}
CAPITAL = 100_000  # Rs 1 lakh per index

def simulate(candles, entry_idx, target, sl):
    ep = candles[entry_idx]['o']
    for i in range(entry_idx, len(candles)):
        lo, hi = candles[i]['l'], candles[i]['h']
        if sl and lo <= ep - sl:
            return ep, -sl, 'SL'
        if hi >= ep + target:
            return ep, target, 'TARGET'
    return ep, candles[-1]['c'] - ep, 'EOD'

data = {}
all_dates = set()
for idx, cfg in CONFIGS.items():
    with open(cfg['file']) as f:
        data[idx] = json.load(f)
    all_dates.update(data[idx].keys())

print('=' * 105)
print('CAPITAL SIM — Rs.1 LAKH per index | NIFTY(SL=50) BANKNIFTY(SL=75) SENSEX(SL=75) | T=60 | 09:20 entry')
print('=' * 105)
print('{:12}  {:^30}  {:^30}  {:^24}  {:>10}'.format('Date', 'NIFTY', 'BANKNIFTY', 'SENSEX', 'DAY TOTAL'))
print('-' * 105)

grand = {'NIFTY': 0, 'BANKNIFTY': 0, 'SENSEX': 0, 'ALL': 0}

for date in sorted(all_dates):
    col = {}
    day_total = 0
    for idx, cfg in CONFIGS.items():
        hist = data[idx]
        if date not in hist:
            col[idx] = 'no data'
            continue
        day = hist[date]
        direction = day['pm_direction']
        if direction == 'FLAT':
            col[idx] = 'FLAT-skip'
            continue
        opt_type = day['opt_type']
        focus = 'ITM_100' if opt_type == 'CE' else 'OTM_50'
        candles = day['strikes'][focus]['candles']
        ep, rpts, outcome = simulate(candles, 1, cfg['t'], cfg['sl'])
        lots = max(1, int(CAPITAL // (ep * cfg['lot'])))
        pnl = lots * rpts * cfg['lot']
        grand[idx] += pnl
        day_total += pnl
        col[idx] = '%dL@%.0f -> %+.0f (%s)' % (lots, ep, pnl, outcome[0])
    grand['ALL'] += day_total
    print('{:12}  {:^30}  {:^30}  {:^24}  {:>+10,.0f}'.format(
        date,
        col.get('NIFTY', '—'),
        col.get('BANKNIFTY', '—'),
        col.get('SENSEX', '—'),
        day_total
    ))

print('-' * 105)
nf_str = 'NIFTY: %+.0f' % grand['NIFTY']
bn_str = 'BANKNIFTY: %+.0f' % grand['BANKNIFTY']
sx_str = 'SENSEX: %+.0f' % grand['SENSEX']
print('{:12}  {:^30}  {:^30}  {:^24}  {:>+10,.0f}'.format(
    'TOTALS', nf_str, bn_str, sx_str, grand['ALL']
))

print()
print('PER-INDEX DETAIL')
print('-' * 70)
for idx, cfg in CONFIGS.items():
    hist = data[idx]
    trade_days = [(d, h) for d, h in hist.items() if h['pm_direction'] != 'FLAT']
    w = 0
    pnls = []
    for d, day in trade_days:
        opt_type = day['opt_type']
        focus = 'ITM_100' if opt_type == 'CE' else 'OTM_50'
        candles = day['strikes'][focus]['candles']
        ep, rpts, outcome = simulate(candles, 1, cfg['t'], cfg['sl'])
        lots = max(1, int(CAPITAL // (ep * cfg['lot'])))
        pnl = lots * rpts * cfg['lot']
        pnls.append(pnl)
        if pnl > 0:
            w += 1
    n = len(trade_days)
    total = sum(pnls)
    print('  {:10} {:2} days  {}W {}L  Total: {:>+10,.0f}  Avg/day: {:>+8,.0f}  Max loss: {:>+8,.0f}  Max win: {:>+8,.0f}'.format(
        idx, n, w, n - w, total, total // n, min(pnls), max(pnls)
    ))

print()
print('  Capital deployed per day : Rs.{:.0f} lakh (3 x Rs.1L)'.format(3 * CAPITAL / 1e5))
print('  Grand total P&L          : Rs.{:+,.0f}'.format(grand['ALL']))
