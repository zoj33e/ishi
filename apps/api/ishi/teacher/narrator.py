"""Narration pipeline (06-teacher-llm): template always, Claude when enabled, validator in between.

FactPackage -> template narration (always)
FactPackage -> Claude -> validate -> final narration; invalid or error -> template
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, replace
from typing import Any, Literal, Protocol

import anthropic

from ishi.teacher.llm import LLMError
from ishi.teacher.narration import Narration
from ishi.teacher.templates import render, template_variant
from ishi.teacher.validator import Rejected, validate
from ishi.why.fact_package import FactPackage

log = logging.getLogger("ishi.teacher")

Source = Literal["llm", "template"]


class Completer(Protocol):
    async def complete(self, user_message: str) -> str: ...


@dataclass(frozen=True)
class NarrationResult:
    narration: Narration
    source: Source
    reject_reason: str | None = None  # why the model's narration wasn't used
    raw: str | None = None  # the model's raw output, if any
    late: asyncio.Future[NarrationResult] | None = None  # still running after its budget
    detail: str | None = None  # the validator's detail for a reject
    retried: int = 0  # how many times Claude was asked again after a reject


ANSWER = "ANSWER"  # stands in for the correct move's coordinate in what the model sees


def _hide(value: Any, answers: set[str]) -> Any:
    if isinstance(value, dict):
        return {k: _hide(v, answers) for k, v in value.items()}
    if isinstance(value, list):
        return [_hide(v, answers) for v in value]
    if isinstance(value, str):
        parts = value.split(" ")  # "W D2" in follow_up_line
        if parts[-1] in answers:
            return " ".join([*parts[:-1], ANSWER])
    return value


def model_input(pkg: FactPackage) -> dict:
    """What the model sees: the package minus the move number (it never needs to say it). In a
    mistake lesson the learner must find the move, so its coordinate is replaced by "ANSWER"
    everywhere (the model can't name or mark what it never sees)."""
    data = pkg.model_dump(exclude={"move_number"}, exclude_none=True)
    variant = template_variant(pkg)  # e.g. missed_capture "short": not capturable in one move
    if variant and pkg.lesson_type != "praise":
        data["variant"] = variant
    if pkg.lesson_type in ("mistake", "nudge") and pkg.correct_moves:
        answers = set(pkg.correct_moves)
        data = _hide(data, answers)
        data["allowed_coordinates"] = [c for c in pkg.allowed_coordinates if c not in answers]
    return data


def _reminder(pkg: FactPackage) -> str:
    if pkg.locale == "th":
        size = "at most 40 Thai characters (about 6-8 words)"
    else:
        size = "at most 12 words (aim for 6-9)"
    lines = [f"Headline: one short title, {size}."]
    if pkg.lesson_type in ("mistake", "nudge"):
        lines.append(
            f'{ANSWER} is the move the learner must find: describe it in words ("the last'
            ' liberty", "the cutting point"), never write it, never mark it.'
        )
    return "\n".join(lines)


def user_message(pkg: FactPackage) -> str:
    facts = json.dumps(model_input(pkg), ensure_ascii=False, indent=1)
    return f"FACT PACKAGE:\n{facts}\n\n{_reminder(pkg)}"


def cache_key(pkg: FactPackage) -> str:
    """Same facts (any move number) -> same narration (06: cache by hash(FactPackage))."""
    data = json.dumps(model_input(pkg), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def uses_llm(pkg: FactPackage) -> bool:
    """A clean-game summary has no facts to rewrite: the template is the lesson."""
    return pkg.lesson_type in ("mistake", "praise")


LLM_ERRORS = (anthropic.APIError, LLMError, TimeoutError)
RETRIES = 1  # a rejected narration is asked for once more, with the reason


def _checked(raw: str, pkg: FactPackage, template: Narration) -> NarrationResult:
    try:
        return NarrationResult(validate(raw, pkg), "llm", None, raw)
    except Rejected as e:
        log.warning("narration rejected (%s): %s", e, raw)
        return NarrationResult(template, "template", e.reason, raw, detail=e.detail)


async def _ask(pkg: FactPackage, llm: Completer, template: Narration) -> NarrationResult:
    """Claude, the validator, and one retry that names the broken rule."""
    message = user_message(pkg)
    result = _checked(await llm.complete(message), pkg, template)
    for attempt in range(RETRIES):
        if result.source == "llm":
            break
        retry = (
            f"{message}\n\nYour previous answer was rejected ({result.reject_reason}: "
            f"{result.detail}). Write the whole JSON again and fix that."
        )
        result = _checked(await llm.complete(retry), pkg, template)
        result = replace(result, retried=attempt + 1)
    return result


async def narrate(
    pkg: FactPackage, llm: Completer | None, budget: float | None = None, keep_late: bool = False
) -> NarrationResult:
    """`budget`: seconds Claude may take before the template is used (None = the client's own
    timeout); a budget of 0 or less skips Claude. With `keep_late`, work that runs out of budget
    keeps going and is returned as `late` (see `finish_late`)."""
    template = render(pkg)
    if llm is None or not uses_llm(pkg):
        return NarrationResult(template, "template")
    if budget is not None and budget <= 0:
        return NarrationResult(template, "template", "error:NoTime")
    task = asyncio.ensure_future(_ask(pkg, llm, template))
    try:
        return await asyncio.wait_for(asyncio.shield(task), budget)
    except TimeoutError:
        if not keep_late:
            task.cancel()
        log.info("narration over budget (%.1f s)%s", budget or 0, "; keeps going" * keep_late)
        late = task if keep_late else None
        return NarrationResult(template, "template", "error:TimeoutError", late=late)
    except LLM_ERRORS as e:
        log.warning("narration failed: %s", type(e).__name__)
        return NarrationResult(template, "template", f"error:{type(e).__name__}")


async def finish_late(pkg: FactPackage, late: asyncio.Future[NarrationResult]) -> NarrationResult:
    """Wait for narration that ran out of budget (already validated)."""
    try:
        return await late
    except LLM_ERRORS as e:
        log.warning("late narration failed: %s", type(e).__name__)
        return NarrationResult(render(pkg), "template", f"error:{type(e).__name__}")
