"""
Configuration Manager
Loads and manages all configuration from .env and trading_rules.json
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Central configuration class for the trading platform"""
    
    def __init__(self):
        # Get project root directory (parent of backend folder)
        self.backend_dir = Path(__file__).parent.parent
        self.project_root = self.backend_dir.parent
        self.config_dir = self.project_root / "config"
        
        # Load trading rules
        self.trading_rules = self._load_trading_rules()
    
    # ========== Kotak Neo API Configuration ==========
    @property
    def kotak_access_token(self):
        """Kotak Neo Access Token"""
        return os.getenv("KOTAK_ACCESS_TOKEN")
    
    @property
    def kotak_mobile_number(self):
        """Kotak Neo Mobile Number"""
        return os.getenv("KOTAK_MOBILE_NUMBER")
    
    @property
    def kotak_ucc(self):
        """Kotak Neo UCC (Client Code)"""
        return os.getenv("KOTAK_UCC")
    
    @property
    def kotak_mpin(self):
        """Kotak Neo MPIN"""
        return os.getenv("KOTAK_MPIN")
    
    @property
    def kotak_login_url(self):
        """Kotak Neo Login URL"""
        return os.getenv("KOTAK_LOGIN_URL", "https://mis.kotaksecurities.com/login/1.0/tradeApiLogin")
    
    @property
    def kotak_validate_url(self):
        """Kotak Neo Validate URL"""
        return os.getenv("KOTAK_VALIDATE_URL", "https://mis.kotaksecurities.com/login/1.0/tradeApiValidate")
    
    # ========== Database Configuration ==========
    @property
    def database_url(self):
        """Database connection URL"""
        return os.getenv("DATABASE_URL", "sqlite:///./trading.db")
    
    # ========== Application Settings ==========
    @property
    def debug(self):
        """Debug mode flag"""
        return os.getenv("DEBUG", "True").lower() == "true"
    
    @property
    def log_level(self):
        """Logging level"""
        return os.getenv("LOG_LEVEL", "INFO")
    
    @property
    def port(self):
        """Application port"""
        return int(os.getenv("PORT", 8000))
    
    # ========== Trading Rules Configuration ==========
    def _load_trading_rules(self):
        """Load trading rules from JSON file"""
        rules_file = self.config_dir / "trading_rules.json"
        
        if not rules_file.exists():
            raise FileNotFoundError(f"Trading rules file not found at {rules_file}")
        
        with open(rules_file, 'r') as f:
            return json.load(f)
    
    @property
    def consensus_threshold(self):
        """Consensus threshold (0.0 to 1.0)"""
        return self.trading_rules.get("consensus_threshold", 0.7)
    
    @property
    def position_size(self):
        """Number of lots to trade"""
        return self.trading_rules.get("position_size", 1)
    
    @property
    def stop_loss_percent(self):
        """Stop loss percentage"""
        return self.trading_rules.get("stop_loss_percent", 0.5)
    
    @property
    def target_percent(self):
        """Target profit percentage"""
        return self.trading_rules.get("target_percent", 1.0)
    
    @property
    def trading_hours(self):
        """Trading hours dictionary"""
        return self.trading_rules.get("trading_hours", {"start": "09:15", "end": "15:30"})
    
    @property
    def max_trades_per_day(self):
        """Maximum trades allowed per day"""
        return self.trading_rules.get("max_trades_per_day", 10)
    
    @property
    def enable_auto_trading(self):
        """Auto trading enabled flag"""
        return self.trading_rules.get("enable_auto_trading", False)
    
    # ========== Utility Methods ==========
    def get_trading_rule(self, key, default=None):
        """Get a specific trading rule by key"""
        return self.trading_rules.get(key, default)
    
    def reload_trading_rules(self):
        """Reload trading rules from file"""
        self.trading_rules = self._load_trading_rules()
        return self.trading_rules
    
    def __repr__(self):
        return f"<Config debug={self.debug} consensus={self.consensus_threshold}>"


# Global config instance (singleton pattern)
config = Config()


# For easy imports: from utils.config import config
if __name__ == "__main__":
    # Test configuration loading
    print("=" * 50)
    print("Configuration Test")
    print("=" * 50)
    print(f"Debug Mode: {config.debug}")
    print(f"Port: {config.port}")
    print(f"Consensus Threshold: {config.consensus_threshold}")
    print(f"Position Size: {config.position_size} lots")
    print(f"Trading Hours: {config.trading_hours}")
    print(f"Auto Trading: {config.enable_auto_trading}")
    print(f"Kotak Access Token: {config.kotak_access_token[:20]}..." if config.kotak_access_token else "Not Set")
    print("=" * 50)
