# Rules-school lessons

One YAML file per lesson (`R01.yaml` … `R10.yaml`), loaded by `apps/api/ishi/school/content.py`.
Every text field has `en` and `th`. Coordinates are GTP (`C3`; columns skip `I`; row 1 is at the bottom).

```yaml
id: R4            # unique, used in URLs
order: 4          # lessons unlock in this order
board_size: 5     # default for every setup below
title / idea / takeaway: {en, th}
demo:
  setup: {black: [..], white: [..], to_move: black, moves: [..], komi: 0}
  frames:         # shown one by one; `move` is played before the frame
    - {text: {en, th}, move: D3, marks: [{point: C2, kind: circle}]}
tasks:            # 2–4 per lesson
  - id: t1
    kind: play | count | select | choose
    prompt / hint / success: {en, th}
    setup: {...}  # same shape as demo.setup
    # play:   steps: [{goal: {...}, reply: {type: save_atari|fixed, ...}}]
    # count:  count: {type: liberties|area, target, color, dead}
    # select: select: {type: liberties|suicide_points|ko_point|false_eyes|points, target, points, mode: one|all}
    # choose: choose: {type: winner, dead}
    expect: 13    # optional; the tests check it against the rules engine
```

Play goals: `place_any`, `place_at {points}`, `capture {min_stones, target}`, `atari {target}`,
`escape {target, min_libs}`, `connect {a, b}`, `cut {a, b}`, `pass`, `two_eyes {target}`.
A step's `reply` is the opponent's scripted answer before the next step.

The rules engine computes every answer; only `select: points` (e.g. which stones are dead) is
authored by hand. After editing, run `uv run pytest tests/school` in `apps/api`: it checks that
every coordinate is valid, every play step has a solution and not every legal move solves it, and
every `expect` matches the engine.
