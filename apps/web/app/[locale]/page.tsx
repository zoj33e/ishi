import { useTranslations } from "next-intl";
import { setRequestLocale } from "next-intl/server";
import { use } from "react";
import { HealthStatus } from "@/components/HealthStatus";
import { Link } from "@/i18n/navigation";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { TeacherMark } from "@/components/TeacherMark";
import { HomeClient } from "./HomeClient";

export default function HomePage({ params }: PageProps<"/[locale]">) {
  const { locale } = use(params);
  setRequestLocale(locale);
  const t = useTranslations();

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col gap-6 px-4 pb-8 pt-5">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <TeacherMark className="size-10" />
          <div className="flex flex-col">
            <h1 className="text-xl font-semibold leading-tight">{t("app.name")}</h1>
            <p className="text-sm leading-snug text-ink-soft">{t("app.tagline")}</p>
          </div>
        </div>
        <LocaleSwitcher />
      </header>
      <HomeClient />
      <footer className="mt-auto flex flex-col gap-2 border-t border-line pt-4 text-sm text-ink-soft">
        <Link href="/sandbox" className="self-start py-1 underline hover:text-seal">
          {t("home.sandboxLink")}
        </Link>
        <details>
          <summary className="cursor-pointer py-1">{t("health.title")}</summary>
          <div className="mt-2">
            <HealthStatus />
          </div>
        </details>
      </footer>
    </main>
  );
}
