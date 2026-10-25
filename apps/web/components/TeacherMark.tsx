/** The teacher's avatar: a black stone with a brush stroke (original mark). */
export function TeacherMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <circle cx="32" cy="32" r="30" style={{ fill: "var(--wood)" }} />
      <circle cx="32" cy="33" r="20" fill="#1f1b16" />
      <path
        d="M19.2 28.3A13.6 13.6 0 0 1 29.6 19.6"
        stroke="#f6f1e7"
        strokeWidth="3"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
}
