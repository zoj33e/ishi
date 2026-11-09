import type { ButtonHTMLAttributes, ComponentProps, ReactNode } from "react";
import { Link } from "@/i18n/navigation";

type Variant = "primary" | "secondary" | "quiet";
type Size = "md" | "lg";

const LOOK: Record<Variant, string> = {
  primary: "bg-ink text-paper border-ink hover:bg-ink-raised active:scale-[0.98]",
  secondary: "bg-card text-ink border-line hover:border-ink-soft active:scale-[0.98]",
  quiet: "bg-transparent text-ink border-transparent underline underline-offset-4 hover:text-seal",
};
const SIZE: Record<Size, string> = {
  md: "min-h-11 px-5",
  lg: "min-h-14 w-full px-6 text-lg",
};

export function buttonClass(variant: Variant = "secondary", size: Size = "md", extra = "") {
  return `inline-flex items-center justify-center gap-2 rounded-control border font-semibold transition-[background-color,border-color,transform,color] duration-150 disabled:pointer-events-none disabled:opacity-40 ${LOOK[variant]} ${SIZE[size]} ${extra}`;
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size };

export function Button({ variant = "secondary", size = "md", className, children, ...props }: ButtonProps) {
  return (
    <button type="button" className={buttonClass(variant, size, className ?? "")} {...props}>
      {children}
    </button>
  );
}

type ButtonLinkProps = ComponentProps<typeof Link> & { variant?: Variant; size?: Size };

/** A link that looks like a button (navigation, not an action). */
export function ButtonLink({ variant = "secondary", size = "md", className, children, ...props }: ButtonLinkProps) {
  return (
    <Link className={buttonClass(variant, size, className ?? "")} {...props}>
      {children}
    </Link>
  );
}

export function Card({ title, children, className }: { title?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section
      className={`flex flex-col gap-3 rounded-2xl border border-line bg-card p-5 shadow-soft ${className ?? ""}`}
    >
      {title && <h2 className="text-xl font-semibold">{title}</h2>}
      {children}
    </section>
  );
}
