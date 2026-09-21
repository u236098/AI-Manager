"""Tests for Pydantic AI output schemas — validation and defaults."""
from __future__ import annotations
import pytest
from pydantic import ValidationError
from app.schemas.ai_outputs import (
    VisualAnalysis,
    DraftReviewOutput,
    DailyBriefOutput,
    CommentClassification,
    ContentIdeaScore,
    CollaborationEvaluation,
    SponsorshipEvaluation,
)


def test_visual_analysis_minimal():
    v = VisualAnalysis()
    assert v.face_visible_first_frame is False
    assert v.location_type == "unknown"


def test_visual_analysis_from_ai_output():
    data = {
        "face_visible_first_frame": True,
        "face_visible_first_3s": True,
        "body_visible": True,
        "location_type": "gym",
        "exercise_performed": "deadlift",
        "camera_angle": "low",
        "text_overlay": True,
        "text_overlay_content": "405lbs PR",
        "dominant_emotion": "energetic",
    }
    v = VisualAnalysis.model_validate(data)
    assert v.exercise_performed == "deadlift"
    assert v.text_overlay_content == "405lbs PR"


def test_draft_review_score_range():
    with pytest.raises(ValidationError):
        DraftReviewOutput(overall_score=0, opening_score=5, objective_fit=5)
    with pytest.raises(ValidationError):
        DraftReviewOutput(overall_score=11, opening_score=5, objective_fit=5)

    valid = DraftReviewOutput(overall_score=7, opening_score=8, objective_fit=6)
    assert valid.overall_score == 7


def test_draft_review_with_issues():
    data = {
        "overall_score": 6,
        "opening_score": 4,
        "objective_fit": 7,
        "issues": [{"timestamp_seconds": 1.5, "description": "Slow start", "severity": "high"}],
        "suggestions": [{"description": "Add text overlay", "expected_impact": "Retention +10%"}],
    }
    review = DraftReviewOutput.model_validate(data)
    assert len(review.issues) == 1
    assert review.issues[0].severity == "high"


def test_daily_brief_defaults():
    b = DailyBriefOutput()
    assert b.actions == []
    assert b.warnings == []


def test_comment_classification():
    c = CommentClassification(
        sentiment="positive",
        category="question",
        reply_priority="high",
        is_question=True,
        suggested_reply="Thanks! Check my latest video for the answer.",
    )
    assert c.is_question is True


def test_content_idea_score_range():
    with pytest.raises(ValidationError):
        ContentIdeaScore(score=0, reasoning="bad")
    valid = ContentIdeaScore(score=85, reasoning="Strong concept", best_objective="authority")
    assert valid.score == 85


def test_collaboration_evaluation():
    e = CollaborationEvaluation(
        fit_score=8,
        audience_overlap="high",
        brand_risk="low",
        reasoning="Good fit",
        recommended_action="accept",
    )
    assert e.fit_score == 8


def test_sponsorship_evaluation_range():
    with pytest.raises(ValidationError):
        SponsorshipEvaluation(brand_fit_score=0, audience_relevance=5)
