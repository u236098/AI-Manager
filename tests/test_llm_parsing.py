"""Tests for LLM response parsing and validated output."""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import BaseModel, ValidationError
from app.agents.llm import LLMResponse
from app.agents.base import BaseAgent


class DummyAgent(BaseAgent):
    name = "test"

    def system_prompt(self) -> str:
        return "You are a test agent."


class SimpleOutput(BaseModel):
    score: int
    reasoning: str


def test_parse_clean_json():
    agent = DummyAgent(creator_id=1)
    response = LLMResponse(text='{"score": 7, "reasoning": "good"}', usage={"input_tokens": 10, "output_tokens": 20}, model="test")
    result = agent._parse_response(response)
    assert "parsed" in result
    assert result["parsed"]["score"] == 7


def test_parse_plain_text():
    agent = DummyAgent(creator_id=1)
    response = LLMResponse(text="This is a plain text response.", usage={"input_tokens": 10, "output_tokens": 20}, model="test")
    result = agent._parse_response(response)
    assert "parsed" not in result
    assert "raw" in result


def test_parse_malformed_json():
    agent = DummyAgent(creator_id=1)
    response = LLMResponse(text='{"score": 7, "reasoning": "incomplete', usage={"input_tokens": 10, "output_tokens": 20}, model="test")
    result = agent._parse_response(response)
    assert "parsed" not in result


@patch("app.agents.base.complete")
async def test_run_validated_clean_json(mock_complete):
    mock_complete.return_value = LLMResponse(
        text='{"score": 8, "reasoning": "great content"}',
        usage={"input_tokens": 10, "output_tokens": 20},
        model="test",
    )
    agent = DummyAgent(creator_id=1)
    result = await agent.run_validated("Rate this", SimpleOutput)
    assert isinstance(result, SimpleOutput)
    assert result.score == 8


@patch("app.agents.base.complete")
async def test_run_validated_fenced_json(mock_complete):
    mock_complete.return_value = LLMResponse(
        text='Here is the result:\n```json\n{"score": 5, "reasoning": "ok"}\n```',
        usage={"input_tokens": 10, "output_tokens": 20},
        model="test",
    )
    agent = DummyAgent(creator_id=1)
    result = await agent.run_validated("Rate this", SimpleOutput)
    assert result.score == 5


@patch("app.agents.base.complete")
async def test_run_validated_rejects_bad_output(mock_complete):
    mock_complete.return_value = LLMResponse(
        text='{"score": "not a number", "reasoning": 123}',
        usage={"input_tokens": 10, "output_tokens": 20},
        model="test",
    )
    agent = DummyAgent(creator_id=1)
    with pytest.raises(ValidationError):
        await agent.run_validated("Rate this", SimpleOutput)
