import { setRequestLocale } from "next-intl/server";
import { use } from "react";
import { WelcomeClient } from "./WelcomeClient";

export default function WelcomePage({ params }: PageProps<"/[locale]/welcome">) {
  const { locale } = use(params);
  setRequestLocale(locale);
  return <WelcomeClient />;
}
