"""Tests for manager orchestration — routing, conflict detection, graceful degradation."""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.orchestrator import (
    classify_request,
    route,
    detect_conflicts,
    _detect_brief_triggers,
    _cap_confidence,
    ROUTING_TABLE,
    MAX_UNSUPPORTED_CONFIDENCE,
)
from app.schemas.agent_outputs import (
    SpecialistOutput,
    GrowthOutput,
    ContentOutput,
    BrandOutput,
    BusinessOutput,
    Finding,
    RecommendedAction,
    Conflict,
    EvidenceType,
)


def test_classify_content_question():
    result = classify_request("What should I post tomorrow?")
    assert result in ("what_to_post", "content_planning")


def test_classify_sponsorship():
    result = classify_request("Nike offered me €600 for two Reels")
    assert result in ("sponsorship", "deal_evaluation")


def test_classify_profile_change():
    assert classify_request("Should I change my bio?") == "profile_change"


def test_classify_collaboration():
    assert classify_request("Should I collab with this creator?") == "collaboration"


def test_classify_ambiguous_returns_none():
    assert classify_request("How are things going generally?") is None


def test_route_content_planning():
    agents = route("content_planning")
    assert "content" in agents
    assert "growth" in agents
    assert "business" not in agents


def test_route_sponsorship():
    agents = route("sponsorship")
    assert "business" in agents
    assert "brand" in agents
    assert "community" not in agents


def test_route_collaboration():
    agents = route("collaboration")
    assert "community" in agents
    assert "growth" in agents
    assert "brand" in agents


def test_route_unknown_defaults():
    agents = route("some_unknown_type")
    assert len(agents) >= 2


def test_all_routing_entries_reference_valid_agents():
    valid_agents = {"growth", "content", "brand", "research", "community", "business"}
    for decision_type, agents in ROUTING_TABLE.items():
        for agent in agents:
            assert agent in valid_agents, f"{decision_type} references unknown agent: {agent}"


def test_detect_no_conflicts():
    outputs = {
        "growth": (GrowthOutput(
            findings=[Finding(statement="Views are up", confidence=0.8)],
            recommended_actions=[RecommendedAction(action="Post more reels", reasoning="Growth", priority=2)],
        ), None),
        "content": (ContentOutput(
            findings=[Finding(statement="Content gaps exist", confidence=0.7)],
            recommended_actions=[RecommendedAction(action="Create educational content", reasoning="Gap", priority=3)],
        ), None),
    }
    conflicts = detect_conflicts(outputs)
    assert len(conflicts) == 0


def test_detect_directional_conflict():
    outputs = {
        "growth": (GrowthOutput(
            recommended_actions=[
                RecommendedAction(action="Increase fitness posting frequency", reasoning="Performance data", priority=1),
            ],
        ), None),
        "brand": (BrandOutput(
            recommended_actions=[
                RecommendedAction(action="Reduce fitness posting to avoid narrow positioning", reasoning="Brand diversity", priority=2),
            ],
            warnings=["Account becoming too narrowly positioned"],
        ), None),
    }
    conflicts = detect_conflicts(outputs)
    assert len(conflicts) >= 1


def test_detect_warning_vs_recommendation_conflict():
    outputs = {
        "brand": (BrandOutput(
            warnings=["Repeating physique content too often damages brand diversity"],
        ), None),
        "growth": (GrowthOutput(
            recommended_actions=[
                RecommendedAction(action="Repeat physique content format — 2.8× baseline reach", reasoning="viral signal", priority=1),
            ],
        ), None),
    }
    conflicts = detect_conflicts(outputs)
    assert len(conflicts) >= 1


def test_agent_failure_graceful():
    """When one agent fails, the others should still work."""
    outputs = {
        "growth": (GrowthOutput(
            findings=[Finding(statement="Growth is healthy", confidence=0.8)],
        ), None),
        "content": (None, "Agent error: API timeout"),
    }
    conflicts = detect_conflicts(outputs)
    assert isinstance(conflicts, list)


def test_all_agents_fail():
    outputs = {
        "growth": (None, "Error 1"),
        "content": (None, "Error 2"),
    }
    conflicts = detect_conflicts(outputs)
    assert conflicts == []


def test_brief_triggers_follower_drop():
    context = {
        "account_metrics": {
            "kobbycooper": [{"date": "2026-09-09", "followers": 5000, "followers_delta": -80, "total_reach": None, "profile_to_follow_rate": None}]
        },
        "pending_recommendations": [],
        "todays_calendar": [],
        "recent_posts": [{"id": 1}],
    }
    triggers = _detect_brief_triggers(context)
    assert any("drop" in t["reason"].lower() for t in triggers)
    agent_lists = [t["agents"] for t in triggers if "drop" in t["reason"].lower()]
    assert any("brand" in agents for agents in agent_lists)


def test_brief_triggers_follower_surge():
    context = {
        "account_metrics": {
            "kobbycooper": [{"date": "2026-09-09", "followers": 5000, "followers_delta": 350, "total_reach": None, "profile_to_follow_rate": None}]
        },
        "pending_recommendations": [],
        "todays_calendar": [],
        "recent_posts": [{"id": 1}],
    }
    triggers = _detect_brief_triggers(context)
    assert any("surge" in t["reason"].lower() for t in triggers)


def test_brief_triggers_sponsorship_pending():
    context = {
        "account_metrics": {},
        "pending_recommendations": [
            {"summary": "Evaluate Nike deal", "category": "sponsorship", "agent": "business"},
        ],
        "todays_calendar": [],
        "recent_posts": [{"id": 1}],
    }
    triggers = _detect_brief_triggers(context)
    assert any("sponsor" in t["reason"].lower() for t in triggers)


def test_brief_triggers_no_posts():
    context = {
        "account_metrics": {},
        "pending_recommendations": [],
        "todays_calendar": [],
        "recent_posts": [],
    }
    triggers = _detect_brief_triggers(context)
    assert any("no recent" in t["reason"].lower() for t in triggers)


def test_brief_triggers_routine_no_issues():
    context = {
        "account_metrics": {
            "kobbycooper": [{"date": "2026-09-09", "followers": 5000, "followers_delta": 15, "total_reach": None, "profile_to_follow_rate": None}]
        },
        "pending_recommendations": [],
        "todays_calendar": [],
        "recent_posts": [{"id": 1}],
    }
    triggers = _detect_brief_triggers(context)
    assert len(triggers) == 0


def test_cap_confidence_post_data_no_evidence():
    """Data-derived claim without post evidence gets capped."""
    finding = Finding(
        statement="Physique videos convert best",
        evidence_post_ids=[],
        evidence_type=EvidenceType.POST_DATA,
        confidence=0.95,
    )
    _cap_confidence(finding)
    assert finding.confidence == MAX_UNSUPPORTED_CONFIDENCE


def test_cap_confidence_with_evidence_not_capped():
    """Claim with post evidence keeps its confidence."""
    finding = Finding(
        statement="Physique videos convert best",
        evidence_post_ids=[1, 5, 9],
        evidence_type=EvidenceType.POST_DATA,
        confidence=0.95,
    )
    _cap_confidence(finding)
    assert finding.confidence == 0.95


def test_cap_confidence_qualitative_not_capped():
    """Qualitative inferences don't require post IDs."""
    finding = Finding(
        statement="Your username is recognizable",
        evidence_post_ids=[],
        evidence_type=EvidenceType.QUALITATIVE_INFERENCE,
        confidence=0.9,
    )
    _cap_confidence(finding)
    assert finding.confidence == 0.9


def test_cap_confidence_with_metrics_not_capped():
    """If metrics dict has data, that counts as supporting evidence."""
    finding = Finding(
        statement="Follow rate improved",
        evidence_post_ids=[],
        evidence_type=EvidenceType.ACCOUNT_DATA,
        metrics={"follow_rate": 0.015},
        confidence=0.85,
    )
    _cap_confidence(finding)
    assert finding.confidence == 0.85
