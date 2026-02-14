"""
Test strategies with historical data from yfinance
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from strategies.strategy_1_moving_average import MovingAverageStrategy
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

def test_moving_average_strategy():
    """Test Moving Average strategy with real data"""
    print("\n" + "="*60)
    print("TESTING MOVING AVERAGE STRATEGY WITH HISTORICAL DATA")
    print("="*60 + "\n")
    
    # Fetch data
    df = fetch_nifty_data(days=30)
    
    if len(df) < 20:
        print("ERROR: Not enough data points for testing")
        return
    
    # Initialize strategy
    strategy = MovingAverageStrategy(period=20)
    
    # Simulate candle-by-candle trading with actual trades
    print(f"\nSimulating candle-by-candle trading on {len(df)} candles...")
    print("(Starting from candle 20 after MA warmup)")
    
    trades = []
    position = None  # None = no position, "LONG" = holding position
    entry_price = None
    entry_time = None
    
    # Start from candle 20 (after MA has enough data)
    for i in range(20, len(df)):
        # Get data up to current candle (simulating real-time)
        current_data = df.iloc[:i+1]
        current_price = df.iloc[i]['close']
        current_time = df.index[i]
        
        # Calculate strategy signal
        signal = strategy.calculate(current_data)
        
        # Trading logic
        if signal == "BUY" and position is None:
            # Enter long position
            position = "LONG"
            entry_price = current_price
            entry_time = current_time
            
        elif signal == "SELL" and position == "LONG":
            # Exit position and calculate profit
            exit_price = current_price
            exit_time = current_time
            
            # Calculate P&L (for options, 1 point = ₹1 per lot, assuming 1 lot = 50 qty)
            points_profit = exit_price - entry_price
            money_profit = points_profit * 50  # 1 lot = 50 qty for Nifty options
            profit_percent = (points_profit / entry_price) * 100
            
            trades.append({
                'entry_time': entry_time,
                'exit_time': exit_time,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'points': points_profit,
                'profit': money_profit,
                'profit_pct': profit_percent
            })
            
            # Reset position
            position = None
            entry_price = None
            entry_time = None
    
    # Summary
    print("\n" + "="*60)
    print("BACKTEST RESULTS - ACTUAL TRADES")
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
        
        # Show first 10 trades
        print("\n" + "-"*60)
        print("FIRST 10 TRADES")
        print("-"*60)
        print(f"{'#':<4} {'Entry':<20} {'Exit':<20} {'Points':<10} {'P&L':<15}")
        print("-"*60)
        for i, trade in enumerate(trades[:10]):
            entry_str = trade['entry_time'].strftime('%m-%d %H:%M')
            exit_str = trade['exit_time'].strftime('%m-%d %H:%M')
            points_str = f"{trade['points']:+.2f}"
            profit_str = f"₹{trade['profit']:+,.0f}"
            profit_color = "✓" if trade['profit'] > 0 else "✗"
            print(f"{i+1:<4} {entry_str:<20} {exit_str:<20} {points_str:<10} {profit_str:<15} {profit_color}")
        
        # Show best and worst trades
        best_trade = max(trades, key=lambda x: x['profit'])
        worst_trade = min(trades, key=lambda x: x['profit'])
        
        print("\n" + "-"*60)
        print("BEST TRADE")
        print("-"*60)
        print(f"Entry: {best_trade['entry_time']} @ ₹{best_trade['entry_price']:.2f}")
        print(f"Exit:  {best_trade['exit_time']} @ ₹{best_trade['exit_price']:.2f}")
        print(f"Profit: ₹{best_trade['profit']:,.2f} ({best_trade['profit_pct']:+.2f}%)")
        
        print("\n" + "-"*60)
        print("WORST TRADE")
        print("-"*60)
        print(f"Entry: {worst_trade['entry_time']} @ ₹{worst_trade['entry_price']:.2f}")
        print(f"Exit:  {worst_trade['exit_time']} @ ₹{worst_trade['exit_price']:.2f}")
        print(f"Loss: ₹{worst_trade['profit']:,.2f} ({worst_trade['profit_pct']:+.2f}%)")
    
    # Current signal
    result = strategy.get_signal()
    print("\n" + "-"*60)
    print("CURRENT SIGNAL (LATEST CANDLE)")
    print("-"*60)
    print(f"Signal: {result['signal']}")
    print(f"Price: {result['price']:.2f}")
    print(f"MA(20): {result['metadata']['ma_value']:.2f}")
    print(f"Distance: {result['metadata']['distance_from_ma']:.2f} ({result['metadata']['distance_percent']:.2f}%)")
    
    print("\n" + "="*60)
    print("TEST COMPLETED")
    print("="*60)

if __name__ == "__main__":
    test_moving_average_strategy()
