"""
LIVE NIFTY CONSENSUS MONITOR
Continuously monitors Nifty 50 and alerts when 70% consensus is reached
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

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
from datetime import datetime
import time
import os

from utils.yahoo_finance import fetch_history, standardize_ohlcv

# Initialize strategies once
STRATEGIES = [
    MovingAverageStrategy(period=20),
    RSIStrategy(period=14, oversold_threshold=40, overbought_threshold=60),
    MACDStrategy(fast_period=5, slow_period=13, signal_period=1),
    BollingerBandsStrategy(period=20, num_std=2),
    EMACrossoverStrategy(short_period=9, long_period=21),
    SupertrendStrategy(period=10, multiplier=3),
    VWAPStrategy(),
    StochasticStrategy(k_period=14, d_period=3),
    ADXStrategy(period=14, trend_threshold=25),
    VolumeStrategy(period=20)
]

# Track signal history
signal_history = []
last_consensus = None

def clear_screen():
    """Clear terminal screen"""
    os.system('clear' if os.name != 'nt' else 'cls')

def get_consensus(df, strategies, threshold=0.7):
    """Calculate consensus from strategies"""
    signals = []
    strategy_details = []
    
    for strategy in strategies:
        signal = strategy.calculate(df)
        signals.append(signal)
        strategy_details.append({
            'name': strategy.name,
            'signal': signal
        })
    
    buy_votes = signals.count("BUY")
    sell_votes = signals.count("SELL")
    neutral_votes = signals.count("NEUTRAL")
    total = len(signals)
    
    buy_pct = buy_votes / total
    sell_pct = sell_votes / total
    
    if buy_pct >= threshold:
        consensus = "BUY"
    elif sell_pct >= threshold:
        consensus = "SELL"
    else:
        consensus = "NEUTRAL"
    
    return {
        'consensus': consensus,
        'buy_votes': buy_votes,
        'sell_votes': sell_votes,
        'neutral_votes': neutral_votes,
        'total_votes': total,
        'buy_percentage': buy_pct * 100,
        'sell_percentage': sell_pct * 100,
        'strategies': strategy_details
    }

def display_dashboard(result, current_price, price_change, timestamp):
    """Display monitoring dashboard"""
    clear_screen()
    
    print("=" * 80)
    print(" " * 20 + "🚀 LIVE NIFTY CONSENSUS MONITOR 🚀")
    print("=" * 80)
    print(f"Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S IST')}")
    print(f"Nifty Price: ₹{current_price:.2f} ({price_change:+.2f} / {(price_change/current_price*100):+.2f}%)")
    print("=" * 80)
    
    # Consensus status
    consensus = result['consensus']
    if consensus == "BUY":
        icon = "🟢"
        color = "BUY"
    elif consensus == "SELL":
        icon = "🔴"
        color = "SELL"
    else:
        icon = "⚪"
        color = "NEUTRAL"
    
    print(f"\n{icon} CONSENSUS: {color}")
    print(f"   BUY:     {result['buy_votes']}/10 ({result['buy_percentage']:.0f}%)")
    print(f"   SELL:    {result['sell_votes']}/10 ({result['sell_percentage']:.0f}%)")
    print(f"   NEUTRAL: {result['neutral_votes']}/10")
    print(f"   Threshold: 7/10 (70%) required")
    
    # Individual strategy votes
    print("\n" + "-" * 80)
    print("INDIVIDUAL STRATEGY SIGNALS:")
    print("-" * 80)
    
    for strat in result['strategies']:
        signal = strat['signal']
        if signal == "BUY":
            icon = "🟢"
        elif signal == "SELL":
            icon = "🔴"
        else:
            icon = "⚪"
        print(f"  {icon} {strat['name']:20s} → {signal}")
    
    # Trading recommendation
    print("\n" + "=" * 80)
    if consensus == "BUY":
        print("✅ STRONG BUY SIGNAL!")
        print(f"   Entry: ₹{current_price:.2f}")
        print(f"   Target: ₹{current_price * 1.02:.2f} (+2%)")
        print(f"   Stop Loss: ₹{current_price * 0.99:.2f} (-1%)")
    elif consensus == "SELL":
        print("❌ STRONG SELL SIGNAL!")
        print(f"   Exit all positions at ₹{current_price:.2f}")
    else:
        print("⏸️  NO TRADE - Waiting for consensus")
        print(f"   Current: ₹{current_price:.2f}")
    
    # Recent history
    if signal_history:
        print("\n" + "-" * 80)
        print("RECENT SIGNAL HISTORY (Last 10):")
        print("-" * 80)
        for entry in signal_history[-10:]:
            time_str = entry['time'].strftime('%H:%M:%S')
            price = entry['price']
            cons = entry['consensus']
            buy = entry['buy_votes']
            sell = entry['sell_votes']
            
            if cons == "BUY":
                icon = "🟢"
            elif cons == "SELL":
                icon = "🔴"
            else:
                icon = "⚪"
            
            print(f"  {time_str} | ₹{price:8.2f} | {icon} {cons:7s} | B:{buy} S:{sell}")
    
    print("\n" + "=" * 80)
    print("Press Ctrl+C to stop monitoring")
    print("Next update in 5 minutes...")
    print("=" * 80)

def main():
    global signal_history, last_consensus
    
    print("=" * 80)
    print(" " * 15 + "🚀 STARTING NIFTY CONSENSUS MONITOR 🚀")
    print("=" * 80)
    print("\nFetching initial data...")
    
    check_count = 0
    
    try:
        while True:
            check_count += 1
            
            # Fetch live data from Yahoo Finance
            fetched = fetch_history("^NSEI")
            df = fetched.df
            
            if df.empty:
                print("\n⚠️  Could not fetch data, retrying in 30 seconds...")
                time.sleep(30)
                continue
            
            # Prepare data
            df = standardize_ohlcv(df)
            
            current_price = df['close'].iloc[-1]
            prev_price = df['close'].iloc[-2] if len(df) > 1 else current_price
            price_change = current_price - prev_price
            
            # Get consensus
            result = get_consensus(df, STRATEGIES, threshold=0.7)
            
            # Record in history
            timestamp = datetime.now()
            signal_history.append({
                'time': timestamp,
                'price': current_price,
                'consensus': result['consensus'],
                'buy_votes': result['buy_votes'],
                'sell_votes': result['sell_votes']
            })
            
            # Display dashboard
            display_dashboard(result, current_price, price_change, timestamp)
            
            # Alert on consensus change
            if last_consensus != result['consensus']:
                if result['consensus'] in ["BUY", "SELL"]:
                    print(f"\n🔔 ALERT: Consensus changed to {result['consensus']}!")
                    print("\a")  # System beep
                last_consensus = result['consensus']
            
            # Wait 5 minutes (300 seconds)
            # During market hours, check every 5 minutes
            # Can adjust frequency as needed
            time.sleep(300)
            
    except KeyboardInterrupt:
        print("\n\n" + "=" * 80)
        print(" " * 20 + "📊 MONITORING STOPPED")
        print("=" * 80)
        print(f"Total checks: {check_count}")
        print(f"Signal history saved: {len(signal_history)} records")
        
        if signal_history:
            print("\nFinal Summary:")
            buy_count = sum(1 for s in signal_history if s['consensus'] == 'BUY')
            sell_count = sum(1 for s in signal_history if s['consensus'] == 'SELL')
            neutral_count = sum(1 for s in signal_history if s['consensus'] == 'NEUTRAL')
            
            print(f"  BUY signals: {buy_count}")
            print(f"  SELL signals: {sell_count}")
            print(f"  NEUTRAL: {neutral_count}")
        
        print("\n✅ Thank you for using Nifty Consensus Monitor!")
        print("=" * 80)

if __name__ == "__main__":
    main()
