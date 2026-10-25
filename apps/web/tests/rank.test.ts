import { describe, expect, it } from "vitest";
import { rankLabel } from "@/lib/rank";

describe("rankLabel", () => {
  it("matches the backend kyu/dan scale", () => {
    expect(rankLabel(30)).toBe("30k");
    expect(rankLabel(1)).toBe("1k");
    expect(rankLabel(0)).toBe("1d");
    expect(rankLabel(-4)).toBe("5d");
  });
});
