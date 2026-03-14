"""
NIFTY50 Stock Symbols and Mapping
Maps between different symbol formats: Yahoo, Zerodha, NSE
"""

# NIFTY50 stocks with multiple symbol formats
NIFTY50_STOCKS = [
    {"name": "ADANIPORTS", "nse": "ADANIPORTS", "yahoo": "ADANIPORTS.NS", "zerodha": "NSE:ADANIPORTS"},
    {"name": "ASIANPAINT", "nse": "ASIANPAINT", "yahoo": "ASIANPAINT.NS", "zerodha": "NSE:ASIANPAINT"},
    {"name": "AXISBANK", "nse": "AXISBANK", "yahoo": "AXISBANK.NS", "zerodha": "NSE:AXISBANK"},
    {"name": "BAJAJ-AUTO", "nse": "BAJAJ-AUTO", "yahoo": "BAJAJ-AUTO.NS", "zerodha": "NSE:BAJAJ-AUTO"},
    {"name": "BAJAJFINSV", "nse": "BAJAJFINSV", "yahoo": "BAJAJFINSV.NS", "zerodha": "NSE:BAJAJFINSV"},
    {"name": "BAJAJHLDNG", "nse": "BAJAJHLDNG", "yahoo": "BAJAJHLDNG.NS", "zerodha": "NSE:BAJAJHLDNG"},
    {"name": "BHARATIARTL", "nse": "BHARATIARTL", "yahoo": "BHARATIARTL.NS", "zerodha": "NSE:BHARATIARTL"},
    {"name": "BHARATIFIN", "nse": "BHARATIFIN", "yahoo": "BHARATIFIN.NS", "zerodha": "NSE:BHARATIFIN"},
    {"name": "BIOCON", "nse": "BIOCON", "yahoo": "BIOCON.NS", "zerodha": "NSE:BIOCON"},
    {"name": "BOSCHIND", "nse": "BOSCHIND", "yahoo": "BOSCHIND.NS", "zerodha": "NSE:BOSCHIND"},
    {"name": "BPCL", "nse": "BPCL", "yahoo": "BPCL.NS", "zerodha": "NSE:BPCL"},
    {"name": "BRITANNIA", "nse": "BRITANNIA", "yahoo": "BRITANNIA.NS", "zerodha": "NSE:BRITANNIA"},
    {"name": "CIPLA", "nse": "CIPLA", "yahoo": "CIPLA.NS", "zerodha": "NSE:CIPLA"},
    {"name": "COALINDIA", "nse": "COALINDIA", "yahoo": "COALINDIA.NS", "zerodha": "NSE:COALINDIA"},
    {"name": "COLPAL", "nse": "COLPAL", "yahoo": "COLPAL.NS", "zerodha": "NSE:COLPAL"},
    {"name": "DIVISLAB", "nse": "DIVISLAB", "yahoo": "DIVISLAB.NS", "zerodha": "NSE:DIVISLAB"},
    {"name": "DRREDDY", "nse": "DRREDDY", "yahoo": "DRREDDY.NS", "zerodha": "NSE:DRREDDY"},
    {"name": "EICHERMOT", "nse": "EICHERMOT", "yahoo": "EICHERMOT.NS", "zerodha": "NSE:EICHERMOT"},
    {"name": "GAIL", "nse": "GAIL", "yahoo": "GAIL.NS", "zerodha": "NSE:GAIL"},
    {"name": "GICRE", "nse": "GICRE", "yahoo": "GICRE.NS", "zerodha": "NSE:GICRE"},
    {"name": "GRASIM", "nse": "GRASIM", "yahoo": "GRASIM.NS", "zerodha": "NSE:GRASIM"},
    {"name": "HCLTECH", "nse": "HCLTECH", "yahoo": "HCLTECH.NS", "zerodha": "NSE:HCLTECH"},
    {"name": "HDFC", "nse": "HDFC", "yahoo": "HDFC.NS", "zerodha": "NSE:HDFC"},
    {"name": "HDFCBANK", "nse": "HDFCBANK", "yahoo": "HDFCBANK.NS", "zerodha": "NSE:HDFCBANK"},
    {"name": "HDFCLIFE", "nse": "HDFCLIFE", "yahoo": "HDFCLIFE.NS", "zerodha": "NSE:HDFCLIFE"},
    {"name": "HEROMOTOCO", "nse": "HEROMOTOCO", "yahoo": "HEROMOTOCO.NS", "zerodha": "NSE:HEROMOTOCO"},
    {"name": "HINDALCO", "nse": "HINDALCO", "yahoo": "HINDALCO.NS", "zerodha": "NSE:HINDALCO"},
    {"name": "HINDPETRO", "nse": "HINDPETRO", "yahoo": "HINDPETRO.NS", "zerodha": "NSE:HINDPETRO"},
    {"name": "HINDUNILVR", "nse": "HINDUNILVR", "yahoo": "HINDUNILVR.NS", "zerodha": "NSE:HINDUNILVR"},
    {"name": "HONAUT", "nse": "HONAUT", "yahoo": "HONAUT.NS", "zerodha": "NSE:HONAUT"},
    {"name": "HUL", "nse": "HUL", "yahoo": "HUL.NS", "zerodha": "NSE:HUL"},
    {"name": "ICICIBANK", "nse": "ICICIBANK", "yahoo": "ICICIBANK.NS", "zerodha": "NSE:ICICIBANK"},
    {"name": "ICICIPRULI", "nse": "ICICIPRULI", "yahoo": "ICICIPRULI.NS", "zerodha": "NSE:ICICIPRULI"},
    {"name": "ITC", "nse": "ITC", "yahoo": "ITC.NS", "zerodha": "NSE:ITC"},
    {"name": "JSWSTEEL", "nse": "JSWSTEEL", "yahoo": "JSWSTEEL.NS", "zerodha": "NSE:JSWSTEEL"},
    {"name": "KOTAKBANK", "nse": "KOTAKBANK", "yahoo": "KOTAKBANK.NS", "zerodha": "NSE:KOTAKBANK"},
    {"name": "LT", "nse": "LT", "yahoo": "LT.NS", "zerodha": "NSE:LT"},
    {"name": "LICI", "nse": "LICI", "yahoo": "LICI.NS", "zerodha": "NSE:LICI"},
    {"name": "MARUTI", "nse": "MARUTI", "yahoo": "MARUTI.NS", "zerodha": "NSE:MARUTI"},
    {"name": "NESTLEIND", "nse": "NESTLEIND", "yahoo": "NESTLEIND.NS", "zerodha": "NSE:NESTLEIND"},
    {"name": "ONGC", "nse": "ONGC", "yahoo": "ONGC.NS", "zerodha": "NSE:ONGC"},
    {"name": "POWERGRID", "nse": "POWERGRID", "yahoo": "POWERGRID.NS", "zerodha": "NSE:POWERGRID"},
    {"name": "RELIANCE", "nse": "RELIANCE", "yahoo": "RELIANCE.NS", "zerodha": "NSE:RELIANCE"},
    {"name": "SBIN", "nse": "SBIN", "yahoo": "SBIN.NS", "zerodha": "NSE:SBIN"},
    {"name": "SUNPHARMA", "nse": "SUNPHARMA", "yahoo": "SUNPHARMA.NS", "zerodha": "NSE:SUNPHARMA"},
    {"name": "TCS", "nse": "TCS", "yahoo": "TCS.NS", "zerodha": "NSE:TCS"},
    {"name": "TATAMOTORS", "nse": "TATAMOTORS", "yahoo": "TATAMOTORS.NS", "zerodha": "NSE:TATAMOTORS"},
    {"name": "TATAPOWER", "nse": "TATAPOWER", "yahoo": "TATAPOWER.NS", "zerodha": "NSE:TATAPOWER"},
    {"name": "TATASTEEL", "nse": "TATASTEEL", "yahoo": "TATASTEEL.NS", "zerodha": "NSE:TATASTEEL"},
    {"name": "TECHM", "nse": "TECHM", "yahoo": "TECHM.NS", "zerodha": "NSE:TECHM"},
    {"name": "TITAN", "nse": "TITAN", "yahoo": "TITAN.NS", "zerodha": "NSE:TITAN"},
    {"name": "TORNTPHARM", "nse": "TORNTPHARM", "yahoo": "TORNTPHARM.NS", "zerodha": "NSE:TORNTPHARM"},
    {"name": "TRENT", "nse": "TRENT", "yahoo": "TRENT.NS", "zerodha": "NSE:TRENT"},
    {"name": "TVSMOTOR", "nse": "TVSMOTOR", "yahoo": "TVSMOTOR.NS", "zerodha": "NSE:TVSMOTOR"},
    {"name": "UPL", "nse": "UPL", "yahoo": "UPL.NS", "zerodha": "NSE:UPL"},
    {"name": "VEDL", "nse": "VEDL", "yahoo": "VEDL.NS", "zerodha": "NSE:VEDL"},
    {"name": "WIPRO", "nse": "WIPRO", "yahoo": "WIPRO.NS", "zerodha": "NSE:WIPRO"},
]

def get_nifty50_symbols(format_type: str = "nse") -> list:
    """
    Get NIFTY50 symbols in specified format
    
    Args:
        format_type: 'nse', 'yahoo', 'zerodha', or 'name'
    
    Returns:
        List of symbols in requested format
    """
    format_map = {
        "nse": "nse",
        "yahoo": "yahoo",
        "zerodha": "zerodha",
        "name": "name"
    }
    
    key = format_map.get(format_type, "nse")
    return [stock[key] for stock in NIFTY50_STOCKS]

def get_stock_by_nse_symbol(nse_symbol: str) -> dict:
    """Get stock info by NSE symbol"""
    for stock in NIFTY50_STOCKS:
        if stock["nse"] == nse_symbol:
            return stock
    return None

def get_stock_by_zerodha_symbol(zerodha_symbol: str) -> dict:
    """Get stock info by Zerodha symbol"""
    for stock in NIFTY50_STOCKS:
        if stock["zerodha"] == zerodha_symbol:
            return stock
    return None

def is_nifty50_stock(symbol: str) -> bool:
    """Check if symbol is in NIFTY50"""
    nse_symbols = get_nifty50_symbols("nse")
    yahoo_symbols = get_nifty50_symbols("yahoo")
    zerodha_symbols = get_nifty50_symbols("zerodha")
    return symbol in nse_symbols or symbol in yahoo_symbols or symbol in zerodha_symbols
