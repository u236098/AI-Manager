"""Base agent class. All specialised agents inherit from this."""
from __future__ import annotations
import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import complete, CostTier, LLMResponse

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    name: str = "base"
    default_tier: str = CostTier.ANALYSIS

    def __init__(self, creator_id: int, db: AsyncSession | None = None):
        self.db = db
        self.creator_id = creator_id

    @abstractmethod
    def system_prompt(self) -> str:
        """Return the agent's system prompt."""

    async def run(self, task: str, context: dict[str, Any] | None = None, **kwargs) -> dict[str, Any]:
        system = self.system_prompt()
        if context:
            system += f"\n\nCurrent context:\n```json\n{json.dumps(context, default=str, indent=2)}\n```"

        messages = [{"role": "user", "content": task}]
        tier = kwargs.pop("tier", self.default_tier)

        response = await complete(
            messages=messages,
            system=system,
            tier=tier,
            **kwargs,
        )

        logger.info(
            "Agent %s used %s tokens (in=%d, out=%d)",
            self.name, response.model,
            response.usage.get("input_tokens", 0),
            response.usage.get("output_tokens", 0),
        )

        return self._parse_response(response)

    def _parse_response(self, response: LLMResponse) -> dict[str, Any]:
        text = response.text.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return {"parsed": json.loads(text), "raw": text, "usage": response.usage}
            except json.JSONDecodeError:
                pass
        return {"raw": text, "usage": response.usage}

    async def run_json(self, task: str, context: dict[str, Any] | None = None, **kwargs) -> dict[str, Any]:
        result = await self.run(task, context, json_mode=True, **kwargs)
        if "parsed" in result:
            return result["parsed"]
        try:
            return json.loads(result["raw"])
        except json.JSONDecodeError:
            return {"error": "Failed to parse JSON response", "raw": result["raw"]}

    async def run_validated(
        self, task: str, schema: type[T], context: dict[str, Any] | None = None, **kwargs
    ) -> T:
        """Run agent and validate output against a Pydantic schema.

        Tries to extract JSON from the response (including from markdown
        code fences) and validates it. Raises ValidationError on failure.
        """
        result = await self.run(task, context, **kwargs)
        raw = result.get("raw", "")

        data = result.get("parsed")
        if data is None:
            fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
            if fence_match:
                data = json.loads(fence_match.group(1))
            else:
                data = json.loads(raw)

        return schema.model_validate(data)
