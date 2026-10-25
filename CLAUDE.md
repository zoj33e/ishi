# Ishi — Agent Instructions

You are building **Ishi**, an AI Go (หมากล้อม / Baduk / Weiqi) teacher that takes a total beginner to single-digit kyu fast. KataGo provides the truth, a deterministic **Why Engine** turns that truth into teachable facts, and Claude narrates those facts like a human teacher in Thai or English.

Read this file fully before writing code. Then read the docs in this order:

1. `docs/01-product-prd.md` — what we build and why
2. `docs/02-curriculum.md` — how the learner progresses
3. `docs/03-architecture.md` — system shape, stack, repo layout
4. `docs/04-katago-integration.md` — engine protocol and usage
5. `docs/05-why-engine.md` — concept detectors (the core IP)
6. `docs/06-teacher-llm.md` — narration layer
7. `docs/07-data-model.md` — database schema
8. `docs/08-api-spec.md` — HTTP API contract
9. `docs/09-ui-ux.md` — screens and interaction
10. `docs/10-roadmap.md` — milestones and acceptance criteria (build in this order)
11. `docs/11-testing.md` — test strategy
12. `docs/12-glossary.md` — Go terms in English and Thai
13. `docs/13-decisions.md` — decisions already made; do not relitigate without asking

## Golden rules (non-negotiable)

1. **The LLM never judges the board.** It never decides which move is good, whether a group is alive, or what to play. KataGo + the Why Engine decide. The LLM only rewrites a structured fact package into friendly language. If a fact is not in the package, the LLM must not state it.
2. **Every coordinate the LLM outputs is validated** against the fact package. Unknown coordinates → reject and fall back to the template explanation.
3. **The backend rules engine is authoritative** for legality, captures, ko and scoring. It must agree with the KataGo rules config in `docs/04-katago-integration.md`.
4. **One lesson per game.** Never dump a list of mistakes on the learner.
5. **Rank-aware teaching.** Only teach mistakes the learner is ready for (see the rank filter in `docs/05-why-engine.md`).
6. **Build one milestone at a time** (`docs/10-roadmap.md`). A milestone is done only when its acceptance criteria pass. Do not start the next one early.
7. **Every Why Engine detector ships with golden-position tests** before it is wired into lessons.
8. **Bilingual from day one.** No hard-coded user-facing strings; everything goes through i18n (`th`, `en`).
9. **Single user, local first.** No auth system in MVP, but every table has `user_id` so multi-user is a migration, not a rewrite.
10. **When a spec is ambiguous or wrong, stop and ask** with a concrete proposal. Do not silently invent product behavior. Record answers in `docs/13-decisions.md`.

## Verify, don't trust memory

KataGo's analysis engine and HumanSL options evolve. Before implementing the engine adapter, read the actual KataGo docs shipped with the release you install (`docs/analysis_engine.md`, the human-model example configs) and fix any field name in this spec that differs. Note any correction in `docs/13-decisions.md`.

## Coding standards

- Python 3.12, FastAPI, Pydantic v2, SQLModel, `uv` for deps, `ruff` + `pytest`.
- TypeScript strict, Next.js App Router, Tailwind, `vitest` + Playwright.
- Pure functions for rules and detectors (no I/O). I/O lives in adapters.
- Small modules, typed boundaries, no global mutable state except the engine process manager.
- Log every KataGo query/response id at debug level; never log the Anthropic API key.
