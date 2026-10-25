"use client";

import { useTranslations } from "next-intl";
import { useCallback } from "react";
import { ApiError } from "./api";

/** Turns an API failure into a translated sentence (`errors.*`, with move reasons). */
export function useErrorText() {
  const te = useTranslations("errors");
  return useCallback(
    (e: unknown): string => {
      if (!(e instanceof ApiError)) return te("invalid_request");
      const reason = e.detail.details?.reason;
      if (e.detail.code === "ILLEGAL_MOVE" && typeof reason === "string") {
        return te(`reason.${reason}` as "reason.ko");
      }
      const key = e.detail.message_key.replace(/^errors\./, "");
      return te.has(key as "network") ? te(key as "network") : te("invalid_request");
    },
    [te],
  );
}
