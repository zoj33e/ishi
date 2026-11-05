"use client";

import { useTranslations } from "next-intl";
import { type KeyboardEvent, type PointerEvent, useEffect, useId, useMemo, useRef, useState } from "react";
import { columnLabels, gtpToXY, starPoints, xyToGtp, type XY } from "@/lib/coords";

export type StoneColor = "black" | "white";
export type MarkKind = "circle" | "triangle" | "square" | "cross" | "label";
export type Mark = { point: string; kind: MarkKind; label?: string };

export type BoardProps = {
  size: number;
  stones: { black: string[]; white: string[] };
  toMove?: StoneColor;
  lastMove?: string | null;
  marks?: Mark[];
  /** Stones drawn see-through (lessons: the learner's actual move). */
  faded?: { point: string; color: StoneColor }[];
  /** Center of a highlighted 3x3 area (hint level 2). */
  highlight?: string | null;
  /** Empty points owned by each color, drawn as small squares (scoring view). */
  territory?: { black: string[]; white: string[] };
  showCoordinates?: boolean;
  /** When false the board is read-only (lessons, demos). */
  interactive?: boolean;
  /** Called once a ghost stone is confirmed. The backend decides legality. */
  onPlay?: (point: string) => void;
  /** Fired whenever the ghost moves (later: triggers the nudge preview). */
  onGhost?: (point: string | null) => void;
  /** Select mode (lessons): one tap/click/Enter on any point, stone or empty, calls this; no ghost. */
  onSelect?: (point: string) => void;
  className?: string;
};

const CELL = 10;

export function Board({
  size,
  stones,
  toMove = "black",
  lastMove = null,
  marks = [],
  faded = [],
  highlight = null,
  territory,
  showCoordinates = false,
  interactive = true,
  onPlay,
  onGhost,
  onSelect,
  className,
}: BoardProps) {
  const t = useTranslations("board");
  const gradId = useId();
  const pad = showCoordinates ? CELL * 1.2 : CELL * 0.7;
  const span = (size - 1) * CELL;
  const view = span + pad * 2;
  const at = (i: number) => pad + i * CELL;

  const occupied = useMemo(() => {
    const m = new Map<string, StoneColor>();
    for (const p of stones.black) m.set(p, "black");
    for (const p of stones.white) m.set(p, "white");
    return m;
  }, [stones]);

  const [ghost, setGhost] = useState<string | null>(null);
  const [focus, setFocus] = useState<string>(() => xyToGtp({ x: Math.floor(size / 2), y: Math.floor(size / 2) }, size));
  const cellRefs = useRef(new Map<string, SVGRectElement>());

  // A new position (move played, undo, new game) clears the ghost.
  const positionKey = `${size}|${stones.black.join(",")}|${stones.white.join(",")}|${toMove}`;
  const [lastKey, setLastKey] = useState(positionKey);
  if (positionKey !== lastKey) {
    setLastKey(positionKey);
    setGhost(null);
  }
  useEffect(() => onGhost?.(ghost), [ghost, onGhost]);

  const tap = (point: string) => {
    if (!interactive) return;
    if (onSelect) {
      onSelect(point);
      return;
    }
    if (occupied.has(point)) return;
    if (ghost === point) {
      setGhost(null);
      onPlay?.(point);
    } else {
      setGhost(point);
    }
  };

  const onPointerUp = (e: PointerEvent, point: string) => {
    if (!interactive) return;
    if (e.pointerType === "mouse" && !onSelect) {
      // Desktop: hover already shows the ghost, one click confirms.
      if (!occupied.has(point)) {
        setGhost(null);
        onPlay?.(point);
      }
    } else {
      tap(point); // touch / pen: tap to place ghost, tap again to confirm
    }
  };

  const onPointerMove = (e: PointerEvent, point: string) => {
    if (interactive && !onSelect && e.pointerType === "mouse") setGhost(occupied.has(point) ? null : point);
  };

  const onKeyDown = (e: KeyboardEvent, point: string) => {
    const xy = gtpToXY(point, size)!;
    const delta: Record<string, XY> = {
      ArrowLeft: { x: -1, y: 0 },
      ArrowRight: { x: 1, y: 0 },
      ArrowUp: { x: 0, y: -1 },
      ArrowDown: { x: 0, y: 1 },
    };
    const d = delta[e.key];
    if (d) {
      e.preventDefault();
      const next = { x: Math.min(size - 1, Math.max(0, xy.x + d.x)), y: Math.min(size - 1, Math.max(0, xy.y + d.y)) };
      const p = xyToGtp(next, size);
      setFocus(p);
      cellRefs.current.get(p)?.focus();
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      tap(point);
    } else if (e.key === "Escape") {
      setGhost(null);
    }
  };

  const cols = columnLabels(size);
  const points: string[] = [];
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) points.push(xyToGtp({ x, y }, size));

  const pointState = (p: string) => {
    const c = occupied.get(p);
    return c ? t(`stone.${c}`) : t("empty");
  };

  return (
    <svg
      viewBox={`0 0 ${view} ${view}`}
      className={`block w-full touch-manipulation select-none ${className ?? ""}`}
      role="grid"
      aria-label={t("label", { size })}
      onPointerLeave={(e) => e.pointerType === "mouse" && setGhost(null)}
    >
      <defs>
        <radialGradient id={`${gradId}-b`} cx="35%" cy="30%" r="70%">
          <stop offset="0%" stopColor="#5a554e" />
          <stop offset="55%" stopColor="#1f1b16" />
          <stop offset="100%" stopColor="#0c0a08" />
        </radialGradient>
        <radialGradient id={`${gradId}-w`} cx="35%" cy="30%" r="75%">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="70%" stopColor="#eeeae2" />
          <stop offset="100%" stopColor="#c9c3b8" />
        </radialGradient>
      </defs>

      {/* wood */}
      <rect width={view} height={view} rx={CELL * 0.4} style={{ fill: "var(--wood)" }} />

      {/* grid */}
      <g style={{ stroke: "var(--grid)" }} strokeWidth={0.35} strokeLinecap="square">
        {Array.from({ length: size }, (_, i) => (
          <g key={i}>
            <line x1={at(0)} y1={at(i)} x2={at(size - 1)} y2={at(i)} />
            <line x1={at(i)} y1={at(0)} x2={at(i)} y2={at(size - 1)} />
          </g>
        ))}
      </g>
      {starPoints(size).map((p) => {
        const { x, y } = gtpToXY(p, size)!;
        return <circle key={p} cx={at(x)} cy={at(y)} r={0.9} style={{ fill: "var(--grid)" }} />;
      })}

      {showCoordinates && (
        <g fontSize={3.4} style={{ fill: "var(--grid)" }} textAnchor="middle" dominantBaseline="central" aria-hidden="true">
          {cols.map((c, i) => (
            <text key={c} x={at(i)} y={pad * 0.45}>
              {c}
            </text>
          ))}
          {Array.from({ length: size }, (_, i) => (
            <text key={i} x={pad * 0.45} y={at(i)}>
              {size - i}
            </text>
          ))}
        </g>
      )}

      {/* territory (scoring view) */}
      {territory &&
        (["black", "white"] as const).flatMap((c) =>
          territory[c].map((p) => {
            const { x, y } = gtpToXY(p, size)!;
            return (
              <rect
                key={`t-${p}`}
                x={at(x) - 1.6}
                y={at(y) - 1.6}
                width={3.2}
                height={3.2}
                fill={c === "black" ? "#1f1b16" : "#f6f1e7"}
                stroke={c === "white" ? "#8a8274" : "none"}
                strokeWidth={0.3}
                opacity={0.85}
              />
            );
          }),
        )}

      {/* highlighted area (hint level 2) */}
      {highlight && (() => {
        const c = gtpToXY(highlight, size);
        if (!c) return null;
        const x0 = Math.max(0, c.x - 1);
        const x1 = Math.min(size - 1, c.x + 1);
        const y0 = Math.max(0, c.y - 1);
        const y1 = Math.min(size - 1, c.y + 1);
        return (
          <rect
            data-testid="highlight"
            x={at(x0) - CELL / 2}
            y={at(y0) - CELL / 2}
            width={(x1 - x0 + 1) * CELL}
            height={(y1 - y0 + 1) * CELL}
            rx={CELL * 0.3}
            style={{ fill: "var(--hint)", stroke: "var(--hint-edge)" }}
            strokeWidth={0.6}
            pointerEvents="none"
          />
        );
      })()}

      {/* stones */}
      {[...occupied].map(([p, c]) => {
        const { x, y } = gtpToXY(p, size)!;
        return (
          <g key={`${p}-${c}`} className={p === lastMove ? "stone-drop" : undefined} style={{ transformOrigin: `${at(x)}px ${at(y)}px` }}>
            <circle cx={at(x) + 0.35} cy={at(y) + 0.55} r={CELL * 0.47} fill="rgba(0,0,0,0.25)" />
            <circle cx={at(x)} cy={at(y)} r={CELL * 0.47} fill={`url(#${gradId}-${c === "black" ? "b" : "w"})`} />
          </g>
        );
      })}

      {/* faded stones (the learner's actual move in a lesson) */}
      {faded
        .filter((f) => !occupied.has(f.point))
        .map((f) => {
          const { x, y } = gtpToXY(f.point, size)!;
          return (
            <circle
              key={`f-${f.point}`}
              data-testid="faded"
              data-point={f.point}
              cx={at(x)}
              cy={at(y)}
              r={CELL * 0.47}
              fill={`url(#${gradId}-${f.color === "black" ? "b" : "w"})`}
              opacity={0.45}
              pointerEvents="none"
            />
          );
        })}

      {/* last-move marker */}
      {lastMove && occupied.has(lastMove) && (() => {
        const { x, y } = gtpToXY(lastMove, size)!;
        const c = occupied.get(lastMove);
        return (
          <circle
            data-testid="last-move"
            cx={at(x)}
            cy={at(y)}
            r={CELL * 0.2}
            fill="none"
            stroke={c === "black" ? "#f6f1e7" : "#1f1b16"}
            strokeWidth={0.8}
          />
        );
      })()}

      {/* marks */}
      {marks.map((m) => (
        <MarkGlyph key={`${m.kind}-${m.point}`} mark={m} cx={at(gtpToXY(m.point, size)!.x)} cy={at(gtpToXY(m.point, size)!.y)} color={occupied.get(m.point)} />
      ))}

      {/* ghost stone */}
      {ghost && (() => {
        const { x, y } = gtpToXY(ghost, size)!;
        return (
          <circle
            data-testid="ghost"
            data-point={ghost}
            cx={at(x)}
            cy={at(y)}
            r={CELL * 0.47}
            fill={`url(#${gradId}-${toMove === "black" ? "b" : "w"})`}
            opacity={0.5}
            pointerEvents="none"
          />
        );
      })()}

      {/* input layer: one cell per intersection, roving tabindex for keyboard play */}
      <g fill="transparent">
        {points.map((p) => {
          const { x, y } = gtpToXY(p, size)!;
          return (
            <rect
              key={p}
              ref={(el) => {
                if (el) cellRefs.current.set(p, el);
                else cellRefs.current.delete(p);
              }}
              data-point={p}
              role="gridcell"
              aria-label={`${p}, ${pointState(p)}`}
              aria-disabled={!interactive || occupied.has(p)}
              tabIndex={interactive && p === focus ? 0 : -1}
              x={at(x) - CELL / 2}
              y={at(y) - CELL / 2}
              width={CELL}
              height={CELL}
              className="outline-none focus-visible:stroke-[var(--ink)] focus-visible:[stroke-width:0.6]"
              onPointerUp={(e) => onPointerUp(e, p)}
              onPointerMove={(e) => onPointerMove(e, p)}
              onFocus={() => setFocus(p)}
              onKeyDown={(e) => onKeyDown(e, p)}
            />
          );
        })}
      </g>
    </svg>
  );
}

function MarkGlyph({ mark, cx, cy, color }: { mark: Mark; cx: number; cy: number; color?: StoneColor }) {
  const ink = color === "black" ? "#f6f1e7" : "#1f1b16";
  const r = CELL * 0.26;
  const common = { fill: "none", stroke: ink, strokeWidth: 0.8, pointerEvents: "none" as const };
  switch (mark.kind) {
    case "circle":
      return <circle cx={cx} cy={cy} r={r} {...common} />;
    case "square":
      return <rect x={cx - r * 0.85} y={cy - r * 0.85} width={r * 1.7} height={r * 1.7} {...common} />;
    case "triangle":
      return <polygon points={`${cx},${cy - r} ${cx - r * 0.9},${cy + r * 0.6} ${cx + r * 0.9},${cy + r * 0.6}`} {...common} />;
    case "cross":
      return (
        <path d={`M${cx - r * 0.8} ${cy - r * 0.8}L${cx + r * 0.8} ${cy + r * 0.8}M${cx + r * 0.8} ${cy - r * 0.8}L${cx - r * 0.8} ${cy + r * 0.8}`} {...common} style={{ stroke: "var(--bad)" }} strokeWidth={1} />
      );
    case "label":
      return (
        <text x={cx} y={cy} fontSize={4.6} fontWeight={600} textAnchor="middle" dominantBaseline="central" fill={ink} pointerEvents="none">
          {mark.label}
        </text>
      );
  }
}
