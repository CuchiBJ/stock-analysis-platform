"""
Universe Health Monitoring

Monitor universe health:
- Missing sectors (sectors with no tickers)
- Stale tickers (tickers not updated in > 7 days)
- Dead listings (tickers with no price data)
- Symbol inconsistencies (duplicate symbols, invalid symbols)
- Universe freshness (last update time)
- Coverage gaps (sectors with < 10 tickers)
- Ingestion failures (failed enrichments, validation failures)

Create Universe Health Dashboard.
"""

import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class HealthAlertSeverity(Enum):
    """Health alert severity"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class HealthAlert:
    """Health alert"""
    alert_id: str
    severity: HealthAlertSeverity
    alert_type: str
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "alert_id": self.alert_id,
            "severity": self.severity.value,
            "alert_type": self.alert_type,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None
        }


@dataclass
class UniverseHealthReport:
    """Universe health report"""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_tickers: int = 0
    active_tickers: int = 0
    stale_tickers: int = 0
    dead_listings: int = 0
    missing_sectors: List[str] = field(default_factory=list)
    coverage_gaps: Dict[str, int] = field(default_factory=dict)
    symbol_inconsistencies: List[str] = field(default_factory=list)
    universe_freshness: Optional[float] = None  # 0-100 score
    ingestion_failure_rate: float = 0.0
    alerts: List[HealthAlert] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_tickers": self.total_tickers,
            "active_tickers": self.active_tickers,
            "stale_tickers": self.stale_tickers,
            "dead_listings": self.dead_listings,
            "missing_sectors": self.missing_sectors,
            "coverage_gaps": self.coverage_gaps,
            "symbol_inconsistencies": self.symbol_inconsistencies,
            "universe_freshness": self.universe_freshness,
            "ingestion_failure_rate": self.ingestion_failure_rate,
            "alerts": [a.to_dict() for a in self.alerts],
            "critical_alerts": len([a for a in self.alerts if a.severity == HealthAlertSeverity.CRITICAL]),
            "high_alerts": len([a for a in self.alerts if a.severity == HealthAlertSeverity.HIGH])
        }


class UniverseHealthMonitor:
    """
    Universe Health Monitor
    
    Monitor universe health:
    - Missing sectors (sectors with no tickers)
    - Stale tickers (tickers not updated in > 7 days)
    - Dead listings (tickers with no price data)
    - Symbol inconsistencies (duplicate symbols, invalid symbols)
    - Universe freshness (last update time)
    - Coverage gaps (sectors with < 10 tickers)
    - Ingestion failures (failed enrichments, validation failures)
    """
    
    def __init__(self):
        self._alerts: List[HealthAlert] = []
        self._health_reports: List[UniverseHealthReport] = []
        self._expected_sectors = [
            "Technology",
            "Health Care",
            "Financials",
            "Consumer Discretionary",
            "Consumer Staples",
            "Energy",
            "Industrials",
            "Materials",
            "Utilities",
            "Real Estate",
            "Communication Services"
        ]
    
    def check_missing_sectors(self, current_sectors: Set[str]) -> List[str]:
        """
        Check for missing sectors.
        
        Args:
            current_sectors: Set of current sectors in universe
            
        Returns:
            List of missing sectors
        """
        missing = [sector for sector in self._expected_sectors if sector not in current_sectors]
        
        if missing:
            alert = HealthAlert(
                alert_id=f"missing_sectors_{datetime.utcnow().timestamp()}",
                severity=HealthAlertSeverity.HIGH,
                alert_type="missing_sectors",
                message=f"Missing sectors: {', '.join(missing)}",
                metadata={"missing_sectors": missing}
            )
            self._alerts.append(alert)
            logger.warning(f"Missing sectors detected: {missing}")
        
        return missing
    
    def check_stale_tickers(self, ticker_data: Dict[str, datetime], stale_threshold_days: int = 7) -> List[str]:
        """
        Check for stale tickers (not updated in > threshold days).
        
        Args:
            ticker_data: Dictionary mapping symbol to last update timestamp
            stale_threshold_days: Days threshold for staleness
            
        Returns:
            List of stale ticker symbols
        """
        cutoff_date = datetime.utcnow() - timedelta(days=stale_threshold_days)
        stale = [symbol for symbol, last_update in ticker_data.items() if last_update < cutoff_date]
        
        if stale:
            alert = HealthAlert(
                alert_id=f"stale_tickers_{datetime.utcnow().timestamp()}",
                severity=HealthAlertSeverity.MEDIUM,
                alert_type="stale_tickers",
                message=f"Found {len(stale)} stale tickers (not updated in > {stale_threshold_days} days)",
                metadata={"stale_tickers": stale[:100], "stale_count": len(stale)}
            )
            self._alerts.append(alert)
            logger.warning(f"Found {len(stale)} stale tickers")
        
        return stale
    
    def check_dead_listings(self, ticker_data: Dict[str, Optional[float]]) -> List[str]:
        """
        Check for dead listings (tickers with no price data).
        
        Args:
            ticker_data: Dictionary mapping symbol to current price (None if no data)
            
        Returns:
            List of dead listing symbols
        """
        dead = [symbol for symbol, price in ticker_data.items() if price is None]
        
        if dead:
            alert = HealthAlert(
                alert_id=f"dead_listings_{datetime.utcnow().timestamp()}",
                severity=HealthAlertSeverity.HIGH,
                alert_type="dead_listings",
                message=f"Found {len(dead)} dead listings (no price data)",
                metadata={"dead_listings": dead[:100], "dead_count": len(dead)}
            )
            self._alerts.append(alert)
            logger.warning(f"Found {len(dead)} dead listings")
        
        return dead
    
    def check_symbol_inconsistencies(self, ticker_symbols: List[str]) -> List[str]:
        """
        Check for symbol inconsistencies (duplicates, invalid formats).
        
        Args:
            ticker_symbols: List of ticker symbols
            
        Returns:
            List of inconsistent symbols
        """
        # Check for duplicates (case-insensitive)
        symbol_counts: Dict[str, int] = {}
        for symbol in ticker_symbols:
            symbol_upper = symbol.upper()
            symbol_counts[symbol_upper] = symbol_counts.get(symbol_upper, 0) + 1
        
        duplicates = [symbol for symbol, count in symbol_counts.items() if count > 1]
        
        # Check for invalid formats
        invalid = []
        for symbol in ticker_symbols:
            if not symbol or len(symbol) > 10 or not symbol.isalnum():
                invalid.append(symbol)
        
        inconsistencies = list(set(duplicates + invalid))
        
        if inconsistencies:
            alert = HealthAlert(
                alert_id=f"symbol_inconsistencies_{datetime.utcnow().timestamp()}",
                severity=HealthAlertSeverity.MEDIUM,
                alert_type="symbol_inconsistencies",
                message=f"Found {len(inconsistencies)} inconsistent symbols",
                metadata={"inconsistent_symbols": inconsistencies[:100], "inconsistency_count": len(inconsistencies)}
            )
            self._alerts.append(alert)
            logger.warning(f"Found {len(inconsistencies)} inconsistent symbols")
        
        return inconsistencies
    
    def check_coverage_gaps(self, sector_counts: Dict[str, int], min_per_sector: int = 10) -> Dict[str, int]:
        """
        Check for coverage gaps (sectors with < min tickers).
        
        Args:
            sector_counts: Dictionary mapping sector to ticker count
            min_per_sector: Minimum tickers per sector
            
        Returns:
            Dictionary mapping sector to count for sectors below threshold
        """
        gaps = {sector: count for sector, count in sector_counts.items() if count < min_per_sector}
        
        if gaps:
            alert = HealthAlert(
                alert_id=f"coverage_gaps_{datetime.utcnow().timestamp()}",
                severity=HealthAlertSeverity.HIGH,
                alert_type="coverage_gaps",
                message=f"Coverage gaps in {len(gaps)} sectors (below {min_per_sector} tickers)",
                metadata={"coverage_gaps": gaps}
            )
            self._alerts.append(alert)
            logger.warning(f"Coverage gaps in {len(gaps)} sectors")
        
        return gaps
    
    def calculate_universe_freshness(self, ticker_data: Dict[str, datetime]) -> float:
        """
        Calculate universe freshness score (0-100).
        
        Args:
            ticker_data: Dictionary mapping symbol to last update timestamp
            
        Returns:
            Freshness score (0-100)
        """
        if not ticker_data:
            return 0.0
        
        now = datetime.utcnow()
        freshness_scores = []
        
        for symbol, last_update in ticker_data.items():
            days_old = (now - last_update).days
            # Score: 100 for 0 days old, 0 for 30+ days old
            score = max(0, 100 - (days_old * 100 / 30))
            freshness_scores.append(score)
        
        return sum(freshness_scores) / len(freshness_scores)
    
    def calculate_ingestion_failure_rate(self, total_attempts: int, failed_attempts: int) -> float:
        """
        Calculate ingestion failure rate.
        
        Args:
            total_attempts: Total ingestion attempts
            failed_attempts: Failed ingestion attempts
            
        Returns:
            Failure rate (0-1)
        """
        if total_attempts == 0:
            return 0.0
        
        failure_rate = failed_attempts / total_attempts
        
        if failure_rate > 0.1:  # > 10% failure rate
            alert = HealthAlert(
                alert_id=f"high_failure_rate_{datetime.utcnow().timestamp()}",
                severity=HealthAlertSeverity.HIGH,
                alert_type="high_failure_rate",
                message=f"High ingestion failure rate: {failure_rate:.2%}",
                metadata={"failure_rate": failure_rate, "total_attempts": total_attempts, "failed_attempts": failed_attempts}
            )
            self._alerts.append(alert)
            logger.warning(f"High ingestion failure rate: {failure_rate:.2%}")
        
        return failure_rate
    
    def generate_health_report(
        self,
        total_tickers: int,
        active_tickers: int,
        ticker_last_updates: Dict[str, datetime],
        ticker_prices: Dict[str, Optional[float]],
        sector_counts: Dict[str, int],
        current_sectors: Set[str],
        ingestion_stats: Optional[Dict[str, int]] = None
    ) -> UniverseHealthReport:
        """
        Generate comprehensive universe health report.
        
        Args:
            total_tickers: Total number of tickers
            active_tickers: Number of active tickers
            ticker_last_updates: Dictionary mapping symbol to last update
            ticker_prices: Dictionary mapping symbol to current price
            sector_counts: Dictionary mapping sector to ticker count
            current_sectors: Set of current sectors
            ingestion_stats: Optional ingestion statistics
            
        Returns:
            UniverseHealthReport
        """
        report = UniverseHealthReport(
            timestamp=datetime.utcnow(),
            total_tickers=total_tickers,
            active_tickers=active_tickers
        )
        
        # Check health metrics
        report.stale_tickers = len(self.check_stale_tickers(ticker_last_updates))
        report.dead_listings = len(self.check_dead_listings(ticker_prices))
        report.missing_sectors = self.check_missing_sectors(current_sectors)
        report.coverage_gaps = self.check_coverage_gaps(sector_counts)
        report.symbol_inconsistencies = self.check_symbol_inconsistences(list(ticker_last_updates.keys()))
        report.universe_freshness = self.calculate_universe_freshness(ticker_last_updates)
        
        # Ingestion failure rate
        if ingestion_stats:
            total_attempts = ingestion_stats.get("total", 0)
            failed_attempts = ingestion_stats.get("failed", 0)
            report.ingestion_failure_rate = self.calculate_ingestion_failure_rate(total_attempts, failed_attempts)
        
        # Add recent alerts
        report.alerts = self._alerts[-50:] if self._alerts else []
        
        self._health_reports.append(report)
        logger.info(f"Generated health report: {report.universe_freshness:.2f}% freshness, {len(report.alerts)} alerts")
        
        return report
    
    def get_alerts(
        self,
        severity: Optional[HealthAlertSeverity] = None,
        resolved: Optional[bool] = None,
        limit: int = 100
    ) -> List[HealthAlert]:
        """
        Get alerts with optional filtering.
        
        Args:
            severity: Filter by severity
            resolved: Filter by resolved status
            limit: Maximum number of alerts to return
            
        Returns:
            List of alerts
        """
        alerts = self._alerts
        
        # Filter by severity
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        # Filter by resolved status
        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]
        
        # Return most recent first
        alerts = sorted(alerts, key=lambda a: a.timestamp, reverse=True)
        
        return alerts[:limit]
    
    def resolve_alert(self, alert_id: str):
        """
        Resolve an alert.
        
        Args:
            alert_id: Alert ID to resolve
        """
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.resolved = True
                alert.resolved_at = datetime.utcnow()
                logger.info(f"Resolved alert: {alert_id}")
                return
        
        logger.warning(f"Alert not found: {alert_id}")
    
    def get_health_statistics(self) -> Dict[str, Any]:
        """
        Get health monitoring statistics.
        
        Returns:
            Dictionary with statistics
        """
        total_alerts = len(self._alerts)
        
        # Count by severity
        severity_counts = {}
        for alert in self._alerts:
            severity_counts[alert.severity.value] = severity_counts.get(alert.severity.value, 0) + 1
        
        # Count resolved vs unresolved
        resolved_count = sum(1 for a in self._alerts if a.resolved)
        unresolved_count = total_alerts - resolved_count
        
        # Most recent report
        most_recent_report = self._health_reports[-1] if self._health_reports else None
        
        return {
            "total_alerts": total_alerts,
            "severity_distribution": severity_counts,
            "resolved_alerts": resolved_count,
            "unresolved_alerts": unresolved_count,
            "total_health_reports": len(self._health_reports),
            "most_recent_report": most_recent_report.to_dict() if most_recent_report else None
        }
    
    def clear_old_alerts(self, days_to_keep: int = 30):
        """
        Clear alerts older than specified days.
        
        Args:
            days_to_keep: Number of days to keep alerts
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        self._alerts = [a for a in self._alerts if a.timestamp > cutoff_date]
        logger.info(f"Cleared alerts older than {days_to_keep} days")
