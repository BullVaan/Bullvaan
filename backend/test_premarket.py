"""
Premarket Signals Testing Script
=================================
Run this to verify the premarket signal system is working correctly.

Usage:
    python test_premarket.py        # Run all tests
    python test_premarket.py --api   # Test API endpoints
    python test_premarket.py --engine # Test signal engine
"""

import asyncio
import sys
import json
from datetime import datetime, timezone
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_premarket")

def test_imports():
    """Test that all required modules can be imported"""
    print("\n" + "="*60)
    print("TEST 1: Checking Imports")
    print("="*60)
    
    try:
        from engine.premarket_signals import PremarketSignalEngine
        print("✓ PremarketSignalEngine imported")
    except Exception as e:
        print(f"✗ Failed to import PremarketSignalEngine: {e}")
        return False
    
    try:
        from engine.premarket_alerts import PremarketAlertManager, AlertSeverity
        print("✓ PremarketAlertManager imported")
    except Exception as e:
        print(f"✗ Failed to import PremarketAlertManager: {e}")
        return False
    
    try:
        from utils.nifty50_stocks import get_nifty50_symbols, NIFTY50_STOCKS
        print("✓ NIFTY50 stocks loaded")
    except Exception as e:
        print(f"✗ Failed to load NIFTY50 stocks: {e}")
        return False
    
    return True


def test_nifty50_list():
    """Test NIFTY50 stock list"""
    print("\n" + "="*60)
    print("TEST 2: NIFTY50 Stock List")
    print("="*60)
    
    try:
        from utils.nifty50_stocks import get_nifty50_symbols, NIFTY50_STOCKS
        
        symbols = get_nifty50_symbols("nse")
        print(f"✓ Loaded {len(symbols)} NIFTY50 stocks")
        
        if len(symbols) != 50:
            print(f"⚠ WARNING: Expected 50 stocks, got {len(symbols)}")
        
        # Show first 10 stocks
        print(f"\nFirst 10 stocks: {symbols[:10]}")
        
        return True
    except Exception as e:
        print(f"✗ Error loading NIFTY50 list: {e}")
        return False


def test_alert_manager():
    """Test alert manager functionality"""
    print("\n" + "="*60)
    print("TEST 3: Alert Manager")
    print("="*60)
    
    try:
        from engine.premarket_alerts import PremarketAlertManager, AlertType, AlertSeverity
        
        # Create manager
        alert_mgr = PremarketAlertManager()
        print("✓ Alert manager initialized")
        
        # Create sample alert
        sample_signals = [
            {
                'symbol': 'INFY',
                'signal': 'BUY',
                'strength': 'STRONG',
                'gap_percent': 2.5,
                'reason': 'Strong gap up with high volume',
                'yesterday_volume': 500000,
                'prev_volume_avg': 400000
            },
            {
                'symbol': 'TCS',
                'signal': 'SELL',
                'strength': 'MEDIUM',
                'gap_percent': -1.5,
                'reason': 'Gap down with reversing candle',
                'yesterday_volume': 300000,
                'prev_volume_avg': 250000
            }
        ]
        
        alert_mgr.process_signals(sample_signals)
        print(f"✓ Processed {len(sample_signals)} sample signals")
        
        # Check alerts
        active_alerts = alert_mgr.get_active_alerts()
        print(f"✓ Generated {len(active_alerts)} alerts")
        
        if len(active_alerts) > 0:
            print(f"\nSample alert:")
            print(json.dumps(active_alerts[0], indent=2))
        
        # Check summary
        summary = alert_mgr.get_summary()
        print(f"\nAlert summary: {summary}")
        
        return True
    except Exception as e:
        print(f"✗ Error testing alert manager: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_signal_engine():
    """Test signal engine (without Zerodha connection)"""
    print("\n" + "="*60)
    print("TEST 4: Signal Engine")
    print("="*60)
    
    try:
        from engine.premarket_signals import PremarketSignalEngine
        
        # Create engine without kite (will use None for kite)
        engine = PremarketSignalEngine(kite=None)
        print("✓ Signal engine initialized")
        
        # Try to get a signal (will fail due to no data, but tests the structure)
        signal = engine.get_premarket_signals("INFY")
        print(f"✓ Signal generation attempted for INFY")
        
        print(f"\nSignal structure:")
        print(json.dumps(signal, indent=2, default=str))
        
        # Check required fields
        required_fields = ['symbol', 'signal', 'strength', 'gap_percent', 'reason']
        missing_fields = [f for f in required_fields if f not in signal]
        
        if missing_fields:
            print(f"⚠ WARNING: Missing fields: {missing_fields}")
        else:
            print(f"✓ All required fields present")
        
        return True
    except Exception as e:
        print(f"✗ Error testing signal engine: {e}")
        import traceback
        traceback.print_exc()
        return False


def print_api_endpoints():
    """Print available API endpoints"""
    print("\n" + "="*60)
    print("AVAILABLE API ENDPOINTS")
    print("="*60)
    
    endpoints = {
        "Premarket Signals": [
            "GET /premarket/signals?symbol=INFY",
            "GET /premarket/signals/batch?symbols=INFY,TCS,RELIANCE",
            "GET /premarket/stocks"
        ],
        "Alerts": [
            "GET /premarket/alerts",
            "GET /premarket/alerts/critical",
            "POST /premarket/alerts/acknowledge",
            "DELETE /premarket/alerts"
        ],
        "Testing/Debug": [
            "GET /debug/premarket-test?symbol=INFY",
            "GET /debug/premarket-batch-test?symbols=INFY,TCS",
            "GET /debug/nifty50-list",
            "GET /debug/premarket-health"
        ]
    }
    
    for category, endpoint_list in endpoints.items():
        print(f"\n{category}:")
        for endpoint in endpoint_list:
            print(f"  - {endpoint}")


def print_signal_explanation():
    """Print explanation of signal generation"""
    print("\n" + "="*60)
    print("SIGNAL GENERATION LOGIC")
    print("="*60)
    
    logic = """
SIGNAL TYPES:
  - BUY:     Uptrend expected, consider CALL options
  - SELL:    Downtrend expected, consider PUT options  
  - NEUTRAL: No clear setup, WATCH mode

SIGNAL STRENGTH:
  - STRONG:  High confidence, 2+ factors confirmed
  - MEDIUM:  Good setup, 1-2 factors confirmed
  - WEAK:    Insufficient pattern, low confidence

KEY FACTORS:
  1. Gap Analysis
     - Gap > 1.5% + High Volume = Strong signal
     - Gap < -1.5% + High Volume = Strong sell signal
  
  2. Volume Patterns
     - Volume > 1.3x average = High conviction
     - Combined with gap for better accuracy
  
  3. Price Action
     - Bullish candle (close > open) + strong body
     - Bearish candle (close < open) + strong body
  
  4. Support/Resistance
     - Bounce from 20-day support = reversal signal
     - Breakout from 20-day resistance = momentum signal

EXAMPLES:
  
  ✓ STRONG BUY:
    - Gap up 2.5%
    - Volume 1.5x average
    - Bullish close
    - Action: Buy CALL options at market open
  
  ✓ MEDIUM SELL:
    - Gap down 1.2%
    - Bearish candle
    - Action: Short or buy PUT, watch support
  
  ✓ NEUTRAL:
    - Gap < 0.5%
    - Action: Wait for confirmation from price action
"""
    
    print(logic)


def run_all_tests():
    """Run all tests"""
    print("\n" + "█"*60)
    print("█ BULLVAAN PREMARKET SIGNALS - TEST SUITE")
    print("█"*60)
    
    results = {
        "Imports": test_imports(),
        "NIFTY50 List": test_nifty50_list(),
        "Alert Manager": test_alert_manager(),
        "Signal Engine": test_signal_engine()
    }
    
    # Print results
    print("\n" + "="*60)
    print("TEST RESULTS")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:25} {status}")
    
    print(f"\nPassed: {passed}/{total}")
    
    # Print available endpoints
    print_api_endpoints()
    
    # Print signal explanation
    print_signal_explanation()
    
    print("\n" + "="*60)
    print("NEXT STEPS:")
    print("="*60)
    print("""
1. Start the backend server:
   cd backend
   python -m uvicorn api.server:app --reload
   
2. Test the debug endpoints:
   curl http://localhost:8000/debug/nifty50-list
   curl http://localhost:8000/debug/premarket-health
   curl http://localhost:8000/debug/premarket-test?symbol=INFY
   
3. Get premarket signals for all NIFTY50 stocks:
   curl http://localhost:8000/premarket/stocks
   
4. Monitor alerts in real-time:
   curl http://localhost:8000/premarket/alerts

5. Check frontend integration:
   cd frontend
   npm start
   Navigate to Swing Trade page
""")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
