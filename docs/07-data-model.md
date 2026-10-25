# 07 — Data Model (SQLite via SQLModel)

All tables have `id` (UUID string), `user_id` (FK users.id), `created_at`, `updated_at`. MVP has exactly one user row, created on first launch.

## users
| field | type | notes |
|-------|------|-------|
| display_name | str | |
| locale | str | `th` / `en` |
| belt | str | `white`…`brown` |
| rank_estimate | float | kyu as negative-friendly number: 25k → 25.0, 1d → 0.0, 2d → -1.0 |
| bot_rank | float | current adaptive bot strength, same scale |
| settings | JSON | sound, coordinates shown, nudges on/off |

## lesson_progress (rules school)
| lesson_id | str | e.g. `R4` |
| status | str | `locked`/`available`/`done` |
| attempts | int | |

## games
| field | type | notes |
|-------|------|-------|
| mode | str | `capture`, `full`, `exam` |
| board_size | int | 7, 9, 13, 19 |
| rules | JSON | ko/scoring/etc. |
| komi | float | |
| learner_color | str | `black`/`white` |
| bot_kind | str | `capture_bot`, `humansl` |
| bot_rank | float | |
| bot_params | JSON | profile, temperature, blunder rate, depth |
| status | str | `active`, `finished`, `abandoned` |
| result | str | e.g. `B+3.0`, `W+R`, `B+C` (capture) |
| learner_won | bool | |
| sgf | text | full record, kept in sync |
| nudges_used | int | |
| exam_id | FK? | when mode = exam |

## moves
| game_id | FK | |
| number | int | 1-based |
| color | str | |
| point | str? | GTP coord or null for pass |
| captures | int | |
| by_learner | bool | |
| nudge_shown | bool | |
| played_anyway | bool | after nudge |

## analyses
| game_id, move_number | | analysis of position **after** that move (0 = empty board) |
| visits | int | |
| root | JSON | winrate, scoreLead (Black perspective, raw) |
| move_infos | JSON | trimmed top 12 |
| ownership | JSON | array |
| human_policy | JSON? | for profiles queried, keyed by profile |
| engine_version | str | model + binary hash |

## mistakes
| game_id, move_number | | learner move |
| points_lost | float | |
| concept_id | str | `unexplained` allowed |
| secondary_concepts | JSON | |
| evidence | JSON | ConceptHit |
| p_find | float? | rank filter score |
| eligible | bool | passed filters |

## lessons
| game_id | FK | |
| mistake_id | FK? | null for praise |
| lesson_type | str | `mistake`, `praise`, `clean` |
| fact_package | JSON | |
| narration | JSON | final (LLM or template) |
| narration_source | str | `llm` / `template` |
| llm_reject_reason | str? | |
| retry_result | str? | `solved_first`, `solved_hint`, `failed` |
| viewed_at | datetime? | |

## puzzles
| source | str | `own_mistake`, `seed` |
| concept_id | str | |
| board_size | int | |
| setup | JSON | initialStones, player to move, komi, rules |
| correct_moves | JSON | first-move answers |
| solution_line | JSON | PV ≤ 6 |
| difficulty | float? | |
| origin_lesson_id | FK? | |

## srs_cards
| puzzle_id | FK | |
| fsrs_state | JSON | serialized `fsrs` Card |
| due_at | datetime | indexed |
| reps, lapses | int | |

## puzzle_attempts
| puzzle_id | FK | |
| context | str | `warmup`, `gym`, `exam` |
| result | str | `again`, `hard`, `good`, `easy` |
| hints_used | int | |
| time_ms | int | |

## exams
| belt_target | str | |
| status | str | `in_progress`, `passed`, `failed` |
| puzzle_score | int | of 12 |
| games_won | int | of best-of-3 |

## rank_history
| date | date | one row per day |
| rank_estimate | float | |
| likelihood_rank | float? | |
| results_rank | float? | |
| games_count | int | |

## Indexes
`moves(game_id, number)`, `analyses(game_id, move_number)`, `mistakes(concept_id)`, `srs_cards(due_at)`, `rank_history(date)`.

## Migrations
Use Alembic from day one, even for SQLite (`render_as_batch=True`).
