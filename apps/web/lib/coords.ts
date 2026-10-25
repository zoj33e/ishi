/**
 * The only coordinate conversion on the frontend (mirror of apps/api/ishi/rules/coords.py).
 * GTP: columns A–T skipping I, rows from the bottom ("A1" = bottom-left), "pass".
 * XY:  x = 0 left column, y = 0 TOP row (SVG order).
 */

export const GTP_COLUMNS = "ABCDEFGHJKLMNOPQRST";
export const PASS = "pass";

export type XY = { x: number; y: number };

export function gtpToXY(gtp: string, size: number): XY | null {
  const t = gtp.trim().toUpperCase();
  if (t === "PASS") return null;
  const x = GTP_COLUMNS.indexOf(t[0] ?? "");
  const row = Number(t.slice(1));
  if (x < 0 || x >= size || !/^\d+$/.test(t.slice(1)) || row < 1 || row > size) {
    throw new Error(`bad GTP coordinate ${gtp} for ${size}x${size}`);
  }
  return { x, y: size - row };
}

export function xyToGtp({ x, y }: XY, size: number): string {
  if (x < 0 || y < 0 || x >= size || y >= size) throw new Error(`(${x},${y}) off board`);
  return `${GTP_COLUMNS[x]}${size - y}`;
}

/** Column letters for board labels, left to right. */
export function columnLabels(size: number): string[] {
  return GTP_COLUMNS.slice(0, size).split("");
}

const STAR_POINTS: Record<number, string[]> = {
  9: ["C3", "G3", "E5", "C7", "G7"],
  13: ["D4", "K4", "G7", "D10", "K10"],
  19: ["D4", "K4", "Q4", "D10", "K10", "Q10", "D16", "K16", "Q16"],
};

export function starPoints(size: number): string[] {
  return STAR_POINTS[size] ?? [];
}
