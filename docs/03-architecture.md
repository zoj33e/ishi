# 03 — Architecture

## System overview

```
Phone / PC browser (PWA, Next.js)
        │  HTTPS (Tailscale serve) 
        ▼
Next.js app (UI only, no business logic)
        │  REST JSON
        ▼
FastAPI backend (Python, Windows PC)
 ├── rules/        pure Go rules engine (authoritative)
 ├── engine/       KataGo process manager + query adapter
 ├── bots/         HumanSL bot, Capture Go bot
 ├── why/          Why Engine: fact extraction + concept detectors
 ├── teacher/      lesson selection + Claude narration + validator
 ├── gym/          puzzles + FSRS scheduling
 ├── progress/     belts, exams, rank estimate
 └── db/           SQLite via SQLModel
        │                    │
        ▼                    ▼
 KataGo analysis engine   Anthropic API (Claude Haiku)
 (subprocess, GPU)        (narration only)
```

## Stack
| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | Next.js (App Router) + TypeScript strict + Tailwind | Fast to build, good PWA support |
| PWA | Serwist (`@serwist/next`) | Maintained successor of next-pwa |
| i18n | `next-intl` | App Router native |
| State | Zustand (UI state), TanStack Query (server state) | Small, simple |
| Board | Custom SVG component | Full control over marks/animations |
| Backend | FastAPI + Pydantic v2 + SQLModel | Python is where KataGo tooling lives |
| DB | SQLite (WAL mode) | Single user, zero ops |
| Engine | KataGo analysis engine, OpenCL or CUDA build for RTX 3070 Ti | Best open Go engine |
| LLM | Claude API, model `claude-haiku-5-5` | Cheap, good Thai |
| SRS | `fsrs` Python package | Modern scheduler |
| Remote access | Tailscale (+ `tailscale serve` for HTTPS) | PWA needs HTTPS; no port forwarding |

## Repo layout
```
ishi/
  CLAUDE.md
  docs/
  apps/
    web/                     # Next.js PWA
      app/[locale]/...
      components/board/
      messages/th.json, en.json
    api/                     # FastAPI
      ishi/
        main.py
        config.py
        rules/   (board.py, game.py, scoring.py, sgf.py, coords.py)
        engine/  (katago_process.py, queries.py, models.py)
        bots/    (humansl_bot.py, capture_bot.py)
        why/     (facts.py, groups.py, ladder.py, detectors/*.py, selector.py)
        teacher/ (prompts/, narrator.py, validator.py, templates/)
        gym/     (puzzles.py, fsrs_service.py)
        progress/(belts.py, exams.py, rank.py)
        db/      (models.py, session.py, migrations/)
        api/     (routes_*.py)
      tests/
        golden/  (SGF + expected facts)
  content/
    lessons/     # rules school lesson definitions (YAML, bilingual)
    puzzles/     # seed puzzles (SGF + YAML metadata)
  engine/        # NOT committed: KataGo binary, models, configs
  scripts/       # setup, download models, calibrate bots
```

## Process model
- Backend starts **one** long-lived KataGo analysis process at boot (`engine/katago_process.py`). Queries are written as JSON lines to stdin; responses read from stdout and dispatched by `id` to awaiting futures.
- Priority: nudge and bot-move queries use high `priority`; post-game analysis uses low priority.
- If KataGo dies, the manager restarts it and fails in-flight queries with a retryable error.
- Capture Go bot runs in-process (pure Python, no KataGo).

## Key data flows

### A. Bot move (full 9x9 game)
1. `POST /games/{id}/moves` with learner move.
2. Rules engine validates and applies it.
3. HumanSL query on the new position → sample bot move (softmax over human policy) → validate → apply.
4. Kick off background full analysis of the learner's move (for lesson later).
5. Return new state.

### B. Nudge (ghost stone)
1. `POST /games/{id}/preview` with candidate move.
2. Use cached analysis of the current position (refreshed after each bot move). If the candidate isn't in `moveInfos`, run a fast query on the resulting position.
3. pointsLost ≥ threshold AND a concept detector fires AND concept unlocked AND nudge budget left → return nudge facts; teacher narrates the question (templated text first, LLM optional; see `06`).

### C. Post-game lesson
1. Game ends → ensure every learner move is analyzed.
2. Why Engine runs detectors on each learner mistake → candidate list.
3. Selector picks one (rank-aware filter + score).
4. Teacher builds fact package → Claude narration → validator → stored lesson.
5. Lesson's critical position saved as Shape Gym card.

## Configuration (`apps/api/ishi/config.py`, env vars)
| Var | Example |
|-----|---------|
| `ISHI_KATAGO_BIN` | `C:\ishi\engine\katago.exe` |
| `ISHI_KATAGO_MODEL` | main network path |
| `ISHI_KATAGO_HUMAN_MODEL` | HumanSL network path |
| `ISHI_KATAGO_CONFIG` | analysis config path |
| `ISHI_DB_PATH` | `C:\ishi\data\ishi.db` |
| `ANTHROPIC_API_KEY` | secret |
| `ISHI_LLM_MODEL` | `claude-haiku-5-5` |
| `ISHI_LLM_ENABLED` | `true` (false → template-only narration) |
| `ISHI_DEFAULT_LOCALE` | `th` |

## Deployment (MVP)
- Windows PC: run `api` (uvicorn) and `web` (next start) as two processes; a `scripts/start.ps1` launches both.
- `tailscale serve` exposes the web app over HTTPS to the learner's devices; the web app proxies `/api/*` to FastAPI (Next.js rewrites), so the browser talks to one origin.
- Cloud later: swap SQLite → Postgres, move KataGo to a GPU host; adapters already isolate both.

## Performance budgets
| Operation | Budget | Notes |
|-----------|--------|-------|
| Bot move | < 500 ms | HumanSL needs few visits |
| Nudge preview | < 1.5 s | cached position analysis |
| Move analysis (9x9) | ~200–500 visits | background |
| Lesson ready | < 4 s after game end | most analysis already done during play |

## Error handling
- KataGo unavailable → games still playable vs capture bot only; UI shows "Teacher is resting (engine offline)".
- Anthropic unavailable or invalid output → template narration (always available).
- Every error returned as `{ "error": { "code": "...", "message_key": "..." } }` with an i18n key.
