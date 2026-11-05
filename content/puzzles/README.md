# Shape Gym seed puzzles

One file per concept (`<concept>.yaml`): `concept`, then a `puzzles` list. Each puzzle has
`id`, `to_move` (black/white), `answer` (one correct first move), optional `moves` (learner moves
in a capture chase, default 1), `target` (a stone of the group the puzzle is about), `cut_points`
(cut_disconnect) and `board` (9 rows, top row = row 9; `X` black, `O` white, `.` empty; `#` starts
a comment).

`seed.json` is generated: after editing a diagram, run (from `apps/api`, with KataGo set up)

    uv run python ../../scripts/build_puzzles.py           # rebuild all, write seed.json
    uv run python ../../scripts/build_puzzles.py mc01 ld03 # check some, don't write

The build fails and names the puzzle when the authored answer is not in the accepted set
(D-051). `tests/gym/test_content.py` checks that `seed.json` matches the diagrams.
