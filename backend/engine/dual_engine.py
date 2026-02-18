PRIMARY = ["Supertrend", "EMA", "MACD"]
FILTER = ["RSI", "ADX", "Volume"]
CONFIRM = ["VWAP", "BB"]

def get_weight(name, mode):

    if mode == "trend":
        if any(x in name for x in PRIMARY): return 3
        if any(x in name for x in CONFIRM): return 2
        return 1

    # scalping weights
    if "VWAP" in name: return 3
    if "Stoch" in name: return 2
    if "EMA" in name: return 2
    if "RSI" in name: return 1
    return 1


def calculate_score(signals, mode):

    score = 0
    max_score = 0

    for s in signals:
        weight = get_weight(s["name"], mode)
        max_score += weight

        if s["signal"] == "BUY":
            score += weight
        elif s["signal"] == "SELL":
            score -= weight

    confidence = abs(score) / max_score * 100 if max_score else 0

    if score > 0:
        decision = "BUY"
    elif score < 0:
        decision = "SELL"
    else:
        decision = "NEUTRAL"

    return decision, round(confidence,2), score
