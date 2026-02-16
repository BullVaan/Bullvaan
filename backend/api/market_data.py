import yfinance as yf

SYMBOLS = {
    "nifty": "^NSEI",
    "sensex": "^BSESN",
    "banknifty": "^NSEBANK"
}

def fetch_indices():
    result = {}

    for name, symbol in SYMBOLS.items():
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d")

            if data.empty:
                result[name] = None
            else:
                result[name] = round(float(data["Close"].iloc[-1]), 2)

        except Exception:
            result[name] = None

    return result
