"""
Logger Utility
Provides logging functionality for trades, signals, and application events
"""

import logging
from pathlib import Path
from datetime import datetime

# Get project root and create logs directory
project_root = Path(__file__).parent.parent.parent
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)

# Create formatter for log messages
log_formatter = logging.Formatter(
    '[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def setup_logger(name, log_file, level=logging.INFO):
    """
    Creates and configures a logger
    
    Args:
        name: Logger name
        log_file: Path to log file
        level: Logging level (default: INFO)
    
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent duplicate logs if logger already exists
    if logger.handlers:
        return logger
    
    # File handler - writes to file
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(log_formatter)
    logger.addHandler(file_handler)
    
    # Console handler - prints to terminal
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)
    
    return logger



# Create three different loggers for different purposes
trades_logger = setup_logger(
    'trades_logger', 
    logs_dir / 'trades.log',
    level=logging.INFO
)

signals_logger = setup_logger(
    'signals_logger', 
    logs_dir / 'signals.log',
    level=logging.INFO
)

app_logger = setup_logger(
    'app_logger', 
    logs_dir / 'app.log',
    level=logging.INFO
)



# For testing when run directly
if __name__ == "__main__":
    print("=" * 50)
    print("Logger Test")
    print("=" * 50)
    
    app_logger.info("Application started")
    signals_logger.info("Test signal: BUY from RSI strategy")
    trades_logger.info("Test trade: Bought NIFTY 22400 CE @ 150")
    
    print(f"\nLog files created at: {logs_dir}")
    print("- trades.log")
    print("- signals.log")
    print("- app.log")
    print("\nCheck the files to see the logged messages!")
    print("=" * 50)

# Logger module ready to use
# Example usage:
# from utils.logger import app_logger, trades_logger, signals_logger
# app_logger.info("Application started")
# trades_logger.info("Executed BUY: 1 lot NIFTY 22400 CE @ 150")
# signals_logger.info("RSI Strategy: BUY signal at price 150")
# Log app events
app_logger.info("WebSocket connected to Kotak Neo")
app_logger.error("Failed to fetch option chain")