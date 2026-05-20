"""
Universe Engine Database Models

Models for:
- InstrumentIdentity (canonical identity)
- ListingEvents (lifecycle tracking)
- UniverseEnrichment (enrichment data)
- UniverseTier (tier assignments)
"""

from sqlalchemy import String, Float, Integer, Boolean, DateTime, JSON, Index, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
from datetime import datetime
import uuid


class InstrumentIdentity(Base):
    """Canonical instrument identity"""
    __tablename__ = "instrument_identities"
    
    internal_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    current_symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    historical_symbols: Mapped[str] = mapped_column(JSON, nullable=True, default=list)
    lifecycle_state: Mapped[str] = mapped_column(String(50), nullable=False, default="active", index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=True)
    primary_exchange: Mapped[str] = mapped_column(String(50), nullable=True)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    listing_events: Mapped["ListingEvent"] = relationship("ListingEvent", back_populates="instrument")
    enrichment: Mapped["UniverseEnrichment"] = relationship("UniverseEnrichment", back_populates="instrument", uselist=False)
    tier_assignment: Mapped["UniverseTier"] = relationship("UniverseTier", back_populates="instrument", uselist=False)
    
    __table_args__ = (
        Index('ix_instrument_identities_current_symbol', 'current_symbol'),
        Index('ix_instrument_identities_lifecycle_state', 'lifecycle_state'),
        Index('ix_instrument_identities_asset_type', 'asset_type'),
    )


class ListingEvent(Base):
    """Listing event for tracking lifecycle"""
    __tablename__ = "listing_events"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    instrument_id: Mapped[str] = mapped_column(String(36), ForeignKey("instrument_identities.internal_id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    old_symbol: Mapped[str] = mapped_column(String(10), nullable=True)
    new_symbol: Mapped[str] = mapped_column(String(10), nullable=True)
    old_exchange: Mapped[str] = mapped_column(String(50), nullable=True)
    new_exchange: Mapped[str] = mapped_column(String(50), nullable=True)
    old_sector: Mapped[str] = mapped_column(String(100), nullable=True)
    new_sector: Mapped[str] = mapped_column(String(100), nullable=True)
    event_metadata: Mapped[str] = mapped_column(JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    instrument: Mapped["InstrumentIdentity"] = relationship("InstrumentIdentity", back_populates="listing_events")
    
    __table_args__ = (
        Index('ix_listing_events_instrument_id', 'instrument_id'),
        Index('ix_listing_events_event_date', 'event_date'),
        Index('ix_listing_events_event_type', 'event_type'),
    )


class UniverseEnrichment(Base):
    """Universe enrichment data"""
    __tablename__ = "universe_enrichment"
    
    instrument_id: Mapped[str] = mapped_column(String(36), ForeignKey("instrument_identities.internal_id"), primary_key=True, nullable=False)
    sector: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    industry: Mapped[str] = mapped_column(String(100), nullable=True)
    float_shares: Mapped[int] = mapped_column(Integer, nullable=True)
    avg_volume_20d: Mapped[int] = mapped_column(Integer, nullable=True)
    avg_dollar_volume_20d: Mapped[float] = mapped_column(Float, nullable=True)
    atr: Mapped[float] = mapped_column(Float, nullable=True)
    atr_percent: Mapped[float] = mapped_column(Float, nullable=True)
    volatility_profile: Mapped[str] = mapped_column(String(50), nullable=True)
    institutional_quality_score: Mapped[float] = mapped_column(Float, nullable=True)
    rs_baseline_spy: Mapped[float] = mapped_column(Float, nullable=True)
    rs_baseline_qqq: Mapped[float] = mapped_column(Float, nullable=True)
    tradability_score: Mapped[float] = mapped_column(Float, nullable=True)
    market_cap_tier: Mapped[str] = mapped_column(String(50), nullable=True)
    last_enriched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    instrument: Mapped["InstrumentIdentity"] = relationship("InstrumentIdentity", back_populates="enrichment")
    
    __table_args__ = (
        Index('ix_universe_enrichment_sector', 'sector'),
        Index('ix_universe_enrichment_market_cap_tier', 'market_cap_tier'),
    )


class UniverseTier(Base):
    """Universe tier assignment"""
    __tablename__ = "universe_tiers"
    
    instrument_id: Mapped[str] = mapped_column(String(36), ForeignKey("instrument_identities.internal_id"), primary_key=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, nullable=True)
    institutional_quality_score: Mapped[float] = mapped_column(Float, nullable=True)
    leadership_score: Mapped[float] = mapped_column(Float, nullable=True)
    setup_quality_score: Mapped[float] = mapped_column(Float, nullable=True)
    sector_relevance_score: Mapped[float] = mapped_column(Float, nullable=True)
    regime_alignment_score: Mapped[float] = mapped_column(Float, nullable=True)
    requires_realtime: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_websocket: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_deep_analysis: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_setup_analysis: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    instrument: Mapped["InstrumentIdentity"] = relationship("InstrumentIdentity", back_populates="tier_assignment")
    
    __table_args__ = (
        Index('ix_universe_tiers_tier', 'tier'),
        Index('ix_universe_tiers_priority_score', 'priority_score'),
    )


class DiscoveryCandidate(Base):
    """Discovery candidates from auto discovery"""
    __tablename__ = "discovery_candidates"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    trigger: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    discovery_data: Mapped[str] = mapped_column(JSON, nullable=True, default=dict)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    added_to_universe: Mapped[bool] = mapped_column(Boolean, default=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    __table_args__ = (
        Index('ix_discovery_candidates_symbol', 'symbol'),
        Index('ix_discovery_candidates_trigger', 'trigger'),
        Index('ix_discovery_candidates_processed', 'processed'),
        Index('ix_discovery_candidates_discovered_at', 'discovered_at'),
    )


class UniverseHealthAlert(Base):
    """Universe health alerts"""
    __tablename__ = "universe_health_alerts"
    
    alert_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    alert_metadata: Mapped[str] = mapped_column(JSON, nullable=True, default=dict)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    __table_args__ = (
        Index('ix_universe_health_alerts_severity', 'severity'),
        Index('ix_universe_health_alerts_alert_type', 'alert_type'),
        Index('ix_universe_health_alerts_resolved', 'resolved'),
        Index('ix_universe_health_alerts_created_at', 'created_at'),
    )
