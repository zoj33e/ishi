import { setRequestLocale } from "next-intl/server";
import { use } from "react";
import { SandboxClient } from "./SandboxClient";

export default function SandboxPage({ params }: PageProps<"/[locale]/sandbox">) {
  const { locale } = use(params);
  setRequestLocale(locale);
  return <SandboxClient />;
}
