"""Pydantic schemas for validating structured AI outputs.

Every AI call that expects JSON should validate against one of these.
If the model returns malformed output, we get a clear validation error
instead of a silent KeyError downstream.
"""
from __future__ import annotations
from pydantic import BaseModel, Field


class VisualAnalysis(BaseModel):
    face_visible_first_frame: bool = False
    face_visible_first_3s: bool = False
    body_visible: bool = False
    physique_reveal: bool = False
    physique_reveal_frame: int | None = None
    shirtless: bool = False
    location_type: str = "unknown"
    location_name: str | None = None
    other_people_visible: bool = False
    exercise_performed: str | None = None
    camera_angle: str = "eye-level"
    text_overlay: bool = False
    text_overlay_content: str | None = None
    first_visual_description: str = ""
    dominant_emotion: str = "neutral"
    lighting: str = "natural"
    strongest_visual_frame: int | None = None
    first_action_frame: int | None = None


class DraftIssue(BaseModel):
    timestamp_seconds: float | None = None
    description: str
    severity: str = "medium"


class DraftSuggestion(BaseModel):
    description: str
    expected_impact: str = ""


class DraftReviewOutput(BaseModel):
    overall_score: int = Field(ge=1, le=10)
    opening_score: int = Field(ge=1, le=10)
    issues: list[DraftIssue] = []
    suggestions: list[DraftSuggestion] = []
    objective_fit: int = Field(ge=1, le=10)


class DailyBriefOutput(BaseModel):
    account_status: str = ""
    summary: str = ""
    key_observation: str = ""
    actions: list[str] = []
    warnings: list[str] = []
    opportunities: list[str] = []


class WeeklyReviewOutput(BaseModel):
    what_worked: list[str] = []
    what_failed: list[str] = []
    stop: list[str] = []
    start: list[str] = []
    continue_doing: list[str] = []
    next_week_strategy: str = ""


class ContentIdeaScore(BaseModel):
    score: int = Field(ge=1, le=100)
    reasoning: str = ""
    best_objective: str = "reach"
    suggested_hook: str = ""
    risks: list[str] = []


class CommentClassification(BaseModel):
    sentiment: str = "neutral"
    category: str = "general"
    reply_priority: str = "low"
    is_question: bool = False
    suggested_reply: str | None = None


class CollaborationEvaluation(BaseModel):
    fit_score: int = Field(ge=1, le=10)
    audience_overlap: str = "unknown"
    brand_risk: str = "low"
    reasoning: str = ""
    recommended_action: str = "review"


class SponsorshipEvaluation(BaseModel):
    brand_fit_score: int = Field(ge=1, le=10)
    audience_relevance: int = Field(ge=1, le=10)
    fair_rate_estimate: float | None = None
    risks: list[str] = []
    negotiation_notes: str = ""
    recommended_action: str = "review"
