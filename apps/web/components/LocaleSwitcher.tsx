"use client";

import { useLocale, useTranslations } from "next-intl";
import { usePathname, useRouter } from "@/i18n/navigation";
import { routing, type Locale } from "@/i18n/routing";
import { patchMe } from "@/lib/api";

const LABELS: Record<Locale, string> = { th: "ไทย", en: "English" };

export function LocaleSwitcher() {
  const t = useTranslations("home");
  const locale = useLocale() as Locale;
  const router = useRouter();
  const pathname = usePathname();

  return (
    <div role="group" aria-label={t("language")} className="flex rounded-control border border-line p-0.5 text-sm">
      {routing.locales.map((l) => (
        <button
          key={l}
          type="button"
          aria-pressed={l === locale}
          onClick={() => {
            patchMe({ locale: l }).catch(() => undefined); // remember the choice; the URL already switches
            router.replace(pathname, { locale: l });
          }}
          className={`min-h-9 rounded-lg px-3 transition-colors duration-150 ${l === locale ? "bg-ink text-paper" : "text-ink-soft"}`}
        >
          {LABELS[l]}
        </button>
      ))}
    </div>
  );
}
