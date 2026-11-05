"""Claude adapter for lesson narration (06-teacher-llm). The only module that talks to the API.

The system prompt and every concept guide form one static, cached prefix; the user message is the
FactPackage JSON. Output is constrained to the Narration JSON schema. The API key is never logged.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import anthropic

from ishi.teacher.narration import NARRATION_SCHEMA

log = logging.getLogger("ishi.teacher.llm")

PROMPTS_DIR = Path(__file__).parent / "prompts"
MAX_TOKENS = 1500  # Thai JSON is token-heavy; the contract keeps real output far below this
TIMEOUT_SECONDS = 8.0


@lru_cache
def system_prompt() -> str:
    guides = sorted((PROMPTS_DIR / "concepts").glob("*.md"))
    parts = [(PROMPTS_DIR / "system.md").read_text(encoding="utf-8")]
    parts += [g.read_text(encoding="utf-8") for g in guides]
    return "\n\n".join(p.strip() for p in parts) + "\n"


class TeacherLLM:
    """`complete(user_message)` returns the model's raw JSON text (validated by the caller)."""

    def __init__(self, api_key: str, model: str, *, timeout: float = TIMEOUT_SECONDS) -> None:
        self.model = model
        self.failing = False  # the last call errored (reported by /health)
        self._client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout, max_retries=1)

    async def complete(self, user_message: str) -> str:
        try:
            text = await self._complete(user_message)
        except (anthropic.APIError, LLMError):
            self.failing = True
            raise
        self.failing = False
        return text

    async def _complete(self, user_message: str) -> str:
        response = await self._client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": system_prompt(),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message}],
            # Rewriting facts needs no reasoning; thinking off keeps the lesson fast.
            thinking={"type": "disabled"},
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": NARRATION_SCHEMA},
            },
        )
        usage = response.usage
        log.debug(
            "narration id=%s stop=%s in=%s cached=%s out=%s",
            response.id,
            response.stop_reason,
            usage.input_tokens,
            usage.cache_read_input_tokens,
            usage.output_tokens,
        )
        if response.stop_reason != "end_turn":
            raise LLMError(f"stop_reason={response.stop_reason}")
        return next(b.text for b in response.content if b.type == "text")

    async def close(self) -> None:
        await self._client.close()


class LLMError(Exception):
    """The model didn't give a usable answer (refusal, truncation)."""
