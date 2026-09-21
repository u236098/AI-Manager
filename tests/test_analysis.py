"""Tests for the analysis loop, observations, recommendations, and scoring."""
from __future__ import annotations
import pytest
from app.services.analysis import (
    analyze_performance,
    create_observation,
    create_recommendation,
    score_recommendation,
    run_analysis_loop,
    _get_scoring_weights,
    _get_metric_at_age,
    _compute_age_normalized_medians,
    OBJECTIVE_SCORING_WEIGHTS,
)
from app.models.manager import KnowledgeType


async def test_analyze_performance_returns_summary(seeded_db):
    result = await analyze_performance(1, seeded_db)
    assert "summary" in result
    assert result["summary"]["total_posts"] == 10
    assert "baselines_at_7d" in result["summary"]


async def test_analyze_performance_no_posts(db):
    from app.models.core import Creator
    db.add(Creator(id=1, name="Test"))
    await db.flush()
    result = await analyze_performance(1, db)
    assert "error" in result


async def test_age_normalized_medians(seeded_db):
    medians = await _compute_age_normalized_medians([1, 2, 3], 168, seeded_db)
    assert "views" in medians
    assert medians["views"] > 0


async def test_get_metric_at_age(seeded_db):
    metric = await _get_metric_at_age(1, 24, seeded_db)
    assert metric is not None
    assert abs(metric.hours_after_publish - 24) < 50


async def test_create_observation(seeded_db):
    obs = await create_observation(
        creator_id=1, db=seeded_db,
        category="test",
        statement="Test observation",
        evidence_post_ids=[1, 2],
        metrics_considered=["views"],
        sample_size=2,
        confidence=0.8,
    )
    assert obs.id is not None
    assert obs.knowledge_type == KnowledgeType.OBSERVATION
    assert obs.confidence == 0.8


async def test_create_recommendation(seeded_db):
    rec = await create_recommendation(
        creator_id=1, db=seeded_db,
        agent="growth",
        category="content",
        summary="Test recommendation",
        detail="Details here",
        reasoning="Because test",
        evidence_post_ids=[1],
        evidence_memory_ids=None,
        metrics_considered=["views", "follow_rate"],
        confidence=0.7,
    )
    assert rec.id is not None
    assert rec.status == "pending"
    assert rec.confidence == 0.7


async def test_score_recommendation_follower_conversion(seeded_db):
    rec = await create_recommendation(
        creator_id=1, db=seeded_db,
        agent="growth", category="content",
        summary="Optimize for followers",
        detail=None, reasoning="test",
        evidence_post_ids=None, evidence_memory_ids=None,
        metrics_considered=["follow_rate"],
        confidence=0.8,
    )
    await seeded_db.commit()

    scored = await score_recommendation(
        rec.id, seeded_db,
        outcome_metrics={"followers_from_post": 50, "follow_rate": 0.01, "saves": 200, "retention_rate": 0.6},
        baseline_metrics={"followers_from_post": 30, "follow_rate": 0.005, "saves": 150, "retention_rate": 0.5},
        objective="follower_conversion",
    )
    assert scored.outcome_measured is True
    assert scored.outcome_verdict == "successful"
    assert scored.manager_score > 0.5


async def test_score_recommendation_unsuccessful(seeded_db):
    rec = await create_recommendation(
        creator_id=1, db=seeded_db,
        agent="content", category="format",
        summary="Try new format",
        detail=None, reasoning="test",
        evidence_post_ids=None, evidence_memory_ids=None,
        metrics_considered=["views"],
        confidence=0.5,
    )
    await seeded_db.commit()

    scored = await score_recommendation(
        rec.id, seeded_db,
        outcome_metrics={"views": 1000, "saves": 10, "followers_from_post": 2, "retention_rate": 0.2, "completion_rate": 0.1},
        baseline_metrics={"views": 5000, "saves": 100, "followers_from_post": 20, "retention_rate": 0.5, "completion_rate": 0.4},
        objective="reach",
    )
    assert scored.outcome_verdict == "unsuccessful"
    assert scored.manager_score < 0.45


def test_objective_weights_sum_to_one():
    for obj, weights in OBJECTIVE_SCORING_WEIGHTS.items():
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01, f"{obj} weights sum to {total}"


def test_scoring_weights_default():
    weights = _get_scoring_weights(None)
    assert "views" in weights
    assert sum(weights.values()) == pytest.approx(1.0)


def test_scoring_weights_known_objective():
    weights = _get_scoring_weights("follower_conversion")
    assert weights["followers_from_post"] == 0.40
    assert weights["follow_rate"] == 0.30


async def test_run_analysis_loop(seeded_db):
    result = await run_analysis_loop(1, seeded_db)
    assert "analysis_summary" in result
    assert "observations_created" in result
    assert "recommendations_created" in result
