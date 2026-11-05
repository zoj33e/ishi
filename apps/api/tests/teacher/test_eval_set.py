"""The teacher eval set (06-teacher-llm): 30 packages, 5 per concept, valid references."""

import json
from collections import Counter
from pathlib import Path

from ishi.teacher.validator import validate
from ishi.why.detectors import CONCEPTS
from ishi.why.fact_package import FactPackage

EVAL_SET = Path(__file__).with_name("eval_set")


def test_eval_set_shape_and_references() -> None:
    items = [json.loads(p.read_text("utf-8")) for p in sorted(EVAL_SET.glob("*.json"))]
    assert len(items) == 30
    pkgs = [FactPackage.model_validate(i["package"]) for i in items]
    assert Counter(p.concept_id for p in pkgs) == dict.fromkeys(CONCEPTS, 5)
    assert {p.locale for p in pkgs} == {"th", "en"}
    assert {p.concept_is_new for p in pkgs} == {True, False}
    for item, pkg in zip(items, pkgs, strict=True):
        assert validate(json.dumps(item["reference"], ensure_ascii=False), pkg)
