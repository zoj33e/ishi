# 05 — Why Engine (concept detectors)

The Why Engine turns KataGo numbers into **teachable facts**. It is deterministic, pure Python, fully unit-tested, and the main thing that makes Ishi better than a raw analysis tool.

```
position + learner move + KataGo analysis (before/after)
        │
        ▼
facts.py      → board facts (groups, liberties, atari, captures, connectivity)
detectors/*   → concept hits with evidence
selector.py   → pick ONE lesson (rank-aware)
        │
        ▼
FactPackage (JSON)  →  teacher (06)
```

## Board facts (`why/facts.py`, `why/groups.py`)
Computed from the rules engine board, no KataGo needed:
- `Group`: id, color, stones[], liberties[] (set of points), size.
- Per position: groups, groups in atari (1 liberty), groups with 2 liberties, capturable groups (opponent groups in atari where the capturing move is legal), cutting points (empty point adjacent to ≥ 2 distinct same-color groups that are not otherwise connected), simple eyes (empty point fully surrounded by one color + edges, diagonal check for false eye).
- Diff between before/after the move: captured stones, new atari groups, liberties gained/lost per group.

## Ladder reader (`why/ladder.py`)
- Input: board, target group (exactly 2 liberties after attacker's first move, or in atari).
- Simulates the ladder: attacker plays the liberty that keeps the defender at 1 liberty; defender extends on its single liberty; repeat.
- Stops when defender gets ≥ 3 liberties (ladder **broken** — e.g., a ladder breaker), defender captures an attacker stone that gives it ≥ 2 liberties (broken), or defender reaches 0/1 liberty with no escape at the edge (ladder **works**).
- Max 80 plies. Returns `{works: bool, path: [points], breaker: point|null}`.

## Detectors (MVP)
Each detector: `detect(ctx) -> ConceptHit | None`. `ctx` holds: board_before, move, board_after, analysis_before, analysis_after, learner_color, best_moves.

`ConceptHit = { concept_id, severity_points, key_points[], groups[], evidence: dict, correct_moves[] }`

### C1 `missed_capture`
Fires when **all** hold:
- Before the move, some opponent group G was capturable (in atari, capture legal), OR capturable via a working ladder.
- A best move (or a move within 1.0 point of best) captures G or starts the working ladder on G.
- The learner's move does not capture G.
- pointsLost ≥ 2.0 (9x9).
Evidence: `{target_group, target_size, capture_point, via_ladder}`.

### C2 `ignored_atari`
- Before the move, a learner group G (size ≥ 1) was in atari.
- G is **savable**: some move gives G ≥ 2 liberties not immediately recapturable (G extended has ≥ 3 libs, or ≥ 2 libs and not in a working ladder), or captures an adjacent attacker.
- Learner's move does not save it AND opponent can capture next move.
- pointsLost ≥ 2.0.
- Not fired when KataGo's best move also abandons G (sacrifice is correct) — then skip.
Evidence: `{group, liberty_point, save_move, size}`.

### C3 `self_atari`
- After the learner's move, the group containing the new stone has exactly 1 liberty.
- The opponent's best reply (after-analysis top move) captures it, OR capture is legal and pointsLost ≥ 2.0.
- Exclude snapback-style sacrifices that KataGo rates fine (pointsLost < 1.0).
Evidence: `{group, last_liberty, size}`.

### C4 `ladder`
Two variants:
- **broken_ladder_chase**: learner played atari starting a ladder that `ladder.py` says is broken; pointsLost ≥ 2.0. Evidence: `{path, breaker}`.
- **ran_into_ladder**: learner extended a group in atari into a working ladder (group dies). Evidence: `{path}`.
- (Missed working ladder is covered by C1 with `via_ladder=true`.)

### C5 `cut_disconnect`
- Before the move there was a cutting point P between two learner groups A and B, AND the opponent's best reply after the learner's move is at P (or within PV first 2 moves), AND after cutting, one of A/B ends up with ownership(mover) < −0.3 in the after-analysis PV end or ownership drop ≥ 0.5 averaged over that group.
- Best move set includes connecting at/near P (a move adjacent to P that joins A and B).
- pointsLost ≥ 3.0.
Evidence: `{cut_point, groups:[A,B], connect_moves}`.

### C6 `group_death`
- A learner group G of size ≥ 3 has average ownership(mover) ≥ +0.3 before the move and ≤ −0.6 after (KataGo now thinks it's dead).
- pointsLost ≥ 4.0.
- Key point = the top move in the before-analysis whose PV makes G alive (ownership stays ≥ +0.3 in the PV result) — call it the vital point.
- Evidence: `{group, vital_point, eyes_before, eyes_after}`.

### Detector priority
If several detectors fire on one move, keep the most specific: `missed_capture` > `ignored_atari` > `self_atari` > `ladder` > `cut_disconnect` > `group_death`. Keep the others in `secondary_concepts` (not taught now).

### Unexplained mistakes
If pointsLost ≥ 5 and no detector fires → `concept_id = "unexplained"`. Never taught as a lesson; logged with position for future detector work (`scripts/export_unexplained.py`). This log is how the concept catalog grows.

## Rank-aware filter
For each concept hit, compute **readiness**:
```
target_profile = rank_profile(learner_rank - 5 stones)   # e.g. learner 20k → rank_15k
p_find = sum(humanPolicy_target[m] for m in correct_moves)
```
- If `p_find < 0.10` → skip (too advanced: even a stronger player probably misses it).
- Concept must be unlocked for the learner's belt (`02-curriculum.md`).
- Below Orange belt (no HumanSL profile fits), skip the p_find check and rely on concept unlock only.

## Lesson selection (`why/selector.py`)
Score each eligible hit:
```
score = min(pointsLost, 15) * (0.5 + p_find) * concept_weight * novelty
```
- `concept_weight`: 1.3 if the concept is in the learner's top-2 weakest (most frequent hits, last 10 games), else 1.0.
- `novelty`: 0.5 if the same concept was taught in the previous lesson, else 1.0.
- Pick the max. Ties → earlier in the game.
- If no eligible hit: pick a **praise moment** (learner move in the best set where the opponent just made a move that created an atari/cut, i.e., the learner correctly answered a threat). If none, a generic "clean game" summary.

## FactPackage (output contract to teacher)
```json
{
  "lesson_type": "mistake | praise | nudge",
  "locale": "th",
  "learner": {"belt": "orange", "rank_estimate": "24k"},
  "board_size": 9,
  "move_number": 17,
  "learner_color": "black",
  "concept_id": "ignored_atari",
  "concept_is_new": true,
  "played_move": "D4",
  "correct_moves": ["E5"],
  "points_lost": 6.5,
  "groups": [
    {"id": "g1", "owner": "learner", "stones": ["E4","E3"], "liberties_before": ["E5"], "liberties_after": []}
  ],
  "key_points": {"save_move": "E5", "capture_point": "E5"},
  "follow_up_line": ["W E5", "B F4"],
  "secondary_concepts": [],
  "allowed_coordinates": ["D4","E5","E4","E3","F4"]
}
```
`allowed_coordinates` is the union of every coordinate in the package; the validator rejects LLM output that mentions anything else.

## Tests (mandatory, see `11-testing.md`)
For every detector: ≥ 8 golden positions (≥ 5 positive, ≥ 3 negative look-alikes), each as SGF + expected `ConceptHit` JSON. Use **recorded KataGo analysis fixtures** (JSON) so tests run without the engine.
