PRIMARY = ["Supertrend", "EMA", "MACD"]
FILTER = ["RSI", "ADX", "Volume"]
CONFIRM = ["VWAP", "BB"]

WEIGHTS = {
    "PRIMARY": 3,
    "FILTER": 1,
    "CONFIRM": 2
}


def categorize(name):
    for p in PRIMARY:
        if p in name:
            return "PRIMARY"
    for f in FILTER:
        if f in name:
            return "FILTER"
    for c in CONFIRM:
        if c in name:
            return "CONFIRM"
    return "OTHER"


def calculate_score(signals):

    score = 0
    max_score = 0

    for s in signals:

        category = categorize(s["name"])
        weight = WEIGHTS.get(category, 0)

        max_score += weight

        if s["signal"] == "BUY":
            score += weight
        elif s["signal"] == "SELL":
            score -= weight

    # decision
    if score >= 3:
        decision = "BUY"
    elif score <= -3:
        decision = "SELL"
    else:
        decision = "NEUTRAL"

    confidence = round(abs(score) / max_score * 100, 2) if max_score else 0

    return decision, confidence, score
