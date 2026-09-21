"""Manager Agent — the orchestrator. Sits above all specialised agents and makes final decisions.

The Manager no longer handles everything via a single LLM call.
It routes to specialists, collects structured evidence, resolves conflicts,
and synthesizes decisions. See app/services/orchestrator.py for the full pipeline.
"""
from __future__ import annotations
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import BaseAgent
from app.agents.llm import CostTier


class ManagerAgent(BaseAgent):
    name = "manager"
    default_tier = CostTier.STRATEGY

    def __init__(self, creator_id: int, db: AsyncSession):
        super().__init__(creator_id, db=db)

    def system_prompt(self) -> str:
        return """You are the AI Manager for Kobby Cooper — a digital talent manager.

You sit above six specialised agents: Growth, Content, Brand, Research, Community, Business.
They gather evidence and make recommendations. YOU decide what actually matters.

Your decision model:
1. OBSERVE — What happened?
2. DIAGNOSE — Why might it have happened?
3. COMPARE — What happened historically / externally?
4. HYPOTHESISE — What may improve it?
5. DECIDE — What's the highest-value next action?
6. EXECUTE — With approval where necessary.
7. MEASURE — Did it work?
8. LEARN — Update the creator playbook.

Your daily brief should tell Kobby EXACTLY what to do today:
- What to film
- What to post and when
- What to change on his profile
- Which comments to respond to
- What opportunities to pursue
- What to avoid

Core principles:
- Every recommendation gets recorded and later scored against outcomes.
- Distinguish viral content from brand-building content.
- Don't blindly chase fitness content because it performs.
- The brand goal: "People follow Kobby rather than merely following fitness content."
- Challenge Kobby when an idea doesn't serve the strategy.
- Be honest about evidence strength. Never make confident claims from small samples.
- You are NOT rewarded for generating recommendations. You are rewarded for improving
  Kobby's actual account outcomes.

Autonomy levels:
- Level 1 (Adviser): recommend only, Kobby executes everything.
- Level 2 (Copilot): create calendar, write drafts, analyse. Kobby approves.
- Level 3 (Manager): auto-handle internal tasks. Kobby approves public actions.
- Level 4 (Limited Autopilot): selected safe actions can be automated.

Default to Level 1. Escalate only when explicitly permitted."""

    async def orchestrate(
        self, request: str, context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        from app.services.orchestrator import orchestrate
        return await orchestrate(request, context or {}, self.db, self.creator_id)

    async def daily_brief(self, context: dict[str, Any]) -> dict[str, Any]:
        from app.services.orchestrator import orchestrate_daily_brief
        return await orchestrate_daily_brief(context, self.db, self.creator_id)

    async def weekly_review(self, context: dict[str, Any]) -> dict[str, Any]:
        from app.services.orchestrator import orchestrate
        return await orchestrate(
            "Conduct the weekly management review. Cover: what worked, what failed, why, "
            "audience changes, brand health, experiments, growth. Then provide STOP / START / CONTINUE "
            "and next week's strategy.",
            context, self.db, self.creator_id,
        )

    async def evaluate_draft(self, video_analysis: dict, context: dict[str, Any]) -> dict[str, Any]:
        from app.services.orchestrator import orchestrate
        return await orchestrate(
            "Review this draft video before posting. Evaluate opening strength, hook quality, "
            "pacing, CTA, and alignment with the intended objective. Provide specific improvements.",
            {**context, "video_analysis": video_analysis},
            self.db, self.creator_id,
        )
