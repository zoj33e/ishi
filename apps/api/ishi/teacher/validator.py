"""Validator for model narration (06-teacher-llm). Anything it rejects falls back to the template.

The LLM never judges the board, so the validator only checks that the text stays inside the facts:
schema and lengths, coordinates, concept words, numbers and language.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import ValidationError

from ishi.rules.coords import gtp_to_point
from ishi.teacher.narration import Narration
from ishi.why.fact_package import FactPackage

KEYWORDS_FILE = Path(__file__).parent / "concept_keywords.yaml"
COORD = re.compile(r"(?<![A-Za-z0-9])([A-Za-z])([0-9]{1,2})(?![A-Za-z0-9])")
NUMBER = re.compile(r"\d+(?:\.\d+)?")
THAI = re.compile(r"[฀-๿]")
LATIN = re.compile(r"[A-Za-z]")
HEADLINE_WORDS_EN = 12
HEADLINE_CHARS_TH = 40
MAX_SENTENCE_CHARS = 220
EXPLANATION_SENTENCES = (2, 4)
TEACHING_HINTS = 2
ALWAYS_ALLOWED_NUMBERS = {"1", "2"}  # "one liberty", "two eyes": rules facts, not board facts
THAI_SHARE = 0.7  # of the letters in each text of a Thai narration
PRAISE_CONCEPT = {"answered_atari": "ignored_atari", "answered_cut": "cut_disconnect"}


class Rejected(Exception):
    """The narration breaks a rule; `reason` is a short code for logs and the reject rate."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


@lru_cache
def concept_keywords() -> dict[str, dict[str, list[str]]]:
    return yaml.safe_load(KEYWORDS_FILE.read_text(encoding="utf-8"))


def validate(raw: str, pkg: FactPackage) -> Narration:
    """Parse and check the model's JSON; raise `Rejected` on the first broken rule."""
    try:
        narration = Narration.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as e:
        raise Rejected("schema", str(e)[:200]) from e
    # A mark on the hidden answer is decoration that would give it away: drop it, keep the rest.
    narration = narration.model_copy(
        update={"marks": [m for m in narration.marks if m.point != "ANSWER"]}
    )
    _check_lengths(narration, pkg)
    _check_placeholder(narration)
    _check_coordinates(narration, pkg)
    _check_concepts(narration, pkg)
    _check_numbers(narration, pkg)
    _check_language(narration, pkg)
    return narration


def _check_placeholder(n: Narration) -> None:
    """The model sees the answer as "ANSWER" (narrator.model_input); it must never echo it."""
    if any("ANSWER" in t for t in n.texts()):
        raise Rejected("reveals_answer", "ANSWER placeholder")


def _check_lengths(n: Narration, pkg: FactPackage) -> None:
    if pkg.locale == "th":
        if len(n.headline) > HEADLINE_CHARS_TH:
            raise Rejected(
                "length", f"headline has {len(n.headline)} characters, max {HEADLINE_CHARS_TH}"
            )
    elif len(n.headline.split()) > HEADLINE_WORDS_EN:
        raise Rejected(
            "length", f"headline has {len(n.headline.split())} words, max {HEADLINE_WORDS_EN}"
        )
    lo, hi = EXPLANATION_SENTENCES
    if not lo <= len(n.explanation) <= hi:
        raise Rejected("length", f"{len(n.explanation)} explanation sentences")
    if any(not s.strip() for s in n.texts()):
        raise Rejected("length", "empty text")
    if any(len(s) > MAX_SENTENCE_CHARS for s in n.texts()):
        raise Rejected("length", f"a sentence is over {MAX_SENTENCE_CHARS} characters")
    teaching = pkg.lesson_type in ("mistake", "nudge")
    if teaching and len(n.hints) != TEACHING_HINTS:
        raise Rejected("length", f"{len(n.hints)} hints")
    if teaching and not n.question:
        raise Rejected("length", "no question")


def _coords_in(text: str) -> list[str]:
    return [(m.group(1) + m.group(2)) for m in COORD.finditer(text)]


def _check_coordinates(n: Narration, pkg: FactPackage) -> None:
    allowed = set(pkg.allowed_coordinates)
    for text in n.texts():
        for c in _coords_in(text):
            if c not in allowed:
                raise Rejected("coordinate", c)
    for m in n.marks:
        if m.point not in allowed or gtp_to_point(m.point, pkg.board_size) is None:
            raise Rejected("coordinate", f"mark {m.point}")
    if pkg.lesson_type in ("mistake", "nudge"):
        # The answer comes from the retry, never from the explanation, hints or marks.
        hidden = set(pkg.correct_moves)
        before_answer = [n.headline, *n.explanation, n.question or "", *n.hints]
        shown = {c for t in before_answer for c in _coords_in(t)} | {m.point for m in n.marks}
        if shown & hidden:
            raise Rejected("reveals_answer", ", ".join(sorted(shown & hidden)))


def _own_concepts(pkg: FactPackage) -> set[str]:
    own = set(pkg.secondary_concepts)
    if pkg.concept_id:
        own.add(pkg.concept_id)
    if pkg.praise_kind in PRAISE_CONCEPT:
        own.add(PRAISE_CONCEPT[pkg.praise_kind])
    return own


def _check_concepts(n: Narration, pkg: FactPackage) -> None:
    table = concept_keywords()
    own = _own_concepts(pkg)
    text = " ".join(n.texts())
    if pkg.locale == "th":
        for word in table.get("th_ignore", []):
            text = text.replace(word, " ")
    for concept, words in table.items():
        if concept == "th_ignore" or concept in own:
            continue
        # both languages: a Thai narration may slip in an English term ("ko", "(ladder)")
        for w in [*words.get("en", []), *words.get("th", [])] if isinstance(words, dict) else []:
            if _mentions(text, w, pkg.locale):
                raise Rejected("concept", f"{concept}: {w}")


def _mentions(text: str, word: str, locale: str) -> bool:
    if THAI.search(word):
        return word in text
    pattern = rf"(?<![A-Za-z-]){re.escape(word)}(?![A-Za-z-])"
    return re.search(pattern, text, re.IGNORECASE) is not None


def allowed_numbers(pkg: FactPackage) -> set[str]:
    nums = set(ALWAYS_ALLOWED_NUMBERS)
    for g in pkg.groups:
        nums |= {str(len(g.stones)), str(len(g.liberties_before)), str(len(g.liberties_after))}
    if pkg.points_lost is not None:
        p = pkg.points_lost
        nums |= {str(round(p)), str(int(p)), str(int(p) + 1), f"{p:.1f}"}
    return nums


def _check_numbers(n: Narration, pkg: FactPackage) -> None:
    allowed = allowed_numbers(pkg)
    for text in n.texts():
        for num in NUMBER.findall(COORD.sub(" ", text)):
            if num not in allowed:
                raise Rejected("number", num)


def _check_language(n: Narration, pkg: FactPackage) -> None:
    # Per text, so one English sentence can't hide in a Thai narration. In Thai, coordinates and
    # glossary terms in parentheses, e.g. "อาตาริ (atari)", are Latin by design; English has no
    # such exception (no "(บันได)").
    for raw in n.texts():
        text = COORD.sub(" ", raw)
        if pkg.locale == "th":
            text = re.sub(r"\([^)]*\)", " ", text)
        thai, latin = len(THAI.findall(text)), len(LATIN.findall(text))
        if pkg.locale == "th":
            if thai < THAI_SHARE * (thai + latin):
                raise Rejected("language", f"not Thai enough: {raw}")
        elif thai > 0:
            raise Rejected("language", f"Thai in English narration: {raw}")
