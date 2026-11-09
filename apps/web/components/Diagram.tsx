import { useId } from "react";

export type DiagramStone = {
  /** column, row from the top-left corner, 0-based */
  at: [number, number];
  color: "b" | "w";
  /** a teaching mark drawn on the stone */
  mark?: "triangle" | "cross";
  /** stone that is about to be removed: drawn faint */
  ghost?: boolean;
};

type Props = {
  /** lines on the full board (9 for 9x9) */
  size?: number;
  stones: DiagramStone[];
  /** visible window [x0, y0, x1, y1] (inclusive); lines run past an edge that is not the board's */
  view?: [number, number, number, number];
  /** empty points to shade (e.g. surrounded area) */
  shade?: [number, number][];
  /** stones drop in one by one */
  animate?: boolean;
  label: string;
  className?: string;
};

const CELL = 10;
const STAR_9 = [
  [2, 2],
  [6, 2],
  [4, 4],
  [2, 6],
  [6, 6],
];

/** A static board diagram, like the figures in a Go book. Not interactive. */
export function Diagram({ size = 9, stones, view, shade = [], animate = false, label, className }: Props) {
  const id = useId().replace(/:/g, "");
  const [x0, y0, x1, y1] = view ?? [0, 0, size - 1, size - 1];
  const pad = CELL * 0.75;
  const w = (x1 - x0) * CELL + pad * 2;
  const h = (y1 - y0) * CELL + pad * 2;
  const px = (x: number) => pad + (x - x0) * CELL;
  const py = (y: number) => pad + (y - y0) * CELL;
  // a line stops at the board's own edge, and runs off the figure where the board goes on
  const left = x0 === 0 ? px(0) : 0;
  const right = x1 === size - 1 ? px(size - 1) : w;
  const top = y0 === 0 ? py(0) : 0;
  const bottom = y1 === size - 1 ? py(size - 1) : h;
  const cols = Array.from({ length: x1 - x0 + 1 }, (_, i) => x0 + i);
  const rows = Array.from({ length: y1 - y0 + 1 }, (_, i) => y0 + i);
  const stars = size === 9 ? STAR_9.filter(([x, y]) => x >= x0 && x <= x1 && y >= y0 && y <= y1) : [];

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={className} role="img" aria-label={label}>
      <defs>
        <linearGradient id={`${id}-wood`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="var(--wood-light)" />
          <stop offset="1" stopColor="var(--wood)" />
        </linearGradient>
        <radialGradient id={`${id}-b`} cx="35%" cy="30%" r="75%">
          <stop offset="0" stopColor="#5a5550" />
          <stop offset="0.45" stopColor="#1d1b18" />
          <stop offset="1" stopColor="#0c0b0a" />
        </radialGradient>
        <radialGradient id={`${id}-w`} cx="35%" cy="30%" r="80%">
          <stop offset="0" stopColor="#ffffff" />
          <stop offset="0.7" stopColor="#f1ece2" />
          <stop offset="1" stopColor="#cfc6b6" />
        </radialGradient>
      </defs>
      <rect width={w} height={h} rx="2" fill={`url(#${id}-wood)`} />
      {shade.map(([x, y]) => (
        <rect
          key={`s${x},${y}`}
          x={px(x) - CELL / 2}
          y={py(y) - CELL / 2}
          width={CELL}
          height={CELL}
          fill="var(--ink)"
          opacity="0.12"
        />
      ))}
      <g stroke="var(--grid)" strokeWidth="0.45" strokeLinecap="square">
        {cols.map((x) => (
          <line key={`c${x}`} x1={px(x)} x2={px(x)} y1={top} y2={bottom} />
        ))}
        {rows.map((y) => (
          <line key={`r${y}`} x1={left} x2={right} y1={py(y)} y2={py(y)} />
        ))}
      </g>
      {stars.map(([x, y]) => (
        <circle key={`p${x},${y}`} cx={px(x)} cy={py(y)} r="0.9" fill="var(--grid)" />
      ))}
      {stones.map((s, i) => (
        <g
          key={`${s.at[0]},${s.at[1]}`}
          className={animate ? "stone-drop" : undefined}
          style={animate ? { animationDelay: `${180 + i * 110}ms`, animationFillMode: "backwards" } : undefined}
        >
          {/* the drop animation owns the outer group's opacity, so a ghost fades on an inner one */}
          <g opacity={s.ghost ? 0.38 : 1}>
            <circle cx={px(s.at[0]) + 0.35} cy={py(s.at[1]) + 0.55} r={CELL * 0.47} fill="rgba(40,25,5,0.28)" />
            <circle cx={px(s.at[0])} cy={py(s.at[1])} r={CELL * 0.47} fill={`url(#${id}-${s.color})`} />
          </g>
          {s.mark === "triangle" && (
            <path
              d={`M${px(s.at[0])} ${py(s.at[1]) - 2.6} l2.4 4.2 h-4.8 z`}
              fill="none"
              stroke={s.color === "b" ? "#fff" : "var(--seal)"}
              strokeWidth="0.8"
              strokeLinejoin="round"
            />
          )}
          {s.mark === "cross" && (
            <path
              d={`M${px(s.at[0]) - 2} ${py(s.at[1]) - 2} l4 4 M${px(s.at[0]) + 2} ${py(s.at[1]) - 2} l-4 4`}
              stroke="var(--seal)"
              strokeWidth="0.9"
              strokeLinecap="round"
            />
          )}
        </g>
      ))}
    </svg>
  );
}
