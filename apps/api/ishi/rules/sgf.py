"""SGF (FF[4]) import/export for the main line of a game. Variations are ignored on import."""

from __future__ import annotations

from dataclasses import dataclass, field

from ishi.rules.board import Board, Color
from ishi.rules.coords import Point, point_to_sgf, sgf_to_point
from ishi.rules.game import DEFAULT_KOMI, GameState, new_game, play

Node = dict[str, list[str]]


@dataclass(frozen=True, slots=True)
class SgfGame:
    size: int
    komi: float
    moves: tuple[tuple[Color, Point | None], ...]
    black_setup: tuple[Point, ...] = ()
    white_setup: tuple[Point, ...] = ()
    player_to_start: Color | None = None
    result: str | None = None
    properties: dict[str, str] = field(default_factory=dict)  # other root props, first value

    def to_state(self) -> GameState:
        """Replay into a GameState. Moves must alternate colors (raises otherwise)."""
        initial = None
        if self.black_setup or self.white_setup:
            initial = Board.from_stones(self.size, self.black_setup, self.white_setup)
        first = self.player_to_start
        if first is None:
            first = self.moves[0][0] if self.moves else Color.BLACK
        state = new_game(self.size, self.komi, initial_board=initial, to_move=first)
        for i, (color, point) in enumerate(self.moves, start=1):
            if color is not state.to_move:
                raise ValueError(f"move {i}: {color.value} played out of turn")
            state = play(state, point)
        return state


# -- export ------------------------------------------------------------------------------


def _esc(v: str) -> str:
    return v.replace("\\", "\\\\").replace("]", "\\]")


def to_sgf(
    state: GameState,
    *,
    result: str | None = None,
    player_black: str | None = None,
    player_white: str | None = None,
    date: str | None = None,
) -> str:
    size = state.size
    root = [f"GM[1]FF[4]CA[UTF-8]AP[Ishi:0.1]SZ[{size}]KM[{state.komi:g}]RU[Chinese]"]
    for key, val in (("PB", player_black), ("PW", player_white), ("DT", date), ("RE", result)):
        if val:
            root.append(f"{key}[{_esc(val)}]")
    if state.initial_board is not None:
        for key, color in (("AB", Color.BLACK), ("AW", Color.WHITE)):
            pts = state.initial_board.stones(color)
            if pts:
                root.append(key + "".join(f"[{point_to_sgf(p, size)}]" for p in pts))
        root.append(f"PL[{state.initial_player.value}]")
    body = "".join(f";{m.color.value}[{point_to_sgf(m.point, size)}]" for m in state.moves)
    return f"(;{''.join(root)}{body})"


# -- import ------------------------------------------------------------------------------


def parse_sgf(text: str) -> SgfGame:
    nodes = _parse_main_line(text)
    if not nodes:
        raise ValueError("SGF has no nodes")
    root = nodes[0]
    if root.get("GM", ["1"])[0] != "1":
        raise ValueError("not a Go SGF (GM != 1)")
    size_str = root.get("SZ", ["19"])[0]
    if ":" in size_str:
        raise ValueError("rectangular boards are not supported")
    size = int(size_str)
    komi = float(root.get("KM", [str(DEFAULT_KOMI)])[0] or DEFAULT_KOMI)

    def pts(node: Node, key: str) -> list[Point]:
        out = []
        for v in node.get(key, []):
            p = sgf_to_point(v, size)
            if p is not None:
                out.append(p)
        return out

    black_setup, white_setup = pts(root, "AB"), pts(root, "AW")
    moves: list[tuple[Color, Point | None]] = []
    for i, node in enumerate(nodes):
        if i > 0 and any(k in node for k in ("AB", "AW", "AE")):
            raise ValueError("setup stones after the root node are not supported")
        for key, color in (("B", Color.BLACK), ("W", Color.WHITE)):
            if key in node:
                moves.append((color, sgf_to_point(node[key][0], size)))
    pl = root.get("PL", [None])[0]
    return SgfGame(
        size=size,
        komi=komi,
        moves=tuple(moves),
        black_setup=tuple(black_setup),
        white_setup=tuple(white_setup),
        player_to_start=Color.parse(pl) if pl else None,
        result=root.get("RE", [None])[0],
        properties={k: v[0] for k, v in root.items() if v},
    )


def _parse_main_line(text: str) -> list[Node]:
    """Return the nodes of the first variation at every branch."""
    i = text.find("(")
    if i < 0:
        raise ValueError("SGF must start with '('")
    nodes: list[Node] = []
    _parse_tree(text, i, nodes)
    return nodes


def _skip_ws(text: str, i: int) -> int:
    while i < len(text) and text[i].isspace():
        i += 1
    return i


def _parse_tree(text: str, i: int, out: list[Node] | None) -> int:
    """Parse `( sequence subtrees )` starting at text[i] == '('. Appends main-line nodes to out."""
    assert text[i] == "("
    i = _skip_ws(text, i + 1)
    while i < len(text) and text[i] == ";":
        node, i = _parse_node(text, i + 1)
        if out is not None:
            out.append(node)
        i = _skip_ws(text, i)
    first = True
    while i < len(text) and text[i] == "(":
        i = _parse_tree(text, i, out if first else None)
        first = False
        i = _skip_ws(text, i)
    if i >= len(text) or text[i] != ")":
        raise ValueError(f"unterminated SGF tree at offset {i}")
    return i + 1


def _parse_node(text: str, i: int) -> tuple[Node, int]:
    node: Node = {}
    while True:
        i = _skip_ws(text, i)
        j = i
        while j < len(text) and text[j].isalpha():
            j += 1
        if j == i:
            return node, i
        ident = "".join(c for c in text[i:j] if c.isupper())  # FF[3] allows lowercase noise
        i = _skip_ws(text, j)
        values = []
        while i < len(text) and text[i] == "[":
            val, i = _parse_value(text, i + 1)
            values.append(val)
            i = _skip_ws(text, i)
        if not values:
            raise ValueError(f"property {ident} without value at offset {i}")
        node.setdefault(ident, []).extend(values)


def _parse_value(text: str, i: int) -> tuple[str, int]:
    buf = []
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt != "\n":  # escaped newline = soft line break, dropped
                buf.append(nxt)
            i += 2
            continue
        if c == "]":
            return "".join(buf), i + 1
        buf.append(c)
        i += 1
    raise ValueError("unterminated SGF value")
