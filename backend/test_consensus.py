"""
Test multiple strategies together with consensus logic
"""
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
from utils.logger import signals_logger

def fetch_nifty_data(days=30):
    """Fetch Nifty historical data"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Fetch Nifty 50 data (5-minute interval for intraday)
    print(f"Fetching Nifty data from {start_date.date()} to {end_date.date()}...")
    ticker = yf.Ticker("^NSEI")  # Nifty 50 index
    df = ticker.history(start=start_date, end=end_date, interval="5m")
    
    if df.empty:
        print("No data found. Trying daily interval...")
        df = ticker.history(start=start_date, end=end_date, interval="1d")
    
    # Standardize column names to lowercase
    df.columns = [col.lower() for col in df.columns]
    df['timestamp'] = df.index
    
    print(f"Fetched {len(df)} candles")
    print(f"Date range: {df.index[0]} to {df.index[-1]}")
    print(f"Latest close: {df['close'].iloc[-1]:.2f}")
    
    return df

def test_consensus_trading():
    """Test multiple strategies with consensus logic"""
    print("\n" + "="*60)
    print("TESTING MULTI-STRATEGY CONSENSUS SYSTEM")
    print("="*60)
    
    # Fetch data
    df = fetch_nifty_data(days=30)
    
    if len(df) < 20:
        print("ERROR: Not enough data points for testing")
        return
    
    # Initialize only Moving Average strategy for comparison
    strategies = [
        MovingAverageStrategy(period=20),
        # RSIStrategy(period=14, oversold=40, overbought=60),
        # MACDStrategy(fast_period=5, slow_period=13, signal_period=1),
        # BollingerBandsStrategy(period=20, std_dev=2),
        # EMACrossoverStrategy(fast_period=9, slow_period=21),
        # SupertrendStrategy(period=10, multiplier=3),
        # VWAPStrategy(),
        # StochasticStrategy(k_period=14, d_period=3, oversold=30, overbought=70),
        # ADXStrategy(period=14, adx_threshold=25),
        # VolumeStrategy(period=20, volume_threshold=1.5)
    ]
    
    print(f"\nActive Strategies: {len(strategies)}")
    for s in strategies:
        print(f"  - {s.name}")
    
    # Consensus threshold (1 strategy = 100%)
    consensus_threshold = 1.0
    min_agrees = max(1, int(len(strategies) * consensus_threshold))
    print(f"\nConsensus Threshold: {consensus_threshold*100:.0f}% ({min_agrees}/{len(strategies)} strategies must agree)")
    print("(Testing single strategy performance)")
    
    # Simulate trading with consensus and scalping rules
    print(f"\nSimulating consensus trading on {len(df)} candles...")
    print("Scalping Rules:")
    print("  - Entry: Both strategies BUY")
    print("  - Exit: Any strategy SELL OR profit target OR stop loss OR time limit")
    print("  - Profit Target: +2%")
    print("  - Stop Loss: -1%")
    print("  - Max Hold Time: 30 minutes (6 candles)")
    
    trades = []
    position = None
    entry_price = None
    entry_time = None
    entry_signals = {}
    entry_candle_index = None
    
    # Start from candle 20 (after indicators have enough data)
    for i in range(20, len(df)):
        current_data = df.iloc[:i+1]
        current_price = df.iloc[i]['close']
        current_time = df.index[i]
        
        # Get signal from each strategy
        strategy_votes = {}
        for strategy in strategies:
            signal = strategy.calculate(current_data)
            strategy_votes[strategy.name] = signal
        
        # Count votes
        buy_votes = sum(1 for s in strategy_votes.values() if s == "BUY")
        sell_votes = sum(1 for s in strategy_votes.values() if s == "SELL")
        
        # Check if we have an open position
        if position == "LONG":
            # Calculate current P&L
            profit_pct = ((current_price - entry_price) / entry_price) * 100
            candles_held = i - entry_candle_index
            
            # Exit conditions for scalping
            exit_reason = None
            
            # 1. Profit target hit
            if profit_pct >= 2.0:
                exit_reason = "PROFIT_TARGET"
            
            # 2. Stop loss hit
            elif profit_pct <= -1.0:
                exit_reason = "STOP_LOSS"
            
            # 3. Time limit (30 minutes = 6 five-minute candles)
            elif candles_held >= 6:
                exit_reason = "TIME_LIMIT"
            
            # 4. Any strategy says SELL
            elif sell_votes >= 1:
                exit_reason = "SELL_SIGNAL"
            
            # 5. RSI returns to NEUTRAL (momentum fading)
            elif strategy_votes.get('RSI(14)') == 'NEUTRAL' and entry_signals.get('RSI(14)') == 'BUY':
                exit_reason = "RSI_NEUTRAL"
            
            # Exit if any condition met
            if exit_reason:
                exit_price = current_price
                exit_time = current_time
                exit_signals = strategy_votes.copy()
                
                # Calculate P&L
                points_profit = exit_price - entry_price
                money_profit = points_profit * 50  # 1 lot = 50 qty
                profit_percent = (points_profit / entry_price) * 100
                
                trades.append({
                    'entry_time': entry_time,
                    'exit_time': exit_time,
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'points': points_profit,
                    'profit': money_profit,
                    'profit_pct': profit_percent,
                    'entry_signals': entry_signals,
                    'exit_signals': exit_signals,
                    'exit_reason': exit_reason,
                    'candles_held': candles_held
                })
                
                # Reset position
                position = None
                entry_price = None
                entry_time = None
                entry_candle_index = None
        
        # Entry logic - consensus BUY
        else:
            if buy_votes >= min_agrees:
                # Enter long position
                position = "LONG"
                entry_price = current_price
                entry_time = current_time
                entry_signals = strategy_votes.copy()
                entry_candle_index = i
    
    # Results
    print("\n" + "="*60)
    print("CONSENSUS BACKTEST RESULTS")
    print("="*60)
    print(f"Total Candles Analyzed: {len(df) - 20}")
    print(f"Total Trades Executed: {len(trades)}")
    
    if trades:
        winning_trades = [t for t in trades if t['profit'] > 0]
        losing_trades = [t for t in trades if t['profit'] < 0]
        total_profit = sum(t['profit'] for t in trades)
        
        print(f"Winning Trades: {len(winning_trades)}")
        print(f"Losing Trades: {len(losing_trades)}")
        print(f"Win Rate: {(len(winning_trades)/len(trades)*100):.1f}%")
        print(f"\nTotal P&L: ₹{total_profit:,.2f}")
        print(f"Average Profit per Trade: ₹{total_profit/len(trades):,.2f}")
        
        # Show first 10 trades with strategy votes
        print("\n" + "-"*60)
        print("FIRST 10 TRADES (WITH STRATEGY VOTES)")
        print("-"*60)
        for i, trade in enumerate(trades[:10]):
            hold_minutes = trade['candles_held'] * 5
            print(f"\nTrade #{i+1}:")
            print(f"  Entry: {trade['entry_time'].strftime('%m-%d %H:%M')} @ ₹{trade['entry_price']:.2f}")
            print(f"  Entry Votes: {trade['entry_signals']}")
            print(f"  Exit:  {trade['exit_time'].strftime('%m-%d %H:%M')} @ ₹{trade['exit_price']:.2f}")
            print(f"  Exit Votes: {trade['exit_signals']}")
            print(f"  Exit Reason: {trade['exit_reason']}")
            print(f"  Hold Time: {hold_minutes} minutes ({trade['candles_held']} candles)")
            print(f"  P&L: ₹{trade['profit']:+,.0f} ({trade['profit_pct']:+.2f}%) {'✓' if trade['profit'] > 0 else '✗'}")
        
        # Best and worst
        best_trade = max(trades, key=lambda x: x['profit'])
        worst_trade = min(trades, key=lambda x: x['profit'])
        
        print("\n" + "-"*60)
        print("BEST TRADE")
        print("-"*60)
        print(f"Entry: {best_trade['entry_time']} @ ₹{best_trade['entry_price']:.2f}")
        print(f"Entry Votes: {best_trade['entry_signals']}")
        print(f"Exit:  {best_trade['exit_time']} @ ₹{best_trade['exit_price']:.2f}")
        print(f"Profit: ₹{best_trade['profit']:,.2f} ({best_trade['profit_pct']:+.2f}%)")
        
        print("\n" + "-"*60)
        print("WORST TRADE")
        print("-"*60)
        print(f"Entry: {worst_trade['entry_time']} @ ₹{worst_trade['entry_price']:.2f}")
        print(f"Entry Votes: {worst_trade['entry_signals']}")
        print(f"Exit:  {worst_trade['exit_time']} @ ₹{worst_trade['exit_price']:.2f}")
        print(f"Loss: ₹{worst_trade['profit']:,.2f} ({worst_trade['profit_pct']:+.2f}%)")
    else:
        print("\nNo trades executed with current consensus settings.")
    
    # Show current signals
    print("\n" + "-"*60)
    print("CURRENT SIGNALS (LATEST CANDLE)")
    print("-"*60)
    for strategy in strategies:
        signal = strategy.calculate(df)
        result = strategy.get_signal()
        print(f"\n{strategy.name}:")
        print(f"  Signal: {result['signal']}")
        print(f"  Metadata: {result['metadata']}")
    
    print("\n" + "="*60)
    print("TEST COMPLETED")
    print("="*60)

if __name__ == "__main__":
    test_consensus_trading()
