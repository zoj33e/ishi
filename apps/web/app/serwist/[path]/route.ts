import { spawnSync } from "node:child_process";
import { createSerwistRoute } from "@serwist/turbopack";

// Bump the precache revision per git commit (falls back to a random id outside git).
const revision =
  spawnSync("git", ["rev-parse", "HEAD"], { encoding: "utf-8" }).stdout?.trim() || crypto.randomUUID();

export const { dynamic, dynamicParams, revalidate, generateStaticParams, GET } = createSerwistRoute({
  additionalPrecacheEntries: [{ url: "/th", revision }, { url: "/en", revision }],
  swSrc: "app/sw.ts",
  useNativeEsbuild: true,
});
