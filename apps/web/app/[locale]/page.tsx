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
    <main className="mx-auto flex max-w-md flex-col gap-6 px-4 py-8">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <TeacherMark className="h-11 w-11" />
          <div>
            <h1 className="text-2xl font-semibold">{t("app.name")}</h1>
            <p className="text-ink-soft">{t("app.tagline")}</p>
          </div>
        </div>
        <LocaleSwitcher />
      </header>
      <HomeClient />
      <details className="rounded-2xl border border-line p-4">
        <summary className="cursor-pointer font-semibold">{t("health.title")}</summary>
        <div className="mt-3 flex flex-col gap-3">
          <HealthStatus />
          <Link href="/sandbox" className="self-start py-2 underline underline-offset-4">
            {t("home.sandboxLink")}
          </Link>
        </div>
      </details>
    </main>
  );
}
