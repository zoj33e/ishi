# 10 — Roadmap & Milestones

Build strictly in order. Each milestone ends with its acceptance criteria passing and a short note appended to `13-decisions.md` (what changed vs spec, if anything).

## M0 — Foundations
- Monorepo layout from `03-architecture.md`; `uv` project, Next.js app, lint/test configs, `scripts/start.ps1`.
- `scripts/setup_engine.ps1`: download KataGo + main net + HumanSL net, run benchmark, write `.env`.
- KataGo process manager + `/api/health`.
**Accept:** `GET /api/health` shows engine ok; a test query on the empty 9x9 board returns `moveInfos` within 2 s; web app installs as a PWA from http://localhost:3000 on the PC (phone over Tailscale deferred, D-013).

## M1 — Rules engine + board
- `rules/`: board, legality (suicide off, simple ko), captures, pass, area scoring, SGF import/export, coordinates.
- Board SVG component with ghost-stone confirm input.
- Local two-player sandbox page (debug).
**Accept:** ≥ 40 rules unit tests incl. ko, suicide-with-capture, edge captures, scoring; 20 KataGo-random-move games replayed with identical legality between our engine and KataGo (no rejected moves).

## M2 — Rules school + Capture Go
- Lesson YAML format + R1–R10 content (th + en).
- Capture bot (3 difficulty levels) and capture game mode.
- Belt: White → Yellow exam.
**Accept:** all 10 lessons completable on phone; capture bot unit tests pass; capture bot level 1 beats random mover ≥ 95% of 200 games.

## M3 — 9x9 vs HumanSL bot
- HumanSL bot with temperature + blunder rate, resign logic, game end + scoring with dead-stone detection.
- Calibration script and first calibration run.
**Accept:** full 9x9 game playable on phone end to end; bot move p95 < 500 ms; calibration log stored; results match KataGo's final score within 1 point on 10 test games.

## M4 — Analysis + Why Engine
- Background per-move analysis; pointsLost.
- Board facts, ladder reader, detectors C1–C6, rank filter, selector, FactPackage.
- Golden tests with recorded analysis fixtures.
**Accept:** every detector ≥ 8 golden tests passing; on 10 real games, manual review agrees with ≥ 80% of detector hits (log in decisions file); unexplained-mistake export works.

## M5 — Teacher + post-game lesson
- Templates (th, en) for C1–C6 + praise + clean game.
- Claude narrator, validator, caching, eval script + eval set.
- Lesson screen with retry and hint ladder; lesson → puzzle creation.
**Accept:** lesson ready < 4 s after game end; validator reject rate < 10% on eval set; with LLM disabled, every lesson still renders correctly in both languages.

## M6 — Shape Gym
- Seed puzzles (≥ 15 per MVP concept), puzzle answer generation, FSRS scheduling, warm-up flow, multi-move puzzles.
**Accept:** due queue correct across simulated days (test with frozen clock); puzzle answers accept any move within the best set.

## M7 — Nudges
- Preview endpoint, cached live analysis, nudge thresholds and budget, nudge UI.
**Accept:** nudge latency p95 < 1.5 s; never reveals the move; 0 nudges in exams.

## M8 — Progression
- Rank estimate (likelihood + results), rank_history, adaptive bot rank, belt exams Orange→Brown, progress screen, Today flow tying it all together.
**Accept:** a scripted "simulated learner" (bot at fixed rank playing as learner) converges to an estimate within ±3 stones of its true rank after 10 games.

**MVP = M0–M8.** Then start using it daily and keep a learning log.

## After MVP (order decided by real usage data)
1. P1 Weakness DNA radar
2. New detectors from the `unexplained` log (snapback, net, false eye, capturing race…)
3. P2 Hunter Bot
4. P3 Three-player replay
5. P4 X-ray fade
6. P6 13x13
7. P7 Cloud + multi-user
