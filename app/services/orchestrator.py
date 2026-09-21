"""Manager orchestration — selective routing, structured agent dispatch, conflict resolution.

The Manager doesn't call all six agents on every request. It:
1. Classifies the decision type (deterministic routing table, LLM fallback for ambiguous)
2. Dispatches only the relevant specialists
3. Each specialist returns structured evidence, not prose
4. Detects conflicts between specialist recommendations
5. Synthesizes a final decision with full provenance
"""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import complete, CostTier
from app.agents.growth import GrowthAgent
from app.agents.content import ContentAgent
from app.agents.brand import BrandAgent
from app.agents.research import ResearchAgent
from app.agents.community import CommunityAgent
from app.agents.business import BusinessAgent
from app.agents.base import BaseAgent
from app.models.manager import ManagerDecision, Recommendation
from app.schemas.agent_outputs import (
    SpecialistOutput,
    GrowthOutput,
    ContentOutput,
    BrandOutput,
    CommunityOutput,
    BusinessOutput,
    ResearchOutput,
    Conflict,
    ManagerDecisionOutput,
    RecommendedAction,
    EvidenceType,
)

logger = logging.getLogger(__name__)

ROUTING_TABLE: dict[str, list[str]] = {
    "content_planning": ["content", "growth"],
    "what_to_post": ["content", "growth"],
    "profile_change": ["brand", "growth"],
    "sponsorship": ["business", "brand"],
    "deal_evaluation": ["business", "brand"],
    "comment_strategy": ["community", "content"],
    "collaboration": ["community", "growth", "brand"],
    "brand_review": ["brand", "growth"],
    "growth_diagnosis": ["growth", "content"],
    "trend_evaluation": ["research", "content", "brand"],
    "video_review": ["content", "brand"],
    "weekly_review": ["growth", "content", "brand"],
    "daily_brief": ["growth", "content"],
    "monetisation": ["business", "growth"],
    "experiment_design": ["growth", "content"],
    "audience_analysis": ["growth", "community"],
    "crisis_response": ["brand", "community"],
}

AGENT_SCHEMA_MAP: dict[str, type[SpecialistOutput]] = {
    "growth": GrowthOutput,
    "content": ContentOutput,
    "brand": BrandOutput,
    "community": CommunityOutput,
    "business": BusinessOutput,
    "research": ResearchOutput,
}

CLASSIFY_PROMPT = """Classify this request into exactly one decision type.

Available types: {types}

Request: "{request}"

Return ONLY the decision type string, nothing else."""


def _build_agent_map(creator_id: int) -> dict[str, BaseAgent]:
    return {
        "growth": GrowthAgent(creator_id),
        "content": ContentAgent(creator_id),
        "brand": BrandAgent(creator_id),
        "research": ResearchAgent(creator_id),
        "community": CommunityAgent(creator_id),
        "business": BusinessAgent(creator_id),
    }


def classify_request(request: str) -> str | None:
    """Try to classify a request using keyword matching before falling back to LLM."""
    lower = request.lower()

    keyword_map = {
        "sponsorship": ["sponsor", "brand deal", "paid", "€", "$", "partnership offer"],
        "deal_evaluation": ["offered me", "should i accept", "rate", "compensation"],
        "content_planning": ["what should i post", "content plan", "content calendar", "next week"],
        "what_to_post": ["post tomorrow", "post today", "film next", "what to film"],
        "profile_change": ["change my bio", "change username", "profile pic", "display name", "handle"],
        "collaboration": ["collab", "collaboration", "feature", "guest"],
        "comment_strategy": ["comment", "reply", "respond to"],
        "brand_review": ["brand", "positioning", "identity", "how am i perceived"],
        "growth_diagnosis": ["growth", "why am i", "follower", "stagnant", "declining"],
        "trend_evaluation": ["trend", "trending", "viral", "challenge"],
        "video_review": ["review this video", "draft review", "before posting"],
        "monetisation": ["monetis", "monetiz", "revenue", "earning", "income"],
        "crisis_response": ["negative", "controversy", "backlash", "hate"],
        "audience_analysis": ["audience", "demographic", "who follows"],
    }

    for decision_type, keywords in keyword_map.items():
        if any(kw in lower for kw in keywords):
            return decision_type

    return None


async def classify_request_llm(request: str) -> str:
    """Fall back to LLM classification when keyword matching fails."""
    types = ", ".join(ROUTING_TABLE.keys())
    response = await complete(
        messages=[{"role": "user", "content": CLASSIFY_PROMPT.format(types=types, request=request)}],
        tier=CostTier.ROUTINE,
        max_tokens=50,
    )
    classified = response.text.strip().lower().replace('"', '').replace("'", "")
    if classified in ROUTING_TABLE:
        return classified
    return "content_planning"


def route(decision_type: str) -> list[str]:
    """Get the list of agents to consult for a decision type."""
    return ROUTING_TABLE.get(decision_type, ["content", "growth"])


async def _dispatch_specialist(
    agent: BaseAgent,
    agent_name: str,
    task: str,
    context: dict[str, Any],
    schema: type[SpecialistOutput],
) -> tuple[str, SpecialistOutput | None, str | None]:
    """Run a single specialist and validate its output. Returns (name, output, error)."""
    try:
        output = await agent.run_validated(task, schema, context=context)
        return (agent_name, output, None)
    except (ValidationError, json.JSONDecodeError) as e:
        logger.warning("Agent %s returned invalid output: %s", agent_name, e)
        try:
            raw_result = await agent.run(task, context=context)
            fallback = schema(
                findings=[],
                recommended_actions=[],
                warnings=[f"Agent returned unstructured output: {raw_result.get('raw', '')[:200]}"],
            )
            return (agent_name, fallback, f"Schema validation failed: {e}")
        except Exception as inner:
            return (agent_name, None, f"Agent failed completely: {inner}")
    except Exception as e:
        logger.error("Agent %s failed: %s", agent_name, e)
        return (agent_name, None, f"Agent error: {e}")


async def consult_specialists(
    decision_type: str,
    request: str,
    context: dict[str, Any],
    db: AsyncSession,
    creator_id: int,
) -> dict[str, tuple[SpecialistOutput | None, str | None]]:
    """Dispatch relevant specialists in parallel and collect structured outputs."""
    agent_names = route(decision_type)
    agent_map = _build_agent_map(creator_id)

    task_prompt = f"""Analyze this request and provide your specialist assessment.

Decision type: {decision_type}
Request: {request}

Return structured JSON matching your output schema. Include:
- findings: evidence-backed observations with post IDs and metrics where available
- recommended_actions: specific actions with reasoning, priority (1-10), and expected outcomes
- warnings: any risks or concerns

Be specific. Cite evidence. Report confidence honestly."""

    tasks = []
    for name in agent_names:
        agent = agent_map.get(name)
        schema = AGENT_SCHEMA_MAP.get(name, SpecialistOutput)
        if agent:
            tasks.append(_dispatch_specialist(agent, name, task_prompt, context, schema))

    results_list = await asyncio.gather(*tasks)

    results = {}
    for name, output, error in results_list:
        results[name] = (output, error)

    return results


MAX_UNSUPPORTED_CONFIDENCE = 0.5
DATA_EVIDENCE_TYPES = {EvidenceType.POST_DATA, EvidenceType.ACCOUNT_DATA}


async def validate_specialist_evidence(
    specialist_outputs: dict[str, tuple[SpecialistOutput | None, str | None]],
    db: AsyncSession,
) -> dict[str, tuple[SpecialistOutput | None, str | None]]:
    """Validate evidence IDs exist in DB and cap confidence for unsupported claims.

    Runs BEFORE the Manager sees specialist outputs, so hallucinated post IDs
    never reach the synthesis step.
    """
    from app.models.core import Post

    all_claimed_ids: set[int] = set()
    for _, (output, _) in specialist_outputs.items():
        if output is None:
            continue
        for finding in output.findings:
            all_claimed_ids.update(finding.evidence_post_ids)

    if all_claimed_ids:
        existing = set((await db.execute(
            select(Post.id).where(Post.id.in_(list(all_claimed_ids)))
        )).scalars().all())
    else:
        existing = set()

    invalid_ids = all_claimed_ids - existing
    if invalid_ids:
        logger.warning("Specialists cited non-existent post IDs: %s", invalid_ids)

    for name, (output, error) in specialist_outputs.items():
        if output is None:
            continue
        for finding in output.findings:
            original_ids = finding.evidence_post_ids[:]
            finding.evidence_post_ids = [pid for pid in finding.evidence_post_ids if pid in existing]
            if len(finding.evidence_post_ids) < len(original_ids):
                removed = set(original_ids) - set(finding.evidence_post_ids)
                logger.warning(
                    "Agent %s finding '%s': removed invalid post IDs %s",
                    name, finding.statement[:60], removed,
                )

            _cap_confidence(finding)

    return specialist_outputs


def _cap_confidence(finding) -> None:
    """Cap confidence when a data-derived claim lacks post evidence."""
    needs_post_evidence = finding.evidence_type in DATA_EVIDENCE_TYPES
    has_post_evidence = bool(finding.evidence_post_ids)
    has_metric_evidence = bool(finding.metrics)

    if needs_post_evidence and not has_post_evidence and not has_metric_evidence:
        if finding.confidence > MAX_UNSUPPORTED_CONFIDENCE:
            logger.info(
                "Capping confidence %.2f → %.2f for unsupported finding: %s",
                finding.confidence, MAX_UNSUPPORTED_CONFIDENCE, finding.statement[:60],
            )
            finding.confidence = MAX_UNSUPPORTED_CONFIDENCE


def detect_conflicts(
    specialist_outputs: dict[str, tuple[SpecialistOutput | None, str | None]]
) -> list[Conflict]:
    """Detect disagreements between specialist recommendations."""
    conflicts = []

    action_topics: dict[str, dict[str, str]] = {}
    for agent_name, (output, _) in specialist_outputs.items():
        if output is None:
            continue
        for action in output.recommended_actions:
            topic_key = action.action.lower()[:50]
            action_topics.setdefault(topic_key, {})[agent_name] = action.action

    agents_with_output = {
        name: output for name, (output, _) in specialist_outputs.items() if output
    }

    POSITIVE_WORDS = {"increase", "more", "repeat", "continue", "double down", "scale"}
    NEGATIVE_WORDS = {"decrease", "less", "stop", "reduce", "avoid", "don't", "limit", "cut"}

    all_actions: list[tuple[str, str, str]] = []
    for name, output in agents_with_output.items():
        for action in output.recommended_actions:
            lower = action.action.lower()
            direction = "neutral"
            if any(w in lower for w in POSITIVE_WORDS):
                direction = "positive"
            elif any(w in lower for w in NEGATIVE_WORDS):
                direction = "negative"
            all_actions.append((name, action.action, direction))

    for i, (name_a, action_a, dir_a) in enumerate(all_actions):
        for name_b, action_b, dir_b in all_actions[i + 1:]:
            if name_a == name_b:
                continue
            if dir_a == "neutral" or dir_b == "neutral":
                continue
            if dir_a == dir_b:
                continue
            words_a = set(action_a.lower().split()) - {"the", "a", "an", "to", "and", "or", "in", "of", "for", "is"}
            words_b = set(action_b.lower().split()) - {"the", "a", "an", "to", "and", "or", "in", "of", "for", "is"}
            shared_topic = words_a & words_b
            if len(shared_topic) >= 1:
                conflicts.append(Conflict(
                    agents=[name_a, name_b],
                    topic=", ".join(sorted(shared_topic)),
                    positions={name_a: action_a, name_b: action_b},
                ))

    for name, output in agents_with_output.items():
        if not output.warnings:
            continue
        for other_name, other_output in agents_with_output.items():
            if other_name == name or not other_output:
                continue
            for warning in output.warnings:
                for other_action in other_output.recommended_actions:
                    warning_lower = warning.lower()
                    action_lower = other_action.action.lower()
                    overlap_words = set(warning_lower.split()) & set(action_lower.split())
                    meaningful_overlap = overlap_words - {"the", "a", "an", "is", "to", "and", "or", "in", "of", "for"}
                    if len(meaningful_overlap) >= 2:
                        conflicts.append(Conflict(
                            agents=[name, other_name],
                            topic=f"{name} warns about {other_name}'s recommendation",
                            positions={name: f"Warning: {warning}", other_name: f"Recommends: {other_action.action}"},
                        ))

    return conflicts


SYNTHESIS_PROMPT = """You are the Manager for Kobby Cooper's talent management team.

Your specialist agents have provided their analysis. Synthesize their findings into a final decision.

Decision type: {decision_type}
Original request: {request}

SPECIALIST OUTPUTS:
{specialist_summaries}

{conflict_section}

INSTRUCTIONS:
1. Weigh all specialist findings by their confidence levels and evidence strength.
2. If specialists disagree, explain WHY you sided with one over the other.
3. Your decision must include specific, actionable next steps.
4. Cite evidence (post IDs, metrics) from the specialist outputs.
5. Be honest about overall confidence — if evidence is thin, say so.

Return valid JSON matching this structure:
{{
  "decision": "Clear statement of what to do",
  "reasoning": "Why this is the right move, addressing any conflicts",
  "agents_consulted": ["list", "of", "agents"],
  "conflicts_detected": [
    {{"agents": ["agent1", "agent2"], "topic": "what they disagreed on", "positions": {{"agent1": "position", "agent2": "position"}}}}
  ],
  "conflict_resolution": "How you resolved the disagreement (null if no conflicts)",
  "recommended_actions": [
    {{"action": "specific action", "reasoning": "why", "priority": 1, "expected_outcome": "what should happen"}}
  ],
  "evidence_post_ids": [1, 2, 3],
  "evidence_memory_ids": [],
  "metrics_considered": ["views", "follow_rate"],
  "confidence": 0.75
}}"""


async def synthesize_decision(
    decision_type: str,
    request: str,
    specialist_outputs: dict[str, tuple[SpecialistOutput | None, str | None]],
    conflicts: list[Conflict],
    db: AsyncSession,
    creator_id: int,
) -> ManagerDecisionOutput:
    """Have the Manager synthesize specialist outputs into a final decision."""
    specialist_summaries = []
    for name, (output, error) in specialist_outputs.items():
        if output is None:
            specialist_summaries.append(f"\n{name.upper()} AGENT: FAILED ({error})")
            continue
        summary = f"\n{name.upper()} AGENT:"
        if output.findings:
            summary += "\nFindings:"
            for f in output.findings:
                summary += f"\n  - {f.statement} (confidence: {f.confidence}, evidence: {f.evidence_post_ids}, metrics: {f.metrics})"
        if output.recommended_actions:
            summary += "\nRecommended actions:"
            for a in output.recommended_actions:
                summary += f"\n  - [{a.priority}] {a.action}: {a.reasoning}"
        if output.warnings:
            summary += f"\nWarnings: {', '.join(output.warnings)}"
        specialist_summaries.append(summary)

    conflict_section = ""
    if conflicts:
        conflict_section = "CONFLICTS DETECTED:\n"
        for c in conflicts:
            conflict_section += f"- {' vs '.join(c.agents)} on {c.topic}:\n"
            for agent, pos in c.positions.items():
                conflict_section += f"    {agent}: {pos}\n"
        conflict_section += "\nYou MUST address each conflict and explain your resolution."

    prompt = SYNTHESIS_PROMPT.format(
        decision_type=decision_type,
        request=request,
        specialist_summaries="\n".join(specialist_summaries),
        conflict_section=conflict_section,
    )

    response = await complete(
        messages=[{"role": "user", "content": prompt}],
        tier=CostTier.STRATEGY,
        max_tokens=4096,
    )

    try:
        import re
        text = response.text.strip()
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fence_match:
            data = json.loads(fence_match.group(1))
        else:
            data = json.loads(text)
        return ManagerDecisionOutput.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning("Manager synthesis returned invalid JSON: %s", e)
        return ManagerDecisionOutput(
            decision=response.text[:500],
            reasoning="Manager returned unstructured response",
            agents_consulted=list(specialist_outputs.keys()),
            conflicts_detected=conflicts,
            confidence=0.3,
        )


async def orchestrate(
    request: str,
    context: dict[str, Any],
    db: AsyncSession,
    creator_id: int,
) -> dict[str, Any]:
    """Full orchestration pipeline: classify → route → dispatch → detect conflicts → synthesize → record."""
    decision_type = classify_request(request)
    if decision_type is None:
        decision_type = await classify_request_llm(request)

    logger.info("Orchestrating: type=%s, request='%s'", decision_type, request[:80])

    specialist_outputs = await consult_specialists(
        decision_type, request, context, db, creator_id,
    )

    specialist_outputs = await validate_specialist_evidence(specialist_outputs, db)

    conflicts = detect_conflicts(specialist_outputs)
    if conflicts:
        logger.info("Conflicts detected: %d", len(conflicts))

    active_agents = [
        name for name, (output, _) in specialist_outputs.items() if output is not None
    ]
    failed_agents = [
        name for name, (output, error) in specialist_outputs.items() if output is None and error
    ]

    if not active_agents:
        return {
            "decision_type": decision_type,
            "error": "All consulted agents failed",
            "failed_agents": failed_agents,
        }

    decision = await synthesize_decision(
        decision_type, request, specialist_outputs, conflicts, db, creator_id,
    )

    valid_evidence = []
    for name, (output, _) in specialist_outputs.items():
        if output:
            for finding in output.findings:
                valid_evidence.extend(finding.evidence_post_ids)
    valid_evidence = list(set(valid_evidence))

    agent_outputs_serialized = {}
    for name, (output, error) in specialist_outputs.items():
        agent_outputs_serialized[name] = {
            "output": output.model_dump() if output else None,
            "error": error,
        }

    record = ManagerDecision(
        creator_id=creator_id,
        decision_type=decision_type,
        request_context=request,
        agents_consulted=list(specialist_outputs.keys()),
        agent_outputs=agent_outputs_serialized,
        conflicts_detected=[c.model_dump() for c in conflicts] if conflicts else None,
        final_decision=decision.decision,
        final_reasoning=decision.reasoning,
        evidence_post_ids=valid_evidence,
        evidence_memory_ids=decision.evidence_memory_ids,
        metrics_considered=decision.metrics_considered,
        confidence=decision.confidence,
    )
    db.add(record)
    await db.flush()

    for action in decision.recommended_actions:
        rec = Recommendation(
            creator_id=creator_id,
            agent="manager",
            category=decision_type,
            summary=action.action,
            detail=action.expected_outcome,
            reasoning=action.reasoning,
            evidence_post_ids=valid_evidence,
            evidence_memory_ids=decision.evidence_memory_ids,
            metrics_considered=decision.metrics_considered,
            confidence=decision.confidence,
            priority=action.priority,
            status="pending",
            outcome_window_days=7,
            outcome_measured=False,
            manager_decision_id=record.id,
        )
        db.add(rec)

    await db.commit()

    return {
        "decision_type": decision_type,
        "agents_consulted": list(specialist_outputs.keys()),
        "agents_succeeded": active_agents,
        "agents_failed": failed_agents,
        "conflicts": [c.model_dump() for c in conflicts],
        "decision": decision.decision,
        "reasoning": decision.reasoning,
        "conflict_resolution": decision.conflict_resolution,
        "recommended_actions": [a.model_dump() for a in decision.recommended_actions],
        "evidence_post_ids": valid_evidence,
        "confidence": decision.confidence,
        "decision_record_id": record.id,
    }


async def orchestrate_daily_brief(
    context: dict[str, Any],
    db: AsyncSession,
    creator_id: int,
) -> dict[str, Any]:
    """Selective daily brief — run cheap checks first, only call agents when needed."""
    triggers = _detect_brief_triggers(context)

    if not triggers:
        agents_needed = ["growth", "content"]
        trigger_summary = "Routine daily check"
    else:
        agents_needed = set()
        for trigger in triggers:
            agents_needed.update(trigger["agents"])
        agents_needed = list(agents_needed)
        trigger_summary = "; ".join(t["reason"] for t in triggers)

    logger.info("Daily brief triggers: %s → agents: %s", trigger_summary, agents_needed)

    specialist_outputs = {}
    agent_map = _build_agent_map(creator_id)

    brief_task = f"""Generate your specialist input for today's daily brief.

Triggers detected: {trigger_summary}

Analyze the current context and provide:
- Key findings relevant to today's decisions
- Specific actions Kobby should take today
- Any warnings or opportunities

Return structured JSON."""

    tasks = []
    for name in agents_needed:
        agent = agent_map.get(name)
        schema = AGENT_SCHEMA_MAP.get(name, SpecialistOutput)
        if agent:
            tasks.append(_dispatch_specialist(agent, name, brief_task, context, schema))

    results_list = await asyncio.gather(*tasks)
    for name, output, error in results_list:
        specialist_outputs[name] = (output, error)

    specialist_outputs = await validate_specialist_evidence(specialist_outputs, db)

    conflicts = detect_conflicts(specialist_outputs)

    decision = await synthesize_decision(
        "daily_brief", "Generate today's daily brief", specialist_outputs, conflicts, db, creator_id,
    )

    record = ManagerDecision(
        creator_id=creator_id,
        decision_type="daily_brief",
        request_context=trigger_summary,
        agents_consulted=agents_needed,
        agent_outputs={
            name: {"output": o.model_dump() if o else None, "error": e}
            for name, (o, e) in specialist_outputs.items()
        },
        conflicts_detected=[c.model_dump() for c in conflicts] if conflicts else None,
        final_decision=decision.decision,
        final_reasoning=decision.reasoning,
        confidence=decision.confidence,
    )
    db.add(record)
    await db.commit()

    return {
        "triggers": triggers,
        "agents_consulted": agents_needed,
        "conflicts": [c.model_dump() for c in conflicts],
        "decision": decision.decision,
        "recommended_actions": [a.model_dump() for a in decision.recommended_actions],
        "confidence": decision.confidence,
    }


def _detect_brief_triggers(context: dict[str, Any]) -> list[dict]:
    """Cheap deterministic checks to decide which agents the daily brief needs."""
    triggers = []

    metrics = context.get("account_metrics", {})
    for username, snapshots in metrics.items():
        if not snapshots:
            continue
        latest = snapshots[0]
        delta = latest.get("followers_delta")
        if delta is not None and delta < -50:
            triggers.append({
                "reason": f"Follower drop: {delta} on @{username}",
                "agents": ["growth", "brand"],
                "severity": "high",
            })
        if delta is not None and delta > 200:
            triggers.append({
                "reason": f"Follower surge: +{delta} on @{username}",
                "agents": ["growth", "content"],
                "severity": "medium",
            })

    pending_recs = context.get("pending_recommendations", [])
    sponsorship_pending = any(
        "sponsor" in r.get("category", "").lower() or "business" in r.get("agent", "").lower()
        for r in pending_recs
    )
    if sponsorship_pending:
        triggers.append({
            "reason": "Pending sponsorship decisions",
            "agents": ["business", "brand"],
            "severity": "medium",
        })

    calendar = context.get("todays_calendar", [])
    if calendar:
        triggers.append({
            "reason": f"{len(calendar)} post(s) scheduled today",
            "agents": ["content"],
            "severity": "low",
        })

    recent_posts = context.get("recent_posts", [])
    if not recent_posts:
        triggers.append({
            "reason": "No recent posts found",
            "agents": ["content", "growth"],
            "severity": "medium",
        })

    return triggers
