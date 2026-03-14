"""
Premarket Alert System
======================
Monitors premarket signals and triggers alerts for strong setups
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Callable
from enum import Enum

logger = logging.getLogger("premarket_alerts")

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))

class AlertSeverity(Enum):
    """Alert severity levels"""
    CRITICAL = "CRITICAL"   # STRONG signal, gap > 2%
    HIGH = "HIGH"           # STRONG signal
    MEDIUM = "MEDIUM"       # MEDIUM signal
    LOW = "LOW"             # WEAK signal or WATCH mode


class AlertType(Enum):
    """Types of premarket alerts"""
    STRONG_BUY = "STRONG_BUY"
    STRONG_SELL = "STRONG_SELL"
    VOLUME_SPIKE = "VOLUME_SPIKE"
    GAP_UP = "GAP_UP"
    GAP_DOWN = "GAP_DOWN"
    REVERSAL = "REVERSAL"


class PremarketAlert:
    """Single premarket alert"""
    
    def __init__(
        self,
        symbol: str,
        alert_type: AlertType,
        severity: AlertSeverity,
        signal_data: Dict,
        message: str
    ):
        self.symbol = symbol
        self.alert_type = alert_type
        self.severity = severity
        self.signal_data = signal_data
        self.message = message
        self.timestamp = datetime.now(IST)
        self.triggered_at = None
        self.acknowledged = False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API response"""
        return {
            "symbol": self.symbol,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "signal": self.signal_data,
            "acknowledged": self.acknowledged
        }


class PremarketAlertManager:
    """Manages premarket alerts and notifications"""
    
    def __init__(self, alert_callback: Optional[Callable] = None):
        """
        Initialize alert manager
        
        Args:
            alert_callback: Optional callback function to trigger on alerts
                          Signature: callback(alert: PremarketAlert)
        """
        self.alerts: List[PremarketAlert] = []
        self.alert_history: List[PremarketAlert] = []
        self.alert_callback = alert_callback
        self.max_alerts = 100
    
    def process_signals(self, signals: List[Dict]):
        """
        Process a batch of premarket signals and generate alerts
        
        Args:
            signals: List of signal dictionaries from PremarketSignalEngine
        """
        for signal in signals:
            if signal['signal'] == 'NEUTRAL':
                continue  # Skip neutral signals
            
            # Check for alert conditions
            if self._is_strong_signal(signal):
                self._create_alert(signal)
            elif self._has_volume_spike(signal):
                self._create_volume_alert(signal)
            elif self._has_large_gap(signal):
                self._create_gap_alert(signal)
    
    def _is_strong_signal(self, signal: Dict) -> bool:
        """Check if signal strength warrants alert"""
        return signal['strength'] in ['STRONG', 'MEDIUM']
    
    def _has_volume_spike(self, signal: Dict) -> bool:
        """Check for abnormal volume spike"""
        if 'yesterday_volume' not in signal or 'prev_volume_avg' not in signal:
            return False
        
        volume_ratio = signal['yesterday_volume'] / signal['prev_volume_avg'] \
            if signal['prev_volume_avg'] > 0 else 0
        
        return volume_ratio > 1.5
    
    def _has_large_gap(self, signal: Dict) -> bool:
        """Check for large gap (>2%)"""
        return abs(signal['gap_percent']) > 2.0
    
    def _create_alert(self, signal: Dict):
        """Create alert for strong signal"""
        signal_type = signal['signal']
        strength = signal['strength']
        gap_percent = signal['gap_percent']
        
        # Determine alert type and severity
        if signal_type == 'BUY':
            alert_type = AlertType.STRONG_BUY
            severity = AlertSeverity.CRITICAL if strength == 'STRONG' else AlertSeverity.HIGH
            base_msg = "Strong Buy Setup"
        else:
            alert_type = AlertType.STRONG_SELL
            severity = AlertSeverity.CRITICAL if strength == 'STRONG' else AlertSeverity.HIGH
            base_msg = "Strong Sell Setup"
        
        message = f"{base_msg} - {signal['reason']}"
        
        alert = PremarketAlert(
            symbol=signal['symbol'],
            alert_type=alert_type,
            severity=severity,
            signal_data=signal,
            message=message
        )
        
        self._add_alert(alert)
    
    def _create_volume_alert(self, signal: Dict):
        """Create alert for volume spike"""
        volume_ratio = signal['yesterday_volume'] / signal['prev_volume_avg'] \
            if signal['prev_volume_avg'] > 0 else 0
        
        message = f"Huge volume spike! {volume_ratio:.1f}x average - Expect volatile move"
        
        alert = PremarketAlert(
            symbol=signal['symbol'],
            alert_type=AlertType.VOLUME_SPIKE,
            severity=AlertSeverity.MEDIUM,
            signal_data=signal,
            message=message
        )
        
        self._add_alert(alert)
    
    def _create_gap_alert(self, signal: Dict):
        """Create alert for large gap"""
        gap_percent = signal['gap_percent']
        direction = "UP" if gap_percent > 0 else "DOWN"
        
        alert_type = AlertType.GAP_UP if gap_percent > 0 else AlertType.GAP_DOWN
        
        message = f"Large gap {direction} of {abs(gap_percent):.2f}% - Watch for gap fill"
        
        alert = PremarketAlert(
            symbol=signal['symbol'],
            alert_type=alert_type,
            severity=AlertSeverity.MEDIUM,
            signal_data=signal,
            message=message
        )
        
        self._add_alert(alert)
    
    def _add_alert(self, alert: PremarketAlert):
        """Add alert to active list and trigger callback"""
        self.alerts.append(alert)
        self.alert_history.append(alert)
        
        # Trim history if too large
        if len(self.alert_history) > self.max_alerts * 2:
            self.alert_history = self.alert_history[-self.max_alerts:]
        
        logger.info(f"Alert triggered: {alert.symbol} - {alert.alert_type.value}")
        
        # Call callback if provided
        if self.alert_callback:
            try:
                self.alert_callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
    
    def get_active_alerts(self) -> List[Dict]:
        """Get all active (unacknowledged) alerts"""
        return [a.to_dict() for a in self.alerts if not a.acknowledged]
    
    def get_all_alerts(self) -> List[Dict]:
        """Get all alerts including acknowledged"""
        return [a.to_dict() for a in self.alerts]
    
    def acknowledge_alert(self, symbol: str, alert_type: str) -> bool:
        """Mark alert as acknowledged"""
        for alert in self.alerts:
            if alert.symbol == symbol and alert.alert_type.value == alert_type:
                alert.acknowledged = True
                return True
        return False
    
    def clear_alerts(self, symbol: Optional[str] = None):
        """Clear alerts for a symbol or all"""
        if symbol:
            self.alerts = [a for a in self.alerts if a.symbol != symbol]
        else:
            self.alerts = []
    
    def get_alerts_by_severity(self, severity: AlertSeverity) -> List[Dict]:
        """Get alerts filtered by severity"""
        return [
            a.to_dict() for a in self.alerts
            if a.severity == severity and not a.acknowledged
        ]
    
    def get_critical_alerts(self) -> List[Dict]:
        """Get only critical priority alerts"""
        return self.get_alerts_by_severity(AlertSeverity.CRITICAL)
    
    def get_summary(self) -> Dict:
        """Get summary of current alerts"""
        active = [a for a in self.alerts if not a.acknowledged]
        critical = [a for a in active if a.severity == AlertSeverity.CRITICAL]
        high = [a for a in active if a.severity == AlertSeverity.HIGH]
        
        return {
            "total_active": len(active),
            "critical": len(critical),
            "high": len(high),
            "timestamp": datetime.now(IST).isoformat()
        }
