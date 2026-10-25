import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

export default createMiddleware(routing);

export const config = {
  // Skip API proxy, service worker files, Next internals and anything with a file extension.
  matcher: "/((?!api|serwist|_next|_vercel|.*\\..*).*)",
};
