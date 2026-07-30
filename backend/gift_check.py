import os, sys
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
from kiteconnect import KiteConnect

kite = KiteConnect(api_key=os.getenv('API_KEY'))
kite.set_access_token(os.getenv('ACCESS_TOKEN'))

date = sys.argv[1] if len(sys.argv) > 1 else '2026-07-22'

candles = kite.historical_data(
    instrument_token=291849,
    from_date=date,
    to_date=date,
    interval='5minute'
)

print(f'GIFT NIFTY 5-min candles for {date}')
print(f'{"Time":<20} {"Open":>8} {"High":>8} {"Low":>8} {"Close":>8} {"Vol":>7}')
print('-' * 65)
for c in candles:
    ts = c['date']
    t = ts.strftime('%Y-%m-%d %H:%M') if hasattr(ts, 'strftime') else str(ts)
    # Show 8:30 AM to 9:30 AM range (premarket + first hour)
    hour = int(t[11:13])
    minute = int(t[14:16])
    if (hour == 8 and minute >= 30) or (hour == 9 and minute <= 30):
        print(f"{t}   {c['open']:>8.1f}  {c['high']:>8.1f}  {c['low']:>8.1f}  {c['close']:>8.1f}  {c['volume']:>7}")
