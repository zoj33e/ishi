import { describe, expect, it } from "vitest";
import { columnLabels, gtpToXY, starPoints, xyToGtp } from "@/lib/coords";

describe("coords (mirror of ishi/rules/coords.py)", () => {
  it.each([
    ["A1", 9, { x: 0, y: 8 }],
    ["A9", 9, { x: 0, y: 0 }],
    ["J9", 9, { x: 8, y: 0 }],
    ["E5", 9, { x: 4, y: 4 }],
    ["T19", 19, { x: 18, y: 0 }],
  ] as const)("%s on %ix%i", (gtp, size, xy) => {
    expect(gtpToXY(gtp, size)).toEqual(xy);
    expect(xyToGtp(xy, size)).toBe(gtp);
  });

  it("skips I and rejects off-board", () => {
    expect(columnLabels(9).join("")).toBe("ABCDEFGHJ");
    for (const bad of ["I5", "K1", "A10", "A0", "E"]) expect(() => gtpToXY(bad, 9)).toThrow();
    expect(gtpToXY("pass", 9)).toBeNull();
  });

  it("has star points for standard sizes", () => {
    expect(starPoints(9)).toContain("E5");
    expect(starPoints(19)).toHaveLength(9);
    expect(starPoints(7)).toEqual([]);
  });
});
