import { describe, expect, it } from "vitest";
import en from "../messages/en.json";
import th from "../messages/th.json";

function keys(obj: object, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === "object" && v !== null ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

describe("i18n messages", () => {
  it("th and en define exactly the same keys", () => {
    expect(keys(th).sort()).toEqual(keys(en).sort());
  });

  it("has no empty strings", () => {
    for (const msgs of [th, en]) {
      for (const k of keys(msgs)) {
        const v = k.split(".").reduce<unknown>((o, p) => (o as Record<string, unknown>)[p], msgs);
        expect(v, k).not.toBe("");
      }
    }
  });
});
