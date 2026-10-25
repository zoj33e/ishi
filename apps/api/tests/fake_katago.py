"""Stand-in for `katago analysis`: speaks the JSON-lines protocol with canned answers.

Special query ids: `crash*` exits the process, `hang*` never answers, `bad*` returns an error.
Multi-turn queries are answered in reverse turn order to exercise out-of-order dispatch.
"""

import json
import sys

from ishi.rules.board import Board, Color
from ishi.rules.coords import gtp_to_point, point_to_index


def ownership(q: dict) -> list[float]:
    """Every stone is alive and every empty point is Black's (no dame, nothing dead)."""
    size = q["boardXSize"]
    board = Board.empty(size)
    for color, move in q.get("initialStones", []) + q.get("moves", []):
        if move.lower() != "pass":
            board, _ = board.place(gtp_to_point(move, size), Color.parse(color))
    own = [1.0] * (size * size)
    for p in board.stones(Color.WHITE):
        own[point_to_index(p, size)] = -1.0
    return own


def analysis(q: dict, turn: int) -> dict:
    """After a pass the best move is pass (lets tests end games); policies are uniform."""
    n = q["boardXSize"] * q["boardYSize"]
    moves = q.get("moves", [])
    best = "pass" if moves and moves[-1][1].lower() == "pass" else "E5"
    # Passing costs the mover 12 points (Black-perspective lead goes the mover's wrong way).
    pass_lead = 7.2 - 12 if len(moves) % 2 == 0 else 7.2 + 12
    out = {
        "id": q["id"],
        "isDuringSearch": False,
        "turnNumber": turn,
        "moveInfos": [
            {
                "move": best,
                "visits": 90,
                "winrate": 0.55,
                "scoreLead": 7.2,
                "prior": 0.6,
                "order": 0,
                "pv": ["E5", "D4"],
                "lcb": 0.5,
                "utility": 0.1,
            },
            {
                "move": "pass",
                "visits": 1,
                "winrate": 0.1,
                "scoreLead": 7.2 if best == "pass" else pass_lead,
                "prior": 0.0,
                "order": 1,
                "pv": ["pass"],
            },
        ],
        "rootInfo": {
            "winrate": 0.54,
            "scoreLead": 7.0,
            "visits": 100,
            "currentPlayer": "B",
            "thisHash": "x",
        },
    }
    if q.get("includeOwnership"):
        out["ownership"] = ownership(q)
    if q.get("includePolicy"):
        out["policy"] = [1.0 / n] * n + [0.0]
        if q.get("overrideSettings", {}).get("humanSLProfile"):
            out["humanPolicy"] = [1.0 / n] * n + [0.0]
    return out


def main() -> None:
    print("fake katago starting", file=sys.stderr, flush=True)
    for line in sys.stdin:
        q = json.loads(line)
        qid = q["id"]
        if q.get("action") == "query_version":
            out = [{**q, "version": "fake-1.0", "git_hash": "<omitted>"}]
        elif q.get("action"):
            out = [q]
        elif qid.startswith("crash"):
            sys.exit(3)
        elif qid.startswith("hang"):
            out = []
        elif qid.startswith("bad"):
            out = [{"error": "bad field", "field": "moves", "id": qid}]
        else:
            turns = q.get("analyzeTurns") or [len(q.get("moves", []))]
            out = [{"warning": "unused field", "field": "x", "id": qid}]
            out += [analysis(q, t) for t in reversed(turns)]
        for msg in out:
            print(json.dumps(msg), flush=True)


if __name__ == "__main__":
    main()
