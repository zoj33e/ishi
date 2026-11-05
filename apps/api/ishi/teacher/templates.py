"""Template narration (06-teacher-llm): fills `templates/{concept}.{locale}.yaml` from the facts.

Templates alone must give an acceptable lesson in both languages; the LLM only improves the wording.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ishi.teacher.narration import Mark, Narration
from ishi.why.fact_package import FactPackage

TEMPLATES_DIR = Path(__file__).parent / "templates"
FIELDS = ("headline", "explanation", "new_term", "question", "hints", "takeaway")
MAX_GROUP_MARKS = 8


@lru_cache
def load_template(name: str, locale: str) -> dict[str, Any]:
    data = yaml.safe_load((TEMPLATES_DIR / f"{name}.{locale}.yaml").read_text(encoding="utf-8"))
    assert set(data) <= {*FIELDS, "variants"}, f"{name}.{locale}: unknown fields"
    return data


def template_name(pkg: FactPackage) -> str:
    if pkg.lesson_type == "praise":
        return "praise"
    if pkg.lesson_type == "clean" or pkg.concept_id is None:
        return "clean"
    return pkg.concept_id


def template_variant(pkg: FactPackage) -> str | None:
    """The detector's variant, or one derived from the facts (e.g. capture from atari or not)."""
    if pkg.lesson_type == "praise":
        return pkg.praise_kind
    if pkg.concept_id == "missed_capture" and pkg.groups:
        return None if len(pkg.groups[0].liberties_before) <= 1 else "short"
    return pkg.variant


def slots(pkg: FactPackage) -> dict[str, str]:
    size = len(pkg.groups[0].stones) if pkg.groups else 0
    out = {
        "played_move": pkg.played_move or "",
        "threat_move": pkg.threat_move or "",
        "size": str(size),
    }
    if pkg.locale == "th":
        out["stones"] = out["a_stones"] = f"{size} เม็ด"
    else:
        one = size == 1  # English agreement: "your stone ... it was", "your 3 stones ... they were"
        out.update(
            stones="stone" if one else f"{size} stones",
            a_stones="a stone" if one else f"{size} stones",
            marked="marked with a triangle" if one else "marked with triangles",
            they="it" if one else "they",
            them="it" if one else "them",
            were="was" if one else "were",
            are="is" if one else "are",
            get="gets" if one else "get",
            do="does" if one else "do",
        )
    out.update(pkg.key_points)
    return out


def render(pkg: FactPackage) -> Narration:
    t = dict(load_template(template_name(pkg), pkg.locale))
    t.update(t.pop("variants", {}).get(template_variant(pkg) or "", {}))
    values = slots(pkg)

    def fill(s: str) -> str:
        return s.format_map(values)

    explanation = [fill(s) for s in t["explanation"]]
    if pkg.concept_is_new and t.get("new_term"):
        explanation.insert(0, fill(t["new_term"]))
    return Narration(
        headline=fill(t["headline"]),
        explanation=explanation,
        question=fill(t["question"]) if t.get("question") else None,
        hints=[fill(h) for h in t.get("hints", [])],
        takeaway=fill(t["takeaway"]),
        marks=default_marks(pkg),
    )


def default_marks(pkg: FactPackage) -> list[Mark]:
    """The played move (cross), the groups in question (triangles) and the key points that don't
    give the answer away (circles). Correct moves are never marked before the retry."""
    hidden = set(pkg.correct_moves) if pkg.lesson_type == "mistake" else set()
    marks: list[Mark] = []
    seen: set[str] = set()

    def add(point: str, kind: str) -> None:
        if point and point.lower() != "pass" and point not in seen and point not in hidden:
            seen.add(point)
            marks.append(Mark(point=point, kind=kind))  # type: ignore[arg-type]

    if pkg.played_move:
        add(pkg.played_move, "square" if pkg.lesson_type == "praise" else "cross")
    if pkg.threat_move:
        add(pkg.threat_move, "circle")
    for g in pkg.groups:
        for s in g.stones[:MAX_GROUP_MARKS]:
            add(s, "triangle")
    for p in pkg.key_points.values():
        add(p, "circle")
    return marks
