"""
Test LIVE NIFTY prediction with all 10 strategies
Fetches real Nifty 50 data and runs consensus engine
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from api.kotak_neo import KotakNeoClient
from strategies.strategy_1_moving_average import MovingAverageStrategy
from strategies.strategy_2_rsi import RSIStrategy
from strategies.strategy_3_macd import MACDStrategy
from strategies.strategy_4_bollinger_bands import BollingerBandsStrategy
from strategies.strategy_5_ema_crossover import EMACrossoverStrategy
from strategies.strategy_6_supertrend import SupertrendStrategy
from strategies.strategy_7_vwap import VWAPStrategy
from strategies.strategy_8_stochastic import StochasticStrategy
from strategies.strategy_9_adx import ADXStrategy
from strategies.strategy_10_volume import VolumeStrategy
import pandas as pd
from datetime import datetime, timedelta

def get_consensus_signal(df, strategies, threshold=0.7):
    """Calculate consensus from multiple strategies"""
    signals = []
    
    print("\n" + "=" * 60)
    print("INDIVIDUAL STRATEGY SIGNALS")
    print("=" * 60)
    
    for strategy in strategies:
        signal = strategy.calculate(df)
        signals.append(signal)
        
        # Get signal details
        signal_data = strategy.get_signal()
        metadata = signal_data.get('metadata', {})
        
        print(f"\n{strategy.name}:")
        print(f"  Signal: {signal}")
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.2f}")
                else:
                    print(f"  {key}: {value}")
    
    # Count votes
    buy_votes = signals.count("BUY")
    sell_votes = signals.count("SELL")
    neutral_votes = signals.count("NEUTRAL")
    
    total_votes = len(signals)
    buy_percentage = buy_votes / total_votes
    sell_percentage = sell_votes / total_votes
    
    print("\n" + "=" * 60)
    print("CONSENSUS RESULTS")
    print("=" * 60)
    print(f"Total Strategies: {total_votes}")
    print(f"BUY votes: {buy_votes} ({buy_percentage*100:.1f}%)")
    print(f"SELL votes: {sell_votes} ({sell_percentage*100:.1f}%)")
    print(f"NEUTRAL votes: {neutral_votes} ({neutral_votes/total_votes*100:.1f}%)")
    print(f"Threshold: {threshold*100:.0f}% ({int(threshold*total_votes)}/{total_votes} strategies)")
    
    # Make decision
    if buy_percentage >= threshold:
        consensus = "BUY"
        print(f"\n✅ CONSENSUS: {consensus}")
        print(f"   {buy_votes} out of {total_votes} strategies agree!")
    elif sell_percentage >= threshold:
        consensus = "SELL"
        print(f"\n❌ CONSENSUS: {consensus}")
        print(f"   {sell_votes} out of {total_votes} strategies agree!")
    else:
        consensus = "NEUTRAL"
        print(f"\n⚪ CONSENSUS: {consensus}")
        print(f"   Not enough agreement (need {int(threshold*total_votes)}/{total_votes})")
    
    return consensus, buy_votes, sell_votes, neutral_votes

def main():
    print("=" * 70)
    print("LIVE NIFTY 50 PREDICTION - 10 STRATEGY CONSENSUS")
    print("=" * 70)
    print()
    
    # Initialize client
    client = KotakNeoClient()
    
    # Authenticate
    print("Step 1: Authenticating with Kotak Neo...")
    if not client.authenticate():
        print("❌ Authentication failed!")
        return
    
    print("✅ Authenticated successfully!\n")
    
    # Fetch Nifty 50 historical data
    print("Step 2: Fetching NIFTY 50 historical data...")
    print("(Need at least 30-40 candles for strategy calculations)")
    
    symbol = "NIFTY 50"
    exchange = "nse_cm"
    
    # Get last 2 days of 5-minute data
    from_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    to_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"Fetching: {symbol} ({exchange})")
    print(f"Period: {from_date} to {to_date}")
    print(f"Interval: 5 minutes\n")
    
    df = client.get_historical_data(
        symbol=symbol,
        exchange_segment=exchange,
        from_date=from_date,
        to_date=to_date,
        interval="5"  # 5-minute candles
    )
    
    if df is None or df.empty:
        print("❌ Could not fetch historical data!")
        print("\nPossible reasons:")
        print("  1. API returns 503 outside market hours")
        print("  2. Markets closed (9:15 AM - 3:30 PM IST)")
        print("  3. Symbol format incorrect")
        print("\n⏰ Current time in India: ~1:20 PM IST (markets SHOULD be open)")
        print("\n💡 Note: Kotak Neo API seems to have issues during market hours too")
        print("   Historical data may only be available after market close")
        return
    
    print(f"✅ Retrieved {len(df)} candles!")
    print("\nLatest data:")
    print(df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail(5))
    print(f"\nCurrent NIFTY Price: ₹{df['close'].iloc[-1]:.2f}")
    
    # Initialize all 10 strategies
    print("\n" + "=" * 60)
    print("INITIALIZING 10 TRADING STRATEGIES")
    print("=" * 60)
    
    strategies = [
        MovingAverageStrategy(period=20),
        RSIStrategy(period=14, oversold=40, overbought=60),
        MACDStrategy(fast=5, slow=13, signal=1),
        BollingerBandsStrategy(period=20, std_dev=2),
        EMACrossoverStrategy(short_period=9, long_period=21),
        SupertrendStrategy(period=10, multiplier=3),
        VWAPStrategy(),
        StochasticStrategy(k_period=14, d_period=3),
        ADXStrategy(period=14, threshold=25),
        VolumeStrategy(period=20)
    ]
    
    for i, strategy in enumerate(strategies, 1):
        print(f"{i}. {strategy.name}")
    
    # Get consensus
    print("\n" + "=" * 60)
    print("RUNNING CONSENSUS ENGINE")
    print("=" * 60)
    
    # Test with 70% threshold (7 out of 10 must agree)
    consensus, buy_votes, sell_votes, neutral_votes = get_consensus_signal(
        df, strategies, threshold=0.7
    )
    
    # Show different thresholds
    print("\n" + "=" * 60)
    print("CONSENSUS AT DIFFERENT THRESHOLDS")
    print("=" * 60)
    
    for threshold, label in [(0.5, "Testing"), (0.6, "Medium"), (0.7, "Production")]:
        needed = int(threshold * len(strategies))
        if buy_votes >= needed:
            result = "✅ BUY"
        elif sell_votes >= needed:
            result = "❌ SELL"
        else:
            result = "⚪ NEUTRAL"
        print(f"{label} ({threshold*100:.0f}%): {needed}/{len(strategies)} → {result}")
    
    print("\n" + "=" * 70)
    print("FINAL RECOMMENDATION (70% threshold)")
    print("=" * 70)
    
    current_price = df['close'].iloc[-1]
    
    if consensus == "BUY":
        print(f"🟢 **BUY SIGNAL ACTIVATED!**")
        print(f"   Entry: ₹{current_price:.2f}")
        print(f"   Target: ₹{current_price * 1.02:.2f} (+2%)")
        print(f"   Stop Loss: ₹{current_price * 0.99:.2f} (-1%)")
        print(f"   {buy_votes}/10 strategies recommend buying!")
    elif consensus == "SELL":
        print(f"🔴 **SELL SIGNAL ACTIVATED!**")
        print(f"   Exit all positions at: ₹{current_price:.2f}")
        print(f"   {sell_votes}/10 strategies recommend selling!")
    else:
        print(f"⚪ **NO TRADE - HOLD POSITION**")
        print(f"   Current: ₹{current_price:.2f}")
        print(f"   Not enough consensus (need 7/10)")
    
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
