"""Templates alone must give a correct lesson in both languages (M5: LLM disabled)."""

import pytest

from ishi.teacher.templates import TEMPLATES_DIR, load_template, render
from ishi.teacher.validator import validate
from ishi.why.detectors import CONCEPTS
from ishi.why.fact_package import clean_package, learner_info, praise_package
from ishi.why.selector import find_praise
from tests.teacher.conftest import POSITIVE_CASES, package_for
from tests.why.test_selector import _review_praise_board

LOCALES = ("en", "th")


@pytest.mark.parametrize("name", [*CONCEPTS, "praise", "clean"])
@pytest.mark.parametrize("locale", LOCALES)
def test_every_concept_has_a_template(name: str, locale: str) -> None:
    t = load_template(name, locale)
    assert {"headline", "explanation", "takeaway"} <= set(t)
    if name not in ("praise", "clean"):
        assert t["question"] and len(t["hints"]) == 2 and t["new_term"]


def test_no_stray_template_files() -> None:
    names = {p.name.split(".")[0] for p in TEMPLATES_DIR.glob("*.yaml")}
    assert names == {*CONCEPTS, "praise", "clean", "nudge"}


@pytest.mark.parametrize("case_id", POSITIVE_CASES)
@pytest.mark.parametrize("locale", LOCALES)
@pytest.mark.parametrize("new", [True, False])
def test_template_lesson_for_every_golden_hit_passes_the_validator(
    case_id: str, locale: str, new: bool
) -> None:
    pkg = package_for(case_id, locale, new=new)  # type: ignore[arg-type]
    n = render(pkg)
    assert not any("{" in t or "}" in t for t in n.texts()), "unfilled slot"
    assert validate(n.model_dump_json(), pkg) == n
    if pkg.played_move:
        assert any(m.point == pkg.played_move and m.kind == "cross" for m in n.marks)


def test_new_concept_starts_with_the_definition() -> None:
    old = render(package_for("self_atari/two_stones", "en"))
    new = render(package_for("self_atari/two_stones", "en", new=True))
    assert new.explanation[1:] == old.explanation
    assert new.explanation[0].startswith("Self-atari means")


def test_english_agreement_for_one_stone() -> None:
    n = render(package_for("ignored_atari/mined_mine20_g12_m9", "en"))  # a single stone
    text = " ".join(n.texts())
    assert "Your stone marked with a triangle had" in text and "saved it?" in text


def test_ladder_variants_differ() -> None:
    ran = render(package_for("ladder/ran_into", "en"))
    chase = render(package_for("ladder/broken_chase", "en"))
    assert ran.headline != chase.headline


@pytest.mark.parametrize("locale", LOCALES)
def test_praise_and_clean_render(locale: str) -> None:
    praise = find_praise([_review_praise_board()])
    assert praise is not None
    learner = learner_info("yellow", None)
    pkg = praise_package(praise, locale=locale, learner=learner)  # type: ignore[arg-type]
    n = render(pkg)
    assert "D4" in n.headline and n.question is None
    assert validate(n.model_dump_json(), pkg) == n
    from ishi.rules.board import Color

    clean = clean_package(locale=locale, learner=learner, size=9, color=Color.BLACK)  # type: ignore[arg-type]
    c = render(clean)
    assert c.marks == [] and validate(c.model_dump_json(), clean) == c
