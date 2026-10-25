import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" };

export function Button({ variant = "secondary", className, children, ...props }: ButtonProps) {
  const look =
    variant === "primary" ? "bg-ink text-paper border-ink" : "bg-card text-ink border-line";
  return (
    <button
      type="button"
      className={`min-h-11 rounded-full border px-5 font-semibold disabled:opacity-40 ${look} ${className ?? ""}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function Card({ title, children, className }: { title?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`flex flex-col gap-3 rounded-2xl border border-line bg-card p-4 shadow-sm ${className ?? ""}`}>
      {title && <h2 className="text-lg font-semibold">{title}</h2>}
      {children}
    </section>
  );
}
