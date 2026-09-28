"""Typed contracts for transition preparation surfaces."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class FormationComponentResponse(BaseModel):
    score: float
    weight: float
    contribution: float
    inputs: dict[str, Any]


class FormationScoreBreakdownResponse(BaseModel):
    raw_score: float
    final_score: float
    components: dict[str, FormationComponentResponse]


class FormationGroupResponse(BaseModel):
    group: Optional[str] = None
    badge: Literal["leader", "neutral", "weak"]


class FormationSetupResponse(BaseModel):
    symbol: str
    current_price: Optional[float] = None
    change_pct: Optional[float] = None
    formation_state: str
    formation_score: float
    rank: int
    eligible_count: int
    formation_narrative: str
    primary_risk: str
    next_trigger: str
    distance_to_trigger_atr: Optional[float] = None
    distance_to_trigger_pct: Optional[float] = None
    distance_to_high_52w_atr: Optional[float] = None
    structural_age_days: Optional[int] = None
    structure_evidence: str
    contraction_evidence: str
    rs_direction: str
    group_strength: FormationGroupResponse
    context_warnings: list[str] = Field(default_factory=list)
    score_breakdown: FormationScoreBreakdownResponse


class FormationContextResponse(BaseModel):
    as_of: str
    participation: str
    leadership: str
    regime: str
    follow_through: str
    warnings: list[str] = Field(default_factory=list)


class FormationEnvelopeResponse(BaseModel):
    setups: list[FormationSetupResponse]
    context_snapshot: Optional[FormationContextResponse]
    total_eligible: int
    returned_count: int
    minimum_score: float
    cutoff_score: Optional[float] = None
    limit: int
