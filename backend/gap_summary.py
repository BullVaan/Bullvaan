import json

with open('data/premarket_snapshots.jsonl') as f:
    lines = [json.loads(l) for l in f]

header = "%-12s %-10s %10s %11s %8s %s" % ("Date", "Snap Time", "GIFT 9AM", "NIFTY Prev", "Gap", "Signal")
print(header)
print('-' * 65)
for s in lines:
    date = s['snapshot_taken_at'][:10]
    time = s['snapshot_taken_at'][11:16]
    gn = s['kite']['gift_nifty']['last_price']
    ni_close = s['kite'].get('indian_indices', {}).get('NIFTY', {}).get('ohlc', {}).get('close', None)
    if ni_close:
        gap = round(gn - ni_close, 1)
        sig = 'BULLISH' if gap > 30 else ('BEARISH' if gap < -30 else 'FLAT')
        print("%-12s %-10s %10s %11s %8s %s" % (date, time, gn, ni_close, gap, sig))
    else:
        print("%-12s %-10s %10s %11s %8s" % (date, time, gn, 'N/A', 'N/A'))
