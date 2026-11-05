"""Narration pipeline with fake completers: LLM text when valid, template otherwise."""

import asyncio
import json
import time

import anthropic
import httpx
import pytest

from ishi.teacher.llm import LLMError, system_prompt
from ishi.teacher.narrator import cache_key, finish_late, narrate, user_message
from ishi.teacher.templates import render
from ishi.why.fact_package import clean_package, learner_info
from tests.teacher.conftest import package_for
from tests.teacher.test_validator import CASE, good_en


class Fake:
    def __init__(self, answer: str | Exception) -> None:
        self.answer = answer
        self.calls: list[str] = []

    async def complete(self, user_message: str) -> str:
        self.calls.append(user_message)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


async def test_valid_llm_output_is_used() -> None:
    pkg = package_for(CASE)
    fake = Fake(json.dumps(good_en(pkg)))
    r = await narrate(pkg, fake)
    assert r.source == "llm" and r.reject_reason is None
    assert r.narration.headline == good_en(pkg)["headline"]
    assert "FACT PACKAGE" in fake.calls[0] and '"move_number"' not in fake.calls[0]


async def test_invalid_output_falls_back_to_the_template() -> None:
    pkg = package_for(CASE)
    bad = good_en(pkg) | {"takeaway": "Watch out for the ladder."}
    r = await narrate(pkg, Fake(json.dumps(bad)))
    assert r.source == "template" and r.reject_reason == "concept"
    assert r.narration == render(pkg) and r.raw is not None


@pytest.mark.parametrize(
    "error",
    [
        LLMError("stop_reason=refusal"),
        anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com")),
        TimeoutError(),
    ],
)
async def test_api_errors_fall_back_to_the_template(error: Exception) -> None:
    pkg = package_for(CASE)
    r = await narrate(pkg, Fake(error))
    assert r.source == "template" and r.reject_reason and r.reject_reason.startswith("error:")


class Slow(Fake):
    async def complete(self, user_message: str) -> str:
        await asyncio.sleep(5)
        return await super().complete(user_message)


async def test_slow_llm_is_cut_off_by_the_budget() -> None:
    pkg = package_for(CASE)
    t0 = time.perf_counter()
    r = await narrate(pkg, Slow(json.dumps(good_en(pkg))), budget=0.2)
    assert time.perf_counter() - t0 < 1.0
    assert r.source == "template" and r.reject_reason == "error:TimeoutError"
    fake = Fake(json.dumps(good_en(pkg)))
    r = await narrate(pkg, fake, budget=0)  # no time left: Claude is not asked
    assert r.source == "template" and r.reject_reason == "error:NoTime" and not fake.calls
    assert (await narrate(pkg, fake, budget=2.0)).source == "llm"


async def test_llm_disabled_and_clean_games_use_templates() -> None:
    pkg = package_for(CASE)
    assert (await narrate(pkg, None)).source == "template"
    from ishi.rules.board import Color

    clean = clean_package(
        locale="en", learner=learner_info("yellow", None), size=9, color=Color.BLACK
    )
    fake = Fake("{}")
    assert (await narrate(clean, fake)).source == "template" and not fake.calls


def test_cache_key_ignores_the_move_number_only() -> None:
    a, b = package_for(CASE, number=17), package_for(CASE, number=40)
    assert cache_key(a) == cache_key(b)
    assert cache_key(a) != cache_key(package_for(CASE, "th"))
    assert user_message(a) == user_message(b)


def test_system_prompt_is_static_and_has_every_guide() -> None:
    text = system_prompt()
    for concept in ("missed_capture", "ignored_atari", "self_atari", "ladder", "group_death"):
        assert f"## {concept}" in text
    assert "allowed_coordinates" in text


def test_the_answer_is_hidden_from_the_model() -> None:
    pkg = package_for("missed_capture/mined_mine20_g01_m25")
    answer = pkg.correct_moves[0]
    msg = user_message(pkg)
    assert answer not in msg and "ANSWER" in msg and "Headline:" in msg
    assert answer in pkg.allowed_coordinates  # the package itself is unchanged


async def test_echoing_the_placeholder_is_rejected() -> None:
    pkg = package_for(CASE)
    bad = good_en(pkg)
    bad["explanation"][1] = "The opponent can capture them at ANSWER."
    r = await narrate(pkg, Fake(json.dumps(bad)))
    assert r.source == "template" and r.reject_reason == "reveals_answer"


async def test_a_mark_on_the_placeholder_is_dropped() -> None:
    pkg = package_for(CASE)
    marked = good_en(pkg) | {"marks": [{"point": "ANSWER", "kind": "circle", "label": None}]}
    r = await narrate(pkg, Fake(json.dumps(marked)))
    assert r.source == "llm" and r.narration.marks == []


class Later(Fake):
    async def complete(self, user_message: str) -> str:
        await asyncio.sleep(0.3)
        return await super().complete(user_message)


async def test_late_narration_is_kept_when_asked() -> None:
    pkg = package_for(CASE)
    r = await narrate(pkg, Later(json.dumps(good_en(pkg))), budget=0.05, keep_late=True)
    assert r.source == "template" and r.late is not None
    assert (await finish_late(pkg, r.late)).source == "llm"
    r = await narrate(pkg, Later(json.dumps(good_en(pkg))), budget=0.05)
    assert r.late is None


class Sequence(Fake):
    def __init__(self, *answers: str) -> None:
        super().__init__("")
        self.answers = list(answers)

    async def complete(self, user_message: str) -> str:
        self.calls.append(user_message)
        return self.answers.pop(0)


async def test_a_rejected_narration_is_retried_once_with_the_reason() -> None:
    pkg = package_for(CASE)
    long = good_en(pkg) | {"headline": " ".join(["word"] * 15)}
    fake = Sequence(json.dumps(long), json.dumps(good_en(pkg)))
    r = await narrate(pkg, fake)
    assert r.source == "llm" and r.retried == 1
    assert "rejected (length: headline has 15 words, max 12)" in fake.calls[1]
    fake = Sequence(json.dumps(long), json.dumps(long), json.dumps(good_en(pkg)))
    r = await narrate(pkg, fake)  # only one retry
    assert r.source == "template" and r.reject_reason == "length" and len(fake.calls) == 2


def test_the_model_sees_the_derived_variant() -> None:
    pkg = package_for("missed_capture/mined_mine20_g01_m25")
    two = pkg.groups[0].model_copy(update={"liberties_before": ["A1", "A2"]})
    short = pkg.model_copy(update={"groups": [two, *pkg.groups[1:]]})
    assert '"variant": "short"' in user_message(short)
    assert '"variant"' not in user_message(pkg)
