import { setRequestLocale } from "next-intl/server";
import { use } from "react";
import { ProgressClient } from "./ProgressClient";

export default function ProgressPage({ params }: PageProps<"/[locale]/progress">) {
  const { locale } = use(params);
  setRequestLocale(locale);
  return <ProgressClient />;
}
