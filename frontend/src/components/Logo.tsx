/** SideQuest wordmark with the hexagon route badge. */
export default function Logo({ size = "md" }: { size?: "md" | "lg" }) {
  const big = size === "lg";
  return (
    <span className="flex items-center gap-2.5">
      <span
        className={`hex flex shrink-0 items-center justify-center bg-gradient-to-br from-brand-300 via-cyan-400 to-violet-500 ${big ? "h-11 w-12" : "h-9 w-10"}`}
        aria-hidden
      >
        <svg viewBox="0 0 24 24" className={big ? "h-6 w-6" : "h-5 w-5"} fill="none" stroke="#050816" strokeWidth="2.4" strokeLinecap="round">
          <path d="M5 19c4-1 3-7 7-8s5-6 7-6" />
          <circle cx="5" cy="19" r="2" fill="#050816" />
          <circle cx="19" cy="5" r="2" fill="#050816" />
        </svg>
      </span>
      <span className="leading-none">
        <span className={`block font-logo tracking-wide text-white ${big ? "text-2xl" : "text-lg"}`}>
          Side<span className="text-gradient">Quest</span>
        </span>
        <span className="block font-display text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-400">Stop planner · SG</span>
      </span>
    </span>
  );
}
