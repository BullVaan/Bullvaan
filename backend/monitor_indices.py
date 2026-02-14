"""
LIVE INDIAN INDICES CONSENSUS MONITOR
Monitor multiple Indian indices with 10-strategy consensus
Supports: Nifty 50, Bank Nifty, Sensex, Nifty IT, Nifty Pharma, etc.
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
import yfinance as yf
import pandas as pd
from datetime import datetime
import time
import os

# Available Indian Indices
INDICES = {
    '1': {'name': 'Nifty 50', 'symbol': '^NSEI', 'lot_size': 50},
    '2': {'name': 'Bank Nifty', 'symbol': '^NSEBANK', 'lot_size': 25},
    '3': {'name': 'Sensex (BSE)', 'symbol': '^BSESN', 'lot_size': 10},
    '4': {'name': 'Nifty IT', 'symbol': '^CNXIT', 'lot_size': 50},
    '5': {'name': 'Nifty Pharma', 'symbol': '^CNXPHARMA', 'lot_size': 40},
    '6': {'name': 'Nifty Midcap', 'symbol': '^NSEMDCP50', 'lot_size': 75},
    '7': {'name': 'Nifty Auto', 'symbol': '^CNXAUTO', 'lot_size': 50},
    '8': {'name': 'Nifty Financial Services', 'symbol': '^CNXFINANCE', 'lot_size': 40},
    '9': {'name': 'Nifty FMCG', 'symbol': '^CNXFMCG', 'lot_size': 50},
    '10': {'name': 'Nifty Metal', 'symbol': '^CNXMETAL', 'lot_size': 50},
    '11': {'name': 'Nifty Realty', 'symbol': '^CNXREALTY', 'lot_size': 50},
    '12': {'name': 'Nifty Energy', 'symbol': '^CNXENERGY', 'lot_size': 50},
}

# Initialize strategies once (all parameters verified from strategy files)
STRATEGIES = [
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

# Track signal history
signal_history = []
last_consensus = None

def clear_screen():
    """Clear terminal screen"""
    os.system('clear' if os.name != 'nt' else 'cls')

def select_index():
    """Display menu and let user select index"""
    clear_screen()
    print("=" * 80)
    print(" " * 20 + "📈 SELECT INDEX TO MONITOR 📈")
    print("=" * 80)
    print()
    
    for key, info in INDICES.items():
        print(f"  {key:2s}. {info['name']:30s} ({info['symbol']:15s}) - Lot Size: {info['lot_size']}")
    
    print()
    print("=" * 80)
    
    while True:
        choice = input("\nEnter your choice (1-12): ").strip()
        if choice in INDICES:
            return INDICES[choice]
        print("❌ Invalid choice. Please enter a number between 1 and 12.")

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

def display_dashboard(result, current_price, price_change, timestamp, index_info):
    """Display monitoring dashboard"""
    clear_screen()
    
    print("=" * 80)
    print(" " * 15 + f"🚀 LIVE {index_info['name'].upper()} CONSENSUS MONITOR 🚀")
    print("=" * 80)
    print(f"Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S IST')}")
    print(f"Index: {index_info['name']} ({index_info['symbol']})")
    print(f"Price: ₹{current_price:.2f} ({price_change:+.2f} / {(price_change/current_price*100):+.2f}%)")
    print(f"Lot Size: {index_info['lot_size']} (₹{current_price * index_info['lot_size']:.0f} per lot)")
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
        print(f"   Position Size: 1 lot = ₹{current_price * index_info['lot_size']:.0f}")
        print(f"   Profit Target: ₹{current_price * index_info['lot_size'] * 0.02:.0f}")
        print(f"   Max Loss: ₹{current_price * index_info['lot_size'] * 0.01:.0f}")
    elif consensus == "SELL":
        print("❌ STRONG SELL SIGNAL!")
        print(f"   Exit all positions at ₹{current_price:.2f}")
        print(f"   Per lot exit: ₹{current_price * index_info['lot_size']:.0f}")
    else:
        print("⏸️  NO TRADE - Waiting for consensus")
        print(f"   Current: ₹{current_price:.2f}")
        need = 7 - max(result['buy_votes'], result['sell_votes'])
        print(f"   Need {need} more votes for signal")
    
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
    
    # Let user select index
    index_info = select_index()
    
    print("\n" + "=" * 80)
    print(f" " * 10 + f"🚀 STARTING {index_info['name'].upper()} CONSENSUS MONITOR 🚀")
    print("=" * 80)
    print(f"\nIndex: {index_info['name']}")
    print(f"Symbol: {index_info['symbol']}")
    print(f"Lot Size: {index_info['lot_size']}")
    print("\nFetching initial data...")
    
    check_count = 0
    consecutive_errors = 0
    max_consecutive_errors = 3
    
    try:
        while True:
            check_count += 1
            
            # Fetch live data from Yahoo Finance with error handling
            try:
                ticker = yf.Ticker(index_info['symbol'])
                df = ticker.history(period="5d", interval="5m")
                consecutive_errors = 0  # Reset error counter on success
            except Exception as e:
                consecutive_errors += 1
                print(f"\n⚠️  Error fetching data (attempt {consecutive_errors}/{max_consecutive_errors}): {str(e)[:100]}")
                
                if consecutive_errors >= max_consecutive_errors:
                    print("\n❌ Too many consecutive errors. Stopping monitor.")
                    print("Possible causes:")
                    print("  - Yahoo Finance rate limiting")
                    print("  - Network connection issues")
                    print("  - Markets closed")
                    break
                
                print("Retrying in 60 seconds...")
                time.sleep(60)
                continue
            
            if df.empty:
                consecutive_errors += 1
                print(f"\n⚠️  No data received (attempt {consecutive_errors}/{max_consecutive_errors})")
                
                if consecutive_errors >= max_consecutive_errors:
                    print("\n❌ Too many consecutive errors. Stopping monitor.")
                    break
                
                print("Retrying in 60 seconds...")
                time.sleep(60)
                continue
            
            # Prepare data
            df = df.reset_index()
            
            # Yahoo Finance may return different columns, handle properly
            df = df.rename(columns={
                'Date': 'timestamp',
                'Datetime': 'timestamp',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            # Keep only required columns
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
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
            display_dashboard(result, current_price, price_change, timestamp, index_info)
            
            # Alert on consensus change
            if last_consensus != result['consensus']:
                if result['consensus'] in ["BUY", "SELL"]:
                    print(f"\n🔔 ALERT: Consensus changed to {result['consensus']}!")
                    print("\a")  # System beep
                last_consensus = result['consensus']
            
            # Wait 5 minutes (300 seconds)
            time.sleep(300)
            
    except KeyboardInterrupt:
        print("\n\n" + "=" * 80)
        print(" " * 20 + "📊 MONITORING STOPPED")
        print("=" * 80)
        print(f"Index: {index_info['name']}")
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
            
            if buy_count > 0:
                print(f"\n💡 Had {buy_count} BUY opportunities during monitoring")
        
        print("\n✅ Thank you for using Index Consensus Monitor!")
        print("=" * 80)

if __name__ == "__main__":
    main()
