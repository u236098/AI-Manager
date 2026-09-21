"""Structured output schemas for specialist agents.

Every specialist returns evidence-backed findings, not prose.
The Manager consumes these structured outputs to make decisions.
"""
from __future__ import annotations
import enum
from pydantic import BaseModel, Field


class EvidenceType(str, enum.Enum):
    ACCOUNT_DATA = "account_data"
    POST_DATA = "post_data"
    MANAGER_MEMORY = "manager_memory"
    EXTERNAL_RESEARCH = "external_research"
    QUALITATIVE_INFERENCE = "qualitative_inference"


class Finding(BaseModel):
    statement: str
    evidence_post_ids: list[int] = []
    evidence_type: EvidenceType = EvidenceType.QUALITATIVE_INFERENCE
    metrics: dict[str, float] = {}
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class RecommendedAction(BaseModel):
    action: str
    reasoning: str
    priority: int = Field(ge=1, le=10, default=5)
    expected_outcome: str = ""


class SpecialistOutput(BaseModel):
    """Base output every specialist agent returns."""
    findings: list[Finding] = []
    recommended_actions: list[RecommendedAction] = []
    warnings: list[str] = []


class GrowthOutput(SpecialistOutput):
    growth_rate_7d: float | None = None
    best_performing_objective: str | None = None
    worst_performing_objective: str | None = None
    experiment_suggestions: list[str] = []


class ContentOutput(SpecialistOutput):
    content_gaps: list[str] = []
    series_opportunities: list[str] = []
    recommended_concepts: list[dict] = []
    calendar_suggestions: list[dict] = []


class BrandOutput(SpecialistOutput):
    positioning_assessment: str = ""
    portfolio_balance: dict[str, float] = {}
    brand_risks: list[str] = []
    profile_suggestions: list[str] = []


class CommunityOutput(SpecialistOutput):
    priority_comments: list[dict] = []
    sentiment_summary: str = ""
    collaboration_leads: list[dict] = []
    content_requests_from_audience: list[str] = []


class BusinessOutput(SpecialistOutput):
    deal_evaluations: list[dict] = []
    monetisation_readiness: str = ""
    opportunity_alerts: list[str] = []


class ResearchOutput(SpecialistOutput):
    trending_formats: list[dict] = []
    competitor_moves: list[dict] = []
    trend_scores: list[dict] = []


class Conflict(BaseModel):
    agents: list[str]
    topic: str
    positions: dict[str, str]


class ManagerDecisionOutput(BaseModel):
    """What the Manager produces after synthesizing specialist outputs."""
    decision: str
    reasoning: str
    agents_consulted: list[str]
    conflicts_detected: list[Conflict] = []
    conflict_resolution: str | None = None
    recommended_actions: list[RecommendedAction] = []
    evidence_post_ids: list[int] = []
    evidence_memory_ids: list[int] = []
    metrics_considered: list[str] = []
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
