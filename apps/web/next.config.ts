import { withSerwist } from "@serwist/turbopack";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const apiUrl = process.env.ISHI_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // cacheComponents stays off: @serwist/turbopack's route handler relies on segment config
  // (`dynamic = "force-static"`), which cacheComponents forbids. See D-014.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // The browser only ever talks to this origin; /api/* is proxied to FastAPI.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
};

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

export default withSerwist(withNextIntl(nextConfig));
