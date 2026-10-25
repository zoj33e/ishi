# 08 — API Spec (FastAPI, prefix `/api`)

JSON only. Coordinates are GTP strings (`"E5"`, `"pass"`). Errors: `{"error": {"code": "ILLEGAL_MOVE", "message_key": "errors.illegal_move", "details": {}}}`. FastAPI auto-generates OpenAPI; the web app generates TS types from it (`openapi-typescript`) — never hand-write API types.

## Shared types
```ts
GameState = {
  id, mode, board_size, komi, learner_color, to_move,
  stones: { black: string[], white: string[] },
  last_move: string | null,
  captures: { black: number, white: number },
  ko_point: string | null,
  move_number: number,
  status: "active" | "finished",
  result: string | null,
  nudges_left: number
}
Narration = { headline, explanation: string[], question: string|null, hints: string[], takeaway, marks: Mark[] }
Mark = { point: string, kind: "circle"|"triangle"|"square"|"cross"|"label", label?: string }
```

## Profile & home
| Method | Path | Body / Query | Returns |
|--------|------|--------------|---------|
| GET | `/me` | | user, belt, rank_estimate, streak |
| PATCH | `/me` | `{locale?, display_name?, settings?}` | user |
| GET | `/today` | | `{warmup_due: n, game: {mode, board_size, bot_rank}, lesson_pending: lesson_id|null, exam_available: bool}` |

## Rules school
| GET | `/school` | `?locale=` | `{lessons: [{id, order, title, status: locked\|available\|done, tasks_total, tasks_done}], next_lesson}` |
| GET | `/school/{lesson_id}` | `?locale=` | lesson text in the locale + server-computed positions for each demo frame and task (D-026) |
| POST | `/school/{lesson_id}/tasks/{task_id}/answer` | `{moves?: string[], number?, points?: string[], choice?}` | `{correct, feedback_key, marks, done, reply, position, lesson_done}`; `409 LESSON_LOCKED` |

## Games
| POST | `/games` | `{mode: "capture"\|"full", board_size?, learner_color?, exam_id?}` (defaults from `/today`; M2 capture games take size/target/bot level from the current stage, D-024) | GameState |
| GET | `/games/bot-ranks` | | `{ranks: number[], unlocked: bool}` — 9x9 strength picker until M8 (D-031) |
| GET | `/games/{id}` | | GameState (full games add `bot_rank`, `bot_label`, and after two passes `score` + `dead`) |
| POST | `/games/{id}/preview` | `{point}` | `{legal, nudge: null \| {narration, hint_level_available: 2, concept_id}}` |
| POST | `/games/{id}/moves` | `{point, played_anyway?: bool}` | `{state: GameState, bot_move: string\|null, game_over: bool}` |
| POST | `/games/{id}/hint` | `{level: 1\|2\|3}` | hint narration / marks (only after a nudge) |
| POST | `/games/{id}/resign` | | GameState |
| GET | `/games/{id}/sgf` | | `text/plain` SGF |

Rules: `preview` is optional (UI calls it on ghost stone). `moves` validates with the rules engine, applies the bot reply in the same request, and schedules analysis in the background. When both players pass in a full game, the backend scores (area scoring + KataGo ownership for dead stones; dead = ownership ≤ −0.8 from owner's perspective) and returns final state.

## Lessons (post-game)
| GET | `/games/{id}/lesson` | | `202 {status: "preparing"}` or `{lesson_id, lesson_type, concept_id, position: GameState-like snapshot, narration}` |
| POST | `/lessons/{lesson_id}/retry` | `{point}` | `{correct, narration_feedback, next_hint_level?, solution_line?}` |
| POST | `/lessons/{lesson_id}/done` | | `{puzzle_added: bool}` |

## Shape Gym
| GET | `/gym/due` | `?limit=8` | puzzles due (setup, to_move, concept, no answers) |
| POST | `/gym/puzzles/{id}/attempt` | `{moves: string[], hints_used, time_ms}` | `{correct, opponent_reply?: string, done: bool, solution_line?, next_due_at}` |
| POST | `/gym/puzzles/{id}/hint` | `{level}` | hint narration/marks |

Multi-move puzzles: client sends the moves so far; server replies with KataGo's reply or `done`.

## Progress & exams
| GET | `/progress` | | belt, rank_history[], concept_stats[] (hits per concept, last 10 games) |
| POST | `/exams` | | starts (or resumes) the exam if available; returns `{id, belt_target, status, games_won, games_lost, wins_needed, losses_allowed, active_game, puzzles}` (D-029); `409 EXAM_NOT_AVAILABLE` |
| GET | `/exams/{id}` | | status |

## System
| GET | `/health` | | `{api: ok, engine: ok\|down, llm: ok\|disabled\|down, db: ok}` |

## Debug (M1, D-018)
| POST | `/sandbox/state` | `{board_size, komi?, moves: string[]}` | `{state: GameState, legal_moves: string[], score, sgf}`; `422 ILLEGAL_MOVE` with `details.reason` ∈ `occupied`, `suicide`, `ko`, `game_over`, `off_board` |
