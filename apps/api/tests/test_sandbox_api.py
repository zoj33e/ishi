from fastapi.testclient import TestClient

from ishi.main import create_app

client = TestClient(create_app())


def post(**body):  # type: ignore[no-untyped-def]
    return client.post("/api/sandbox/state", json=body)


def test_empty_board_state() -> None:
    r = post(board_size=9)
    assert r.status_code == 200
    body = r.json()
    s = body["state"]
    assert s["board_size"] == 9 and s["to_move"] == "black" and s["status"] == "active"
    assert s["stones"] == {"black": [], "white": []}
    assert len(body["legal_moves"]) == 81
    assert body["sgf"].startswith("(;GM[1]FF[4]")


def test_moves_capture_and_ko_reported() -> None:
    # Builds the ko shape, then White takes the ko at D5.
    seq = ["D6", "E6", "C5", "F5", "D4", "E4", "E5", "D5"]
    body = post(board_size=9, moves=seq).json()
    s = body["state"]
    assert s["captures"] == {"black": 0, "white": 1}
    assert s["ko_point"] == "E5"
    assert s["last_move"] == "D5"
    assert "E5" not in body["legal_moves"]
    assert "E5" not in s["stones"]["black"]


def test_illegal_move_error_shape() -> None:
    r = post(board_size=9, moves=["E5", "E5"])
    assert r.status_code == 422
    assert r.json() == {
        "error": {
            "code": "ILLEGAL_MOVE",
            "message_key": "errors.illegal_move",
            "details": {"move_number": 2, "point": "E5", "reason": "occupied"},
        }
    }


def test_bad_coordinate_and_invalid_request() -> None:
    r = post(board_size=9, moves=["I5"])
    assert r.status_code == 422 and r.json()["error"]["code"] == "BAD_COORDINATE"
    r = post(board_size=42)
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_REQUEST"


def test_two_passes_finish_with_area_result() -> None:
    body = post(board_size=9, komi=7, moves=["E5", "pass", "pass"]).json()
    assert body["state"]["status"] == "finished"
    assert body["state"]["result"] == "B+74.0"  # one stone owns the whole board
    assert body["score"]["black_area"] == 81
    assert len(body["score"]["territory"]["black"]) == 80
    assert body["sgf"].endswith(";B[ee];W[];B[])") and "RE[B+74.0]" in body["sgf"]
    assert body["legal_moves"] == []
