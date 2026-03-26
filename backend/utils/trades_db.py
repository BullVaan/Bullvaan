"""
Trades database utilities - interact with Supabase trades table
Replaces JSON file storage with database persistence
"""
from utils.supabase_client import supabase
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("trades_db")


def save_trade(trade: dict) -> dict:
    """
    Save or update a trade in Supabase
    trade dict must have: id, user_id, date, name, quantity, lot, buy_price, sell_price, pnl, status, etc.
    """
    try:
        # Check if trade exists
        response = supabase.table('trades').select('id').eq('id', trade['id']).execute()
        
        if response.data:
            # Update existing trade
            update_data = {k: v for k, v in trade.items() if k != 'id'}
            update_data['updated_at'] = datetime.utcnow().isoformat()
            result = supabase.table('trades').update(update_data).eq('id', trade['id']).execute()
            logger.info(f"Updated trade {trade['id']}")
        else:
            # Insert new trade
            trade['created_at'] = datetime.utcnow().isoformat()
            trade['updated_at'] = datetime.utcnow().isoformat()
            result = supabase.table('trades').insert(trade).execute()
            logger.info(f"Created trade {trade['id']}")
        
        if result.data:
            return result.data[0]
        return trade
    except Exception as e:
        logger.error(f"Error saving trade: {e}")
        raise


def get_trade(trade_id: str) -> dict:
    """Fetch a single trade by ID"""
    try:
        response = supabase.table('trades').select('*').eq('id', trade_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error fetching trade {trade_id}: {e}")
        return None


def get_user_trades(user_id: str, date: str = None) -> list:
    """
    Fetch all trades for a user, optionally filtered by date (YYYY-MM-DD)
    """
    try:
        query = supabase.table('trades').select('*').eq('user_id', int(user_id))
        
        if date:
            query = query.eq('date', date)
        
        response = query.order('created_at', desc=True).execute()
        return response.data or []
    except Exception as e:
        logger.error(f"Error fetching trades for user {user_id}: {e}")
        return []


def get_user_trades_by_date(user_id: str, date: str = None) -> dict:
    """
    Get trades for user, optionally filtered by date.
    Returns: {trades: [...], total_pnl: X, trade_count: Y, date: Z}
    """
    trades = get_user_trades(user_id, date)
    
    if not date:
        # Default to today (IST)
        ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        date = ist_now.strftime('%Y-%m-%d')
    
    # Filter to get today's trades
    filtered = [t for t in trades if t.get('date') == date]
    total_pnl = sum(t.get('pnl', 0) for t in filtered)
    
    return {
        "trades": filtered,
        "total_pnl": round(total_pnl, 2),
        "trade_count": len(filtered),
        "date": date
    }


def get_active_trades(user_id: str, date: str = None) -> dict:
    """
    Get both open and closed trades for user on a specific date.
    Returns: {trades: [...], date: Z, pnl_by_mode: {real: X, paper: Y}}
    """
    trades = get_user_trades(user_id, date)
    
    if not date:
        ist_now = datetime.utcnow() + timedelta(hours=5, minutes=30)
        date = ist_now.strftime('%Y-%m-%d')
    
    date_trades = [t for t in trades if t.get('date') == date]
    
    # Calculate P&L by mode
    real_pnl = sum(t.get('pnl', 0) for t in date_trades if (t.get('mode') or 'paper') == 'real')
    paper_pnl = sum(t.get('pnl', 0) for t in date_trades if (t.get('mode') or 'paper') == 'paper')
    
    return {
        "trades": date_trades,
        "date": date,
        "pnl_by_mode": {
            "real": round(real_pnl, 2),
            "paper": round(paper_pnl, 2)
        }
    }


def delete_trade(trade_id: str, user_id: str) -> bool:
    """Delete a trade (only if it belongs to the user)"""
    try:
        # Verify ownership
        trade = get_trade(trade_id)
        if not trade or trade.get('user_id') != int(user_id):
            logger.warning(f"Unauthorized delete attempt for trade {trade_id}")
            return False
        
        supabase.table('trades').delete().eq('id', trade_id).execute()
        logger.info(f"Deleted trade {trade_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting trade {trade_id}: {e}")
        return False


def update_trade_sell(trade_id: str, user_id: str, sell_price: float, sell_time: str, reason: str = "") -> dict:
    """Close a trade by updating sell_price and sell_time, calculate P&L"""
    try:
        # Verify ownership
        trade = get_trade(trade_id)
        if not trade or trade.get('user_id') != int(user_id):
            logger.warning(f"Unauthorized update attempt for trade {trade_id}")
            return None
        
        # Calculate P&L
        quantity = trade.get('quantity', 0)
        buy_price = trade.get('buy_price', 0)
        pnl = (sell_price - buy_price) * quantity
        
        # Update trade
        update_data = {
            'sell_price': sell_price,
            'sell_time': sell_time,
            'status': 'closed',
            'pnl': round(pnl, 2),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        # Add exit_reason if provided
        if reason:
            update_data['exit_reason'] = reason
        
        result = supabase.table('trades').update(update_data).eq('id', trade_id).execute()
        
        if result.data:
            logger.info(f"Closed trade {trade_id} with P&L: {pnl}{' - Reason: ' + reason if reason else ''}")
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Error updating trade {trade_id}: {e}")
        return None


def bulk_save_trades(trades: list, user_id: str) -> list:
    """
    Batch insert/update multiple trades for a user
    Useful for auto-trader or bulk operations
    """
    try:
        saved_trades = []
        for trade in trades:
            # Ensure user_id is set
            trade['user_id'] = int(user_id)
            saved = save_trade(trade)
            saved_trades.append(saved)
        
        logger.info(f"Saved {len(saved_trades)} trades for user {user_id}")
        return saved_trades
    except Exception as e:
        logger.error(f"Error bulk saving trades: {e}")
        return []


def get_user_daily_summary(user_id: str, num_days: int = 30) -> list:
    """
    Get daily P&L summary for user over last N days
    Returns list of {date: YYYY-MM-DD, pnl: X, count: Y}
    """
    try:
        trades = get_user_trades(user_id)
        daily_stats = {}
        
        for trade in trades:
            date = trade.get('date')
            if date:
                if date not in daily_stats:
                    daily_stats[date] = {'pnl': 0, 'count': 0}
                daily_stats[date]['pnl'] += trade.get('pnl', 0)
                daily_stats[date]['count'] += 1
        
        # Format response
        summary = [
            {'date': date, 'pnl': round(stats['pnl'], 2), 'count': stats['count']}
            for date, stats in sorted(daily_stats.items(), reverse=True)
        ]
        
        return summary[:num_days]
    except Exception as e:
        logger.error(f"Error getting daily summary for user {user_id}: {e}")
        return []
