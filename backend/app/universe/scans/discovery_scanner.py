"""
Discovery Scans

Nightly scans to detect:
- New RS leaders
- Emerging structure
- Volume anomalies
- Unusual tightness
- New sector leadership
- Breakout pressure
- Reclaim quality
- Continuation quality
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from app.universe.discovery.auto_discovery import DiscoveryCandidate, DiscoveryTrigger
from app.universe.enrichment.enricher import EnrichedTicker

logger = logging.getLogger(__name__)


class ScanType(Enum):
    """Scan types"""
    RS_LEADERS = "rs_leaders"
    EMERGING_STRUCTURE = "emerging_structure"
    VOLUME_ANOMALIES = "volume_anomalies"
    TIGHTNESS = "tightness"
    SECTOR_LEADERSHIP = "sector_leadership"
    BREAKOUT_PRESSURE = "breakout_pressure"
    RECLAIM_QUALITY = "reclaim_quality"
    CONTINUATION_QUALITY = "continuation_quality"
    IPO_DETECTION = "ipo_detection"
    SECTOR_ROTATION = "sector_rotation"


@dataclass
class ScanResult:
    """Result of a discovery scan"""
    scan_type: ScanType
    timestamp: datetime
    candidates: List[DiscoveryCandidate]
    total_scanned: int
    scan_duration_seconds: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "scan_type": self.scan_type.value,
            "timestamp": self.timestamp.isoformat(),
            "candidates_found": len(self.candidates),
            "candidates": [c.to_dict() for c in self.candidates],
            "total_scanned": self.total_scanned,
            "scan_duration_seconds": self.scan_duration_seconds
        }


class DiscoveryScanner:
    """
    Discovery Scanner
    
    Nightly scans to detect:
    - New RS leaders (RS > 2.0 for 5 consecutive days)
    - Emerging structure (tight base, volume contraction)
    - Volume anomalies (3x average volume)
    - Unusual tightness (ATR < 2%)
    - New sector leadership (top 3 in sector)
    - Breakout pressure (price near highs with volume)
    - Reclaim quality (reclaim of EMA21 with volume)
    - Continuation quality (extension with volume)
    
    Scan Schedule:
    - Run nightly after market close
    - Scan entire market universe (TIER 2-4)
    - Detect new candidates
    - Validate and enrich
    - Add to universe if valid
    - Emit discovery events
    """
    
    def __init__(self):
        self._scan_results: List[ScanResult] = []
    
    def scan_rs_leaders(
        self,
        ticker_data: List[Dict[str, Any]]
    ) -> ScanResult:
        """
        Scan for new RS leaders (RS > 2.0 for 5 consecutive days).
        
        Args:
            ticker_data: List of ticker data with RS history
            
        Returns:
            ScanResult
        """
        start_time = datetime.utcnow()
        candidates = []
        
        for data in ticker_data:
            symbol = data.get("symbol")
            current_rs = data.get("rs_spy") or data.get("rs_qqq")
            rs_history = data.get("rs_history", [])
            
            if not symbol or not current_rs:
                continue
            
            # Check if RS > 2.0 for 5 consecutive days
            if current_rs > 2.0:
                consecutive_days = 0
                for rs in reversed(rs_history[-5:]):
                    if rs > 2.0:
                        consecutive_days += 1
                    else:
                        break
                
                if consecutive_days >= 5:
                    candidate = DiscoveryCandidate(
                        symbol=symbol,
                        trigger=DiscoveryTrigger.RS_ACCELERATION,
                        timestamp=datetime.utcnow(),
                        data={
                            "current_rs": current_rs,
                            "consecutive_days": consecutive_days,
                            "rs_history": rs_history[-5:]
                        },
                        confidence=min(100, 50 + 30),
                        priority=1
                    )
                    candidates.append(candidate)
        
        scan_duration = (datetime.utcnow() - start_time).total_seconds()
        
        result = ScanResult(
            scan_type=ScanType.RS_LEADERS,
            timestamp=datetime.utcnow(),
            candidates=candidates,
            total_scanned=len(ticker_data),
            scan_duration_seconds=scan_duration
        )
        
        self._scan_results.append(result)
        logger.info(f"RS Leaders scan: {len(candidates)} candidates found from {len(ticker_data)} tickers")
        
        return result
    
    def scan_emerging_structure(
        self,
        ticker_data: List[Dict[str, Any]]
    ) -> ScanResult:
        """
        Scan for emerging structure (tight base, volume contraction).
        
        Args:
            ticker_data: List of ticker data with structure metrics
            
        Returns:
            ScanResult
        """
        start_time = datetime.utcnow()
        candidates = []
        
        for data in ticker_data:
            symbol = data.get("symbol")
            weekly_tightness = data.get("weekly_tightness")
            weekly_volatility_contraction = data.get("weekly_volatility_contraction")
            volume_contraction = data.get("volume_contraction")
            
            if not symbol:
                continue
            
            # Check for tight base with volume contraction
            if weekly_tightness and weekly_tightness < 0.02:  # < 2% tightness
                if volume_contraction and volume_contraction < 0.5:  # < 50% of average volume
                    candidate = DiscoveryCandidate(
                        symbol=symbol,
                        trigger=DiscoveryTrigger.RECLAIM_QUALITY,
                        timestamp=datetime.utcnow(),
                        data={
                            "weekly_tightness": weekly_tightness,
                            "volume_contraction": volume_contraction,
                            "weekly_volatility_contraction": weekly_volatility_contraction
                        },
                        confidence=min(100, 50 + 25),
                        priority=2
                    )
                    candidates.append(candidate)
        
        scan_duration = (datetime.utcnow() - start_time).total_seconds()
        
        result = ScanResult(
            scan_type=ScanType.EMERGING_STRUCTURE,
            timestamp=datetime.utcnow(),
            candidates=candidates,
            total_scanned=len(ticker_data),
            scan_duration_seconds=scan_duration
        )
        
        self._scan_results.append(result)
        logger.info(f"Emerging Structure scan: {len(candidates)} candidates found from {len(ticker_data)} tickers")
        
        return result
    
    def scan_volume_anomalies(
        self,
        ticker_data: List[Dict[str, Any]]
    ) -> ScanResult:
        """
        Scan for volume anomalies (3x average volume).
        
        Args:
            ticker_data: List of ticker data with volume data
            
        Returns:
            ScanResult
        """
        start_time = datetime.utcnow()
        candidates = []
        
        for data in ticker_data:
            symbol = data.get("symbol")
            current_volume = data.get("volume")
            avg_volume = data.get("avg_volume_20d")
            current_price = data.get("close")
            
            if not symbol or not current_volume or not avg_volume:
                continue
            
            if avg_volume == 0:
                continue
            
            volume_multiplier = current_volume / avg_volume
            
            if volume_multiplier >= 3.0 and current_volume >= 1_000_000:
                candidate = DiscoveryCandidate(
                    symbol=symbol,
                    trigger=DiscoveryTrigger.VOLUME_EXPLOSION,
                    timestamp=datetime.utcnow(),
                    data={
                        "current_volume": current_volume,
                        "avg_volume": avg_volume,
                        "volume_multiplier": volume_multiplier,
                        "current_price": current_price
                    },
                    confidence=min(100, 50 + 20),
                    priority=2
                )
                candidates.append(candidate)
        
        scan_duration = (datetime.utcnow() - start_time).total_seconds()
        
        result = ScanResult(
            scan_type=ScanType.VOLUME_ANOMALIES,
            timestamp=datetime.utcnow(),
            candidates=candidates,
            total_scanned=len(ticker_data),
            scan_duration_seconds=scan_duration
        )
        
        self._scan_results.append(result)
        logger.info(f"Volume Anomalies scan: {len(candidates)} candidates found from {len(ticker_data)} tickers")
        
        return result
    
    def scan_tightness(
        self,
        ticker_data: List[Dict[str, Any]]
    ) -> ScanResult:
        """
        Scan for unusual tightness (ATR < 2%).
        
        Args:
            ticker_data: List of ticker data with ATR data
            
        Returns:
            ScanResult
        """
        start_time = datetime.utcnow()
        candidates = []
        
        for data in ticker_data:
            symbol = data.get("symbol")
            atr = data.get("atr")
            current_price = data.get("close")
            
            if not symbol or not atr or not current_price:
                continue
            
            atr_percent = (atr / current_price) * 100
            
            if atr_percent < 2.0:
                candidate = DiscoveryCandidate(
                    symbol=symbol,
                    trigger=DiscoveryTrigger.RECLAIM_QUALITY,
                    timestamp=datetime.utcnow(),
                    data={
                        "atr": atr,
                        "atr_percent": atr_percent,
                        "current_price": current_price
                    },
                    confidence=min(100, 50 + 15),
                    priority=3
                )
                candidates.append(candidate)
        
        scan_duration = (datetime.utcnow() - start_time).total_seconds()
        
        result = ScanResult(
            scan_type=ScanType.TIGHTNESS,
            timestamp=datetime.utcnow(),
            candidates=candidates,
            total_scanned=len(ticker_data),
            scan_duration_seconds=scan_duration
        )
        
        self._scan_results.append(result)
        logger.info(f"Tightness scan: {len(candidates)} candidates found from {len(ticker_data)} tickers")
        
        return result
    
    def scan_sector_leadership(
        self,
        ticker_data: List[Dict[str, Any]]
    ) -> ScanResult:
        """
        Scan for new sector leadership (top 3 in sector).
        
        Args:
            ticker_data: List of ticker data with sector and RS data
            
        Returns:
            ScanResult
        """
        start_time = datetime.utcnow()
        candidates = []
        
        # Group by sector
        sector_groups: Dict[str, List[Dict[str, Any]]] = {}
        for data in ticker_data:
            sector = data.get("sector")
            if sector:
                if sector not in sector_groups:
                    sector_groups[sector] = []
                sector_groups[sector].append(data)
        
        # Find top 3 in each sector by RS
        for sector, sector_tickers in sector_groups.items():
            # Sort by RS
            sorted_tickers = sorted(
                sector_tickers,
                key=lambda x: (x.get("rs_spy") or x.get("rs_qqq") or 0),
                reverse=True
            )
            
            # Get top 3
            for i, ticker in enumerate(sorted_tickers[:3]):
                symbol = ticker.get("symbol")
                rs = ticker.get("rs_spy") or ticker.get("rs_qqq")
                
                if symbol and rs:
                    candidate = DiscoveryCandidate(
                        symbol=symbol,
                        trigger=DiscoveryTrigger.SECTOR_LEADERSHIP,
                        timestamp=datetime.utcnow(),
                        data={
                            "sector": sector,
                            "sector_rank": i + 1,
                            "sector_total": len(sector_tickers),
                            "rs": rs
                        },
                        confidence=min(100, 50 + 25),
                        priority=1
                    )
                    candidates.append(candidate)
        
        scan_duration = (datetime.utcnow() - start_time).total_seconds()
        
        result = ScanResult(
            scan_type=ScanType.SECTOR_LEADERSHIP,
            timestamp=datetime.utcnow(),
            candidates=candidates,
            total_scanned=len(ticker_data),
            scan_duration_seconds=scan_duration
        )
        
        self._scan_results.append(result)
        logger.info(f"Sector Leadership scan: {len(candidates)} candidates found from {len(ticker_data)} tickers")
        
        return result
    
    def scan_ipo_detection(
        self,
        ticker_data: List[Dict[str, Any]]
    ) -> ScanResult:
        """
        Scan for recent IPOs (listings in last 30 days).
        
        Args:
            ticker_data: List of ticker data with listing date
            
        Returns:
            ScanResult
        """
        start_time = datetime.utcnow()
        candidates = []
        
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        for data in ticker_data:
            symbol = data.get("symbol")
            listing_date = data.get("listing_date")
            
            if not symbol or not listing_date:
                continue
            
            # Check if listing date is within 30 days
            if isinstance(listing_date, str):
                try:
                    listing_date = datetime.fromisoformat(listing_date)
                except:
                    continue
            
            if listing_date >= cutoff_date:
                candidate = DiscoveryCandidate(
                    symbol=symbol,
                    trigger=DiscoveryTrigger.SECTOR_LEADERSHIP,  # Using existing trigger for now
                    timestamp=datetime.utcnow(),
                    data={
                        "listing_date": listing_date.isoformat(),
                        "days_since_ipo": (datetime.utcnow() - listing_date).days
                    },
                    confidence=min(100, 50 + 30),
                    priority=1
                )
                candidates.append(candidate)
        
        scan_duration = (datetime.utcnow() - start_time).total_seconds()
        
        result = ScanResult(
            scan_type=ScanType.IPO_DETECTION,
            timestamp=datetime.utcnow(),
            candidates=candidates,
            total_scanned=len(ticker_data),
            scan_duration_seconds=scan_duration
        )
        
        self._scan_results.append(result)
        logger.info(f"IPO Detection scan: {len(candidates)} candidates found from {len(ticker_data)} tickers")
        
        return result
    
    def scan_sector_rotation(
        self,
        ticker_data: List[Dict[str, Any]],
        previous_sector_leadership: Optional[Dict[str, List[str]]] = None
    ) -> ScanResult:
        """
        Scan for sector rotation (changes in sector leadership).
        
        Args:
            ticker_data: List of ticker data with sector and RS data
            previous_sector_leadership: Previous sector leadership mapping (sector -> top tickers)
            
        Returns:
            ScanResult
        """
        start_time = datetime.utcnow()
        candidates = []
        
        if not previous_sector_leadership:
            # No previous data, just return empty result
            logger.info("No previous sector leadership data for rotation detection")
            return ScanResult(
                scan_type=ScanType.SECTOR_ROTATION,
                timestamp=datetime.utcnow(),
                candidates=[],
                total_scanned=len(ticker_data),
                scan_duration_seconds=0
            )
        
        # Group by sector
        sector_groups: Dict[str, List[Dict[str, Any]]] = {}
        for data in ticker_data:
            sector = data.get("sector")
            if sector:
                if sector not in sector_groups:
                    sector_groups[sector] = []
                sector_groups[sector].append(data)
        
        # Find current top 3 in each sector by RS
        current_sector_leadership = {}
        for sector, sector_tickers in sector_groups.items():
            sorted_tickers = sorted(
                sector_tickers,
                key=lambda x: (x.get("rs_spy") or x.get("rs_qqq") or 0),
                reverse=True
            )
            current_sector_leadership[sector] = [t.get("symbol") for t in sorted_tickers[:3]]
        
        # Detect rotation: new leaders entering top 3
        for sector, current_leaders in current_sector_leadership.items():
            previous_leaders = previous_sector_leadership.get(sector, [])
            
            # Find new leaders (in current but not in previous)
            new_leaders = [leader for leader in current_leaders if leader not in previous_leaders]
            
            for new_leader in new_leaders:
                candidate = DiscoveryCandidate(
                    symbol=new_leader,
                    trigger=DiscoveryTrigger.SECTOR_LEADERSHIP,
                    timestamp=datetime.utcnow(),
                    data={
                        "sector": sector,
                        "rotation_type": "new_leader",
                        "previous_leaders": previous_leaders,
                        "current_leaders": current_leaders
                    },
                    confidence=min(100, 50 + 25),
                    priority=1
                )
                candidates.append(candidate)
                logger.info(f"Sector rotation detected: {new_leader} entered top 3 in {sector}")
        
        scan_duration = (datetime.utcnow() - start_time).total_seconds()
        
        result = ScanResult(
            scan_type=ScanType.SECTOR_ROTATION,
            timestamp=datetime.utcnow(),
            candidates=candidates,
            total_scanned=len(ticker_data),
            scan_duration_seconds=scan_duration
        )
        
        self._scan_results.append(result)
        logger.info(f"Sector Rotation scan: {len(candidates)} rotation events found from {len(ticker_data)} tickers")
        
        return result

    def run_all_scans(self, ticker_data: List[Dict[str, Any]]) -> List[ScanResult]:
        """
        Run all discovery scans.
        
        Args:
            ticker_data: List of ticker data
            
        Returns:
            List of all scan results
        """
        logger.info(f"Running all discovery scans on {len(ticker_data)} tickers")
        
        results = []
        
        # Run each scan
        results.append(self.scan_rs_leaders(ticker_data))
        results.append(self.scan_emerging_structure(ticker_data))
        results.append(self.scan_volume_anomalies(ticker_data))
        results.append(self.scan_tightness(ticker_data))
        results.append(self.scan_sector_leadership(ticker_data))
        results.append(self.scan_ipo_detection(ticker_data))
        results.append(self.scan_sector_rotation(ticker_data))
        
        # Combine all candidates
        all_candidates = []
        for result in results:
            all_candidates.extend(result.candidates)
        
        logger.info(f"Total candidates discovered: {len(all_candidates)}")
        
        return results
    
    def get_scan_results(
        self,
        scan_type: Optional[ScanType] = None,
        limit: int = 100
    ) -> List[ScanResult]:
        """
        Get scan results with optional filtering.
        
        Args:
            scan_type: Filter by scan type
            limit: Maximum number of results to return
            
        Returns:
            List of scan results
        """
        results = self._scan_results
        
        # Filter by scan type
        if scan_type:
            results = [r for r in results if r.scan_type == scan_type]
        
        # Return most recent first
        results = sorted(results, key=lambda r: r.timestamp, reverse=True)
        
        return results[:limit]
    
    def get_scan_statistics(self) -> Dict[str, Any]:
        """
        Get scan statistics.
        
        Returns:
            Dictionary with statistics
        """
        total_scans = len(self._scan_results)
        
        if total_scans == 0:
            return {"total_scans": 0}
        
        # Count by scan type
        scan_type_counts = {}
        for result in self._scan_results:
            scan_type_counts[result.scan_type.value] = scan_type_counts.get(result.scan_type.value, 0) + 1
        
        # Total candidates discovered
        total_candidates = sum(len(r.candidates) for r in self._scan_results)
        
        # Average scan duration
        avg_duration = sum(r.scan_duration_seconds for r in self._scan_results) / total_scans
        
        return {
            "total_scans": total_scans,
            "scan_type_distribution": scan_type_counts,
            "total_candidates_discovered": total_candidates,
            "average_scan_duration_seconds": avg_duration,
            "most_recent_scan": self._scan_results[-1].timestamp.isoformat() if self._scan_results else None
        }
    
    def clear_scan_results(self):
        """Clear all scan results"""
        self._scan_results.clear()
        logger.info("Cleared all scan results")
