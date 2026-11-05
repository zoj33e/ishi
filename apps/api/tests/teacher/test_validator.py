"""The validator with canned model outputs (11-testing: every rejection branch)."""

import json
from typing import Any

import pytest

from ishi.teacher.validator import Rejected, allowed_numbers, validate
from ishi.why.fact_package import FactPackage
from tests.teacher.conftest import package_for

CASE = "self_atari/two_stones"


def good_en(pkg: FactPackage) -> dict[str, Any]:
    g = pkg.groups[0]
    return {
        "headline": "That move left your own stones in atari.",
        "explanation": [
            f"After {pkg.played_move}, your {len(g.stones)} stones had one liberty left.",
            f"The opponent can capture them at {pkg.key_points['last_liberty']}.",
        ],
        "question": "Where would have been a better move?",
        "hints": ["Count your liberties after the move.", "Look inside the highlighted area."],
        "takeaway": "Count liberties after your move, not before.",
        "marks": [{"point": pkg.played_move, "kind": "cross", "label": None}],
    }


def good_th(pkg: FactPackage) -> dict[str, Any]:
    return {
        "headline": "ลงแล้วหมากเราติดอาตาริเอง",
        "explanation": [
            f"พอลงที่ {pkg.played_move} หมากของเราเหลือลมหายใจช่องเดียว",
            f"ฝ่ายตรงข้ามลงที่ {pkg.key_points['last_liberty']} ก็กินได้เลย",
        ],
        "question": "ตรงไหนน่าจะเป็นตาเดินที่ดีกว่า",
        "hints": ["ลองนับลมหายใจหลังลงดู", "ลองดูในบริเวณที่ไฮไลต์ไว้"],
        "takeaway": "นับลมหายใจหลังจากลงแล้วนะ",
        "marks": [],
    }


@pytest.fixture
def pkg() -> FactPackage:
    return package_for(CASE, "en")


def reason(raw: dict[str, Any] | str, pkg: FactPackage) -> str:
    with pytest.raises(Rejected) as e:
        validate(raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False), pkg)
    return e.value.reason


def test_good_narrations_pass(pkg: FactPackage) -> None:
    n = validate(json.dumps(good_en(pkg)), pkg)
    assert n.headline.startswith("That move")
    th = package_for(CASE, "th")
    assert validate(json.dumps(good_th(th), ensure_ascii=False), th).question


def test_schema(pkg: FactPackage) -> None:
    assert reason("not json", pkg) == "schema"
    bad = good_en(pkg)
    del bad["takeaway"]
    assert reason(bad, pkg) == "schema"
    bad = good_en(pkg) | {"extra": 1}
    assert reason(bad, pkg) == "schema"
    bad = good_en(pkg)
    bad["marks"] = [{"point": "D4", "kind": "star", "label": None}]
    assert reason(bad, pkg) == "schema"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("headline", "one two three four five six seven eight nine ten eleven twelve thirteen"),
        ("explanation", ["Only one sentence."]),
        ("explanation", ["a.", "b.", "c.", "d.", "e."]),
        ("hints", ["Just one hint."]),
        ("question", None),
        ("takeaway", "   "),
        ("takeaway", "x" * 300),
    ],
)
def test_lengths(pkg: FactPackage, field: str, value: object) -> None:
    assert reason(good_en(pkg) | {field: value}, pkg) == "length"


def test_thai_headline_limit() -> None:
    th = package_for(CASE, "th")
    assert reason(good_th(th) | {"headline": "ก" * 41}, th) == "length"


def test_unknown_coordinate(pkg: FactPackage) -> None:
    unknown = next(c for c in ("A9", "J1", "A1", "J9") if c not in pkg.allowed_coordinates)
    bad = good_en(pkg)
    bad["explanation"][1] = f"The opponent can capture them at {unknown}."
    assert reason(bad, pkg) == "coordinate"
    bad = good_en(pkg) | {"marks": [{"point": unknown, "kind": "circle", "label": None}]}
    assert reason(bad, pkg) == "coordinate"
    bad = good_en(pkg)
    bad["takeaway"] = "Look at Z9 next time."  # off the board
    assert reason(bad, pkg) == "coordinate"


def test_coordinate_glued_to_thai_text() -> None:
    th = package_for(CASE, "th")
    unknown = next(c for c in ("A9", "J1", "A1") if c not in th.allowed_coordinates)
    bad = good_th(th)
    bad["explanation"][0] = f"พอลงที่{unknown}หมากของเราเหลือลมหายใจช่องเดียว"
    assert reason(bad, th) == "coordinate"


def test_revealing_the_answer_before_the_retry(pkg: FactPackage) -> None:
    answer = pkg.correct_moves[0]
    bad = good_en(pkg)
    bad["hints"][0] = f"Try {answer}."
    assert reason(bad, pkg) == "reveals_answer"
    bad = good_en(pkg) | {"marks": [{"point": answer, "kind": "circle", "label": None}]}
    assert reason(bad, pkg) == "reveals_answer"
    ok = good_en(pkg) | {"takeaway": f"Next time, think of {answer}."}
    assert validate(json.dumps(ok), pkg).takeaway.endswith(f"{answer}.")


def test_other_concepts_are_rejected(pkg: FactPackage) -> None:
    bad = good_en(pkg)
    bad["explanation"][1] = "This is like a ladder."
    assert reason(bad, pkg) == "concept"
    bad = good_en(pkg) | {"takeaway": "Watch out for ko."}
    assert reason(bad, pkg) == "concept"
    # its own concept and basic rules words are fine
    ok = good_en(pkg) | {"takeaway": "Self-atari gives the opponent a free capture."}
    assert validate(json.dumps(ok), pkg)


def test_secondary_concepts_are_allowed() -> None:
    pkg = package_for("ignored_atari/mined_mine20_g12_m9", "en")
    pkg = pkg.model_copy(update={"secondary_concepts": ["cut_disconnect"]})
    raw = {
        "headline": "Your stone needed help right away.",
        "explanation": ["Your stone had one liberty left.", "It was also a cutting stone."],
        "question": "How could you have saved it?",
        "hints": ["How can it get more liberties?", "Look inside the highlighted area."],
        "takeaway": "Save stones in atari when they matter.",
        "marks": [],
    }
    assert validate(json.dumps(raw), pkg)


def test_thai_concept_words() -> None:
    th = package_for(CASE, "th")
    bad = good_th(th)
    bad["explanation"][1] = "แบบนี้เหมือนบันไดเลย"
    assert reason(bad, th) == "concept"
    # English concept words are caught in Thai narrations too
    bad = good_th(th) | {"takeaway": "ระวังโค (ko) ด้วยนะ"}
    assert reason(bad, th) == "concept"
    # "จุดตัด" (intersection) is not the cut concept
    ok = good_th(th)
    ok["explanation"][1] = "ฝ่ายตรงข้ามลงที่จุดตัดนั้นก็กินได้"
    assert validate(json.dumps(ok, ensure_ascii=False), th)


def test_numbers(pkg: FactPackage) -> None:
    bad = good_en(pkg)
    bad["explanation"][0] = "You lost 37 points with that move."
    assert reason(bad, pkg) == "number"
    assert str(len(pkg.groups[0].stones)) in allowed_numbers(pkg)
    assert {"1", "2"} <= allowed_numbers(pkg)


def test_language(pkg: FactPackage) -> None:
    bad = good_en(pkg) | {"takeaway": "นับลมหายใจหลังลงนะ"}
    assert reason(bad, pkg) == "language"
    th = package_for(CASE, "th")
    english = good_en(th)
    assert reason(english, th) == "language"
    # Thai in parentheses is still Thai in an English narration
    assert reason(good_en(pkg) | {"takeaway": "Watch your group (กลุ่มหมาก)."}, pkg) == "language"
    # one English sentence in an otherwise Thai narration
    mixed = good_th(th) | {"takeaway": "Count liberties after your move."}
    assert reason(mixed, th) == "language"
    # glossary terms in parentheses don't count against Thai
    ok = good_th(th) | {"takeaway": "อาตาริ (atari) คือเหลือลมหายใจช่องเดียว"}
    assert validate(json.dumps(ok, ensure_ascii=False), th)
