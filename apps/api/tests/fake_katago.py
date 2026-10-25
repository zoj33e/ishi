"""Stand-in for `katago analysis`: speaks the JSON-lines protocol with canned answers.

Special query ids: `crash*` exits the process, `hang*` never answers, `bad*` returns an error.
Multi-turn queries are answered in reverse turn order to exercise out-of-order dispatch.
"""

import json
import sys


def analysis(q: dict, turn: int) -> dict:
    return {
        "id": q["id"],
        "isDuringSearch": False,
        "turnNumber": turn,
        "moveInfos": [
            {
                "move": "E5",
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
                "scoreLead": -5.0,
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
        "ownership": [0.0] * (q["boardXSize"] * q["boardYSize"]),
    }


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
