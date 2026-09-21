"""Tests for manager memory and knowledge type system."""
from __future__ import annotations
import pytest
from sqlalchemy import select
from app.models.manager import ManagerMemory, KnowledgeType, Recommendation


async def test_create_memory_observation(seeded_db):
    memory = ManagerMemory(
        creator_id=1,
        knowledge_type=KnowledgeType.OBSERVATION,
        category="hooks",
        statement="Face-first hooks retain 15% better than text-first hooks.",
        evidence_post_ids=[1, 3, 5],
        metrics_considered=["retention_rate", "completion_rate"],
        sample_size=3,
        confidence=0.7,
        is_active=True,
    )
    seeded_db.add(memory)
    await seeded_db.flush()

    assert memory.id is not None
    assert memory.knowledge_type == KnowledgeType.OBSERVATION


async def test_create_memory_hypothesis(seeded_db):
    memory = ManagerMemory(
        creator_id=1,
        knowledge_type=KnowledgeType.HYPOTHESIS,
        category="timing",
        statement="Posting at 18:00 CET gets more reach than 12:00.",
        evidence_post_ids=[2, 4],
        metrics_considered=["views", "reach"],
        sample_size=2,
        confidence=0.4,
        is_active=True,
    )
    seeded_db.add(memory)
    await seeded_db.flush()

    assert memory.knowledge_type == KnowledgeType.HYPOTHESIS
    assert memory.confidence == 0.4


async def test_memory_supersede(seeded_db):
    old = ManagerMemory(
        creator_id=1, knowledge_type=KnowledgeType.OBSERVATION,
        category="content", statement="Old observation",
        confidence=0.6, is_active=True,
    )
    seeded_db.add(old)
    await seeded_db.flush()

    new = ManagerMemory(
        creator_id=1, knowledge_type=KnowledgeType.OBSERVATION,
        category="content", statement="Updated observation with more data",
        confidence=0.85, is_active=True,
        promoted_from_id=old.id,
    )
    seeded_db.add(new)
    await seeded_db.flush()

    old.is_active = False
    old.superseded_by_id = new.id
    await seeded_db.flush()

    refreshed_old = await seeded_db.get(ManagerMemory, old.id)
    refreshed_new = await seeded_db.get(ManagerMemory, new.id)
    assert refreshed_old.is_active is False
    assert refreshed_old.superseded_by_id == new.id
    assert refreshed_new.promoted_from_id == old.id


def test_knowledge_types_are_distinct():
    assert KnowledgeType.FACT != KnowledgeType.OBSERVATION
    assert KnowledgeType.OBSERVATION != KnowledgeType.HYPOTHESIS
    assert KnowledgeType.FACT.value == "fact"


async def test_recommendation_approve_reject(seeded_db):
    rec = Recommendation(
        creator_id=1, agent="growth", category="test",
        summary="Test rec", status="pending", confidence=0.8,
    )
    seeded_db.add(rec)
    await seeded_db.flush()

    rec.status = "accepted"
    rec.user_decision = "approve"
    rec.user_feedback = "Let's try it"
    await seeded_db.flush()

    result = await seeded_db.get(Recommendation, rec.id)
    assert result.status == "accepted"
    assert result.user_feedback == "Let's try it"


async def test_recommendation_reject(seeded_db):
    rec = Recommendation(
        creator_id=1, agent="content", category="test",
        summary="Bad idea", status="pending", confidence=0.3,
    )
    seeded_db.add(rec)
    await seeded_db.flush()

    rec.status = "rejected"
    rec.user_decision = "reject"
    rec.user_feedback = "Not aligned with brand"
    await seeded_db.flush()

    result = await seeded_db.get(Recommendation, rec.id)
    assert result.status == "rejected"
