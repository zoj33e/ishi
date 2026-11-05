import { setRequestLocale } from "next-intl/server";
import { use } from "react";
import { GymClient } from "./GymClient";

export default function GymPage({ params, searchParams }: PageProps<"/[locale]/gym">) {
  const { locale } = use(params);
  const { warmup } = use(searchParams);
  setRequestLocale(locale);
  return <GymClient context={warmup ? "warmup" : "gym"} />;
}
