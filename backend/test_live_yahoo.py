"""
Test LIVE NIFTY prediction using Yahoo Finance data
Uses yfinance library to get real-time Nifty 50 data
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

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
    print("Data Source: Yahoo Finance (Real-time)")
    print("=" * 70)
    print()
    
    # Fetch Nifty 50 data from Yahoo Finance
    print("Step 1: Fetching NIFTY 50 data from Yahoo Finance...")
    print("Symbol: ^NSEI (Nifty 50 Index)")
    print("Period: Last 5 days")
    print("Interval: 5 minutes\n")
    
    try:
        # Download Nifty data
        ticker = yf.Ticker("^NSEI")
        
        # Get 5-minute data for last 5 days
        df = ticker.history(period="5d", interval="5m")
        
        if df.empty:
            print("❌ No data received from Yahoo Finance!")
            print("\nTrying 1-hour interval instead...")
            df = ticker.history(period="1mo", interval="1h")
        
        if df.empty:
            print("❌ Still no data!")
            return
        
        # Rename columns to match our format
        df = df.reset_index()
        df.columns = df.columns.str.lower()
        
        # Rename 'datetime' or 'date' to 'timestamp'
        if 'datetime' in df.columns:
            df.rename(columns={'datetime': 'timestamp'}, inplace=True)
        elif 'date' in df.columns:
            df.rename(columns={'date': 'timestamp'}, inplace=True)
        
        print(f"✅ Retrieved {len(df)} candles!")
        print("\nLatest 5 candles:")
        print(df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail(5))
        
        current_price = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2] if len(df) > 1 else current_price
        change = current_price - prev_close
        change_pct = (change / prev_close) * 100
        
        print(f"\n📊 Current NIFTY Price: ₹{current_price:.2f}")
        print(f"   Change: {change:+.2f} ({change_pct:+.2f}%)")
        print(f"   Open: ₹{df['open'].iloc[-1]:.2f}")
        print(f"   High: ₹{df['high'].iloc[-1]:.2f}")
        print(f"   Low: ₹{df['low'].iloc[-1]:.2f}")
        
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return
    
    # Initialize all 10 strategies
    print("\n" + "=" * 60)
    print("INITIALIZING 10 TRADING STRATEGIES")
    print("=" * 60)
    
    strategies = [
        MovingAverageStrategy(period=20),
        RSIStrategy(period=14, oversold=40, overbought=60),
        MACDStrategy(fast_period=5, slow_period=13, signal_period=1),
        BollingerBandsStrategy(period=20, std_dev=2),
        EMACrossoverStrategy(fast_period=9, slow_period=21),
        SupertrendStrategy(period=10, multiplier=3),
        VWAPStrategy(),
        StochasticStrategy(k_period=14, d_period=3, oversold=30, overbought=70),
        ADXStrategy(period=14, adx_threshold=25),
        VolumeStrategy(period=20, volume_threshold=1.5)
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
    
    if consensus == "BUY":
        entry = current_price
        target = current_price * 1.02
        stoploss = current_price * 0.99
        
        print(f"🟢 **BUY SIGNAL ACTIVATED!**")
        print(f"   Entry: ₹{entry:.2f}")
        print(f"   Target: ₹{target:.2f} (+2%)")
        print(f"   Stop Loss: ₹{stoploss:.2f} (-1%)")
        print(f"   Risk-Reward: 1:2")
        print(f"   {buy_votes}/10 strategies recommend buying!")
        
        # Option suggestion
        atm_strike = round(current_price / 50) * 50
        print(f"\n💡 Suggested Trade:")
        print(f"   Buy NIFTY {atm_strike} CE (Call Option)")
        print(f"   Quantity: 1 lot (50 qty)")
        print(f"   Hold Time: Max 30 minutes")
        
    elif consensus == "SELL":
        print(f"🔴 **SELL SIGNAL ACTIVATED!**")
        print(f"   Exit all positions at: ₹{current_price:.2f}")
        print(f"   {sell_votes}/10 strategies recommend selling!")
        print(f"\n💡 Action: Close all open positions or stay in cash")
        
    else:
        print(f"⚪ **NO TRADE - HOLD POSITION**")
        print(f"   Current: ₹{current_price:.2f}")
        print(f"   Not enough consensus (need 7/10)")
        print(f"\n💡 Action: Wait for clearer signal")
    
    print("\n" + "=" * 70)
    print(f"Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

if __name__ == "__main__":
    main()
