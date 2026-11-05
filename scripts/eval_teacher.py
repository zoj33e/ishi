"""Teacher eval (06-teacher-llm): run Claude on the eval set, validate every narration, report the
reject rate (M5 accepts < 10%) and the outputs next to the reference narrations for manual review.

The eval set is 30 FactPackages (5 per concept) from the golden cases, alternating Thai/English and
new/known concept; references are the reviewed template narrations.

Usage (from apps/api):
    uv run python ../../scripts/eval_teacher.py --build   # (re)write tests/teacher/eval_set/
    uv run python ../../scripts/eval_teacher.py           # needs ANTHROPIC_API_KEY in .env
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import date
from pathlib import Path

from ishi.config import REPO_ROOT, get_settings
from ishi.teacher.llm import TeacherLLM
from ishi.teacher.narration import Narration
from ishi.teacher.narrator import narrate
from ishi.teacher.templates import render
from ishi.why.detectors import CONCEPTS
from ishi.why.fact_package import FactPackage

EVAL_SET = REPO_ROOT / "apps" / "api" / "tests" / "teacher" / "eval_set"
PER_CONCEPT = 5
CONCURRENCY = 4
MAX_REJECT_RATE = 0.10


def build() -> None:
    sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
    from tests.teacher.conftest import POSITIVE_CASES, package_for

    EVAL_SET.mkdir(parents=True, exist_ok=True)
    for old in EVAL_SET.glob("*.json"):
        old.unlink()
    i = 0
    for concept in CONCEPTS:
        cases = [c for c in POSITIVE_CASES if c.startswith(concept + "/")][:PER_CONCEPT]
        assert len(cases) == PER_CONCEPT, concept
        for k, case in enumerate(cases):
            locale = "th" if i % 2 == 0 else "en"
            pkg = package_for(case, locale, new=k % 2 == 0, number=10 + 2 * k)  # type: ignore[arg-type]
            ref = render(pkg).model_dump()
            item = {"case": case, "package": pkg.model_dump(), "reference": ref}
            name = f"{i:02d}_{concept}_{locale}.json"
            (EVAL_SET / name).write_text(
                json.dumps(item, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
            )
            i += 1
    print(f"wrote {i} eval items to {EVAL_SET}")


def load() -> list[tuple[str, FactPackage, Narration]]:
    out = []
    for p in sorted(EVAL_SET.glob("*.json")):
        item = json.loads(p.read_text(encoding="utf-8"))
        out.append(
            (
                p.stem,
                FactPackage.model_validate(item["package"]),
                Narration.model_validate(item["reference"]),
            )
        )
    return out


def show(n: Narration) -> list[str]:
    lines = [f"**{n.headline}**", *[f"- {s}" for s in n.explanation]]
    if n.question:
        lines.append(f"- ? {n.question}")
    lines += [f"- hint: {h}" for h in n.hints]
    lines.append(f"- takeaway: {n.takeaway}")
    lines.append(f"- marks: {', '.join(f'{m.point} {m.kind}' for m in n.marks) or 'none'}")
    return lines


async def run(out_path: Path) -> int:
    settings = get_settings()
    if settings.anthropic_api_key is None:
        print("ANTHROPIC_API_KEY is not set in .env", file=sys.stderr)
        return 2
    llm = TeacherLLM(settings.anthropic_api_key.get_secret_value(), settings.llm_model)
    items = load()
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(pkg: FactPackage) -> tuple[str | None, Narration | None, str, float, int]:
        """The app's pipeline (Claude, validator, one retry) without a time budget."""
        async with sem:
            t0 = time.perf_counter()
            r = await narrate(pkg, llm)
            secs = time.perf_counter() - t0
            if r.source == "llm":
                return None, r.narration, r.raw or "", secs, r.retried
            return f"{r.reject_reason}: {r.detail}", None, r.raw or "", secs, r.retried

    try:
        results = await asyncio.gather(*(one(pkg) for _, pkg, _ in items))
    finally:
        await llm.close()

    rejects = [(name, r[0]) for (name, _, _), r in zip(items, results, strict=True) if r[0]]
    retried = sum(1 for r in results if r[4])
    rate = len(rejects) / len(items)
    latencies = sorted(r[3] for r in results)
    p95 = latencies[int(0.95 * (len(latencies) - 1))]
    lines = [
        f"# Teacher eval {date.today()} ({settings.llm_model})",
        "",
        f"{len(items)} packages, {len(rejects)} rejected: reject rate {rate:.0%}"
        f" (accept < {MAX_REJECT_RATE:.0%}); {retried} needed the retry; latency p95 {p95:.1f} s.",
        "",
    ]
    if rejects:
        lines += ["## Rejects", *[f"- {name}: {why}" for name, why in rejects], ""]
    for (name, pkg, ref), (why, n, raw, secs, tries) in zip(items, results, strict=True):
        lines += [f"## {name} ({pkg.concept_id}/{pkg.variant or '-'}, new={pkg.concept_is_new})"]
        lines += [
            f"{secs:.1f} s{' (retried)' * bool(tries)};"
            f" correct moves {', '.join(pkg.correct_moves)}",
            "",
        ]
        lines += ["### Claude", *(show(n) if n else [f"REJECTED ({why})", "", "```", raw, "```"])]
        lines += ["", "### Reference (template)", *show(ref), "", "verdict: _todo_", ""]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(lines[2])
    print(f"report: {out_path}")
    return 0 if rate < MAX_REJECT_RATE else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true", help="rewrite the eval set from golden cases")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "eval" / "teacher.md")
    args = ap.parse_args()
    if args.build:
        build()
        return 0
    return asyncio.run(run(args.out))


if __name__ == "__main__":
    sys.exit(main())
