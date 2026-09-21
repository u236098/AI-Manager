"""Model-agnostic LLM layer. Swap providers without touching agent code."""
from __future__ import annotations
import base64
from dataclasses import dataclass
from typing import Any
from app.config import get_settings


@dataclass
class LLMResponse:
    text: str
    usage: dict[str, int]
    model: str
    raw: Any = None


class CostTier:
    STRATEGY = "strategy"
    ANALYSIS = "analysis"
    ROUTINE = "routine"
    VISION = "vision"


def _resolve_model(tier: str) -> tuple[str, str]:
    s = get_settings()
    return {
        CostTier.STRATEGY: (s.strategy_provider, s.strategy_model),
        CostTier.ANALYSIS: (s.analysis_provider, s.analysis_model),
        CostTier.ROUTINE: (s.routine_provider, s.routine_model),
        CostTier.VISION: (s.vision_provider, s.vision_model),
    }[tier]


async def complete(
    messages: list[dict],
    tier: str = CostTier.ANALYSIS,
    system: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    json_mode: bool = False,
    provider: str | None = None,
    model: str | None = None,
) -> LLMResponse:
    if provider is None or model is None:
        resolved_provider, resolved_model = _resolve_model(tier)
        provider = provider or resolved_provider
        model = model or resolved_model

    if provider == "anthropic":
        return await _anthropic_complete(
            messages, model, system, temperature, max_tokens, json_mode
        )
    elif provider == "openai":
        return await _openai_complete(
            messages, model, system, temperature, max_tokens, json_mode
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")


async def analyze_images(
    images: list[bytes],
    prompt: str,
    tier: str = CostTier.VISION,
    media_type: str = "image/jpeg",
) -> LLMResponse:
    """Send multiple images to a vision model in a single request."""
    provider, model = _resolve_model(tier)

    if provider == "anthropic":
        content: list[dict] = []
        for img in images:
            b64 = base64.standard_b64encode(img).decode()
            content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}})
        content.append({"type": "text", "text": prompt})
        messages = [{"role": "user", "content": content}]
        return await _anthropic_complete(messages, model, None, 0.2, 8192, False)
    elif provider == "openai":
        content = []
        for img in images:
            b64 = base64.standard_b64encode(img).decode()
            content.append({"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}})
        content.append({"type": "text", "text": prompt})
        messages = [{"role": "user", "content": content}]
        return await _openai_complete(messages, model, None, 0.2, 8192, False)
    else:
        raise ValueError(f"Unknown provider: {provider}")


async def analyze_image(
    image_bytes: bytes,
    prompt: str,
    tier: str = CostTier.VISION,
    media_type: str = "image/jpeg",
) -> LLMResponse:
    """Convenience wrapper for single-image analysis."""
    return await analyze_images([image_bytes], prompt, tier, media_type)


async def transcribe(audio_bytes: bytes, filename: str = "audio.mp3") -> str:
    """Transcribe audio using OpenAI's transcription model."""
    import openai
    import io

    s = get_settings()
    client = openai.AsyncOpenAI(api_key=s.openai_api_key)
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename
    response = await client.audio.transcriptions.create(
        model=s.transcribe_model,
        file=audio_file,
    )
    return response.text


async def _anthropic_complete(
    messages: list[dict],
    model: str,
    system: str | None,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> LLMResponse:
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if system:
        kwargs["system"] = system

    response = await client.messages.create(**kwargs)
    text = response.content[0].text
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    return LLMResponse(text=text, usage=usage, model=model, raw=response)


async def _openai_complete(
    messages: list[dict],
    model: str,
    system: str | None,
    temperature: float,
    max_tokens: int,
    json_mode: bool,
) -> LLMResponse:
    import openai

    client = openai.AsyncOpenAI(api_key=get_settings().openai_api_key)
    all_messages = []
    if system:
        all_messages.append({"role": "system", "content": system})
    all_messages.extend(messages)

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": all_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = await client.chat.completions.create(**kwargs)
    text = response.choices[0].message.content or ""
    usage = {
        "input_tokens": response.usage.prompt_tokens if response.usage else 0,
        "output_tokens": response.usage.completion_tokens if response.usage else 0,
    }
    return LLMResponse(text=text, usage=usage, model=model, raw=response)
