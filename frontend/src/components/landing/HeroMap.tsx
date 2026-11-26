import { useLayoutEffect, useRef, useState } from "react";

const ROUTE = "M70 350 C 150 335, 120 255, 205 245 S 305 280, 330 195 S 400 95, 455 75";

const CHECKPOINTS = [
  { at: 0.3, icon: "🕌", label: "Masjid", cost: "+3 min", grad: ["#fde68a", "#f59e0b"], side: -1 },
  { at: 0.58, icon: "🍨", label: "Halal ice cream", cost: "+5 min", grad: ["#fdba74", "#f43f5e"], side: 1 },
  { at: 0.8, icon: "⛽", label: "Petrol", cost: "COMBO +0", grad: ["#c4b5fd", "#a21caf"], side: -1 },
];

type Pt = { x: number; y: number };
const reduced = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Hero illustration: a trip drawn as a game level, with a player running it. */
export default function HeroMap() {
  const path = useRef<SVGPathElement>(null);
  const [pts, setPts] = useState<Pt[]>([]);
  const [prayer, setPrayer] = useState<Pt | null>(null);
  const motion = !reduced();

  useLayoutEffect(() => {
    const p = path.current;
    if (!p) return;
    const L = p.getTotalLength();
    setPts(CHECKPOINTS.map((c) => p.getPointAtLength(L * c.at)));
    setPrayer(p.getPointAtLength(L * 0.22));
  }, []);

  return (
    <svg viewBox="0 0 520 420" className="h-auto w-full" role="img" aria-label="Illustration: a route from A to the finish flag with three stops along the way">
      <defs>
        <linearGradient id="hm-route" x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="#34d399" />
          <stop offset="0.5" stopColor="#22d3ee" />
          <stop offset="1" stopColor="#f472b6" />
        </linearGradient>
        <pattern id="hm-grid" width="26" height="26" patternUnits="userSpaceOnUse">
          <path d="M26 0H0V26" fill="none" stroke="rgba(148,163,184,0.09)" strokeWidth="1" />
        </pattern>
        <filter id="hm-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="6" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        <radialGradient id="hm-vignette" cx="50%" cy="45%" r="70%">
          <stop offset="0.6" stopColor="#0a1024" stopOpacity="0" />
          <stop offset="1" stopColor="#050816" stopOpacity="0.9" />
        </radialGradient>
        {CHECKPOINTS.map((c, i) => (
          <linearGradient key={i} id={`hm-cp${i}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor={c.grad[0]} />
            <stop offset="1" stopColor={c.grad[1]} />
          </linearGradient>
        ))}
      </defs>

      {/* board */}
      <rect x="4" y="4" width="512" height="412" rx="28" fill="#0a1024" stroke="rgba(255,255,255,0.1)" />
      <rect x="4" y="4" width="512" height="412" rx="28" fill="url(#hm-grid)" />
      {/* city blocks + water */}
      <path d="M4 300 C 90 280, 140 330, 230 330 S 400 300, 516 340 V 416 H 4 Z" fill="rgba(34,211,238,0.07)" />
      {[
        [40, 60, 90, 50],
        [150, 40, 70, 80],
        [250, 70, 60, 40],
        [360, 150, 80, 60],
        [60, 150, 70, 60],
        [400, 230, 70, 50],
        [250, 330, 90, 40],
        [120, 380, 60, 25],
      ].map(([x, y, w, h], i) => (
        <rect key={i} x={x} y={y} width={w} height={h} rx="8" fill="rgba(148,163,184,0.06)" stroke="rgba(148,163,184,0.08)" />
      ))}

      {/* route: glow, base, marching dashes */}
      <path ref={path} d={ROUTE} fill="none" stroke="url(#hm-route)" strokeWidth="14" strokeLinecap="round" opacity="0.35" filter="url(#hm-glow)" />
      <path d={ROUTE} fill="none" stroke="#050816" strokeWidth="10" strokeLinecap="round" />
      <path d={ROUTE} fill="none" stroke="url(#hm-route)" strokeWidth="5" strokeLinecap="round" />
      <path d={ROUTE} fill="none" stroke="rgba(255,255,255,0.75)" strokeWidth="1.6" strokeLinecap="round" strokeDasharray="2 12">
        {motion && <animate attributeName="stroke-dashoffset" from="28" to="0" dur="1s" repeatCount="indefinite" />}
      </path>

      {/* prayer-time marker: where you'll be when Asar begins */}
      {prayer && (
        <g transform={`translate(${prayer.x} ${prayer.y})`}>
          <circle r="15" fill="none" stroke="#fbbf24" strokeWidth="2" opacity="0.6">
            {motion && <animate attributeName="r" values="12;26" dur="2.2s" repeatCount="indefinite" />}
            {motion && <animate attributeName="opacity" values="0.7;0" dur="2.2s" repeatCount="indefinite" />}
          </circle>
          <circle r="12" fill="#1f1606" stroke="#fcd34d" strokeWidth="2" />
          <text y="4.5" textAnchor="middle" fontSize="12">
            🕌
          </text>
          <g transform="translate(18 4)">
            <rect width="96" height="24" rx="12" fill="rgba(31,22,6,0.9)" stroke="rgba(251,191,36,0.55)" />
            <text x="48" y="16" textAnchor="middle" fontSize="11" fontWeight="700" fill="#fde68a" fontFamily="Fredoka, sans-serif">
              Asar 16:16
            </text>
          </g>
        </g>
      )}

      {/* checkpoints */}
      {pts.map((p, i) => {
        const c = CHECKPOINTS[i];
        const lx = c.side < 0 ? -150 : 26;
        return (
          <g key={i} transform={`translate(${p.x} ${p.y})`} className="animate-fade-in" style={{ animationDelay: `${0.4 + i * 0.35}s` }}>
            <polygon points="-11,-19 11,-19 22,0 11,19 -11,19 -22,0" fill={`url(#hm-cp${i})`} stroke="rgba(255,255,255,0.85)" strokeWidth="2" filter="url(#hm-glow)" />
            <text y="5" textAnchor="middle" fontSize="15">
              {c.icon}
            </text>
            <g transform={`translate(${lx} -18)`}>
              <rect width="124" height="36" rx="12" fill="rgba(13,20,48,0.92)" stroke="rgba(255,255,255,0.14)" />
              <text x="12" y="15" fontSize="11" fontWeight="700" fill="#fff" fontFamily="Plus Jakarta Sans, sans-serif">
                {c.label}
              </text>
              <text x="12" y="29" fontSize="10.5" fontWeight="700" fill={i === 2 ? "#c4b5fd" : "#6de4c8"} fontFamily="Fredoka, sans-serif" letterSpacing="0.5">
                ⏱ {c.cost}
              </text>
            </g>
          </g>
        );
      })}

      {/* start + finish */}
      <g transform="translate(70 350)">
        <circle r="17" fill="#059669" stroke="#fff" strokeWidth="3" filter="url(#hm-glow)" />
        <text y="5" textAnchor="middle" fontSize="14" fontWeight="800" fill="#fff" fontFamily="Fredoka, sans-serif">
          A
        </text>
      </g>
      <g transform="translate(455 75)">
        <circle r="18" fill="#e11d48" stroke="#fff" strokeWidth="3" filter="url(#hm-glow)" />
        <text y="5.5" textAnchor="middle" fontSize="15">
          🏁
        </text>
        <g transform="translate(-60 26)">
          <text x="0" y="14" fontSize="17" fill="#fbbf24" letterSpacing="2">
            ★★★
          </text>
        </g>
      </g>

      {/* the player */}
      <g>
        <circle r="13" fill="#5eead4" opacity="0.35" filter="url(#hm-glow)" />
        <circle r="7" fill="#fff" stroke="#34cfae" strokeWidth="3" />
        {motion ? (
          <animateMotion dur="7s" repeatCount="indefinite" keyPoints="0;1;1" keyTimes="0;0.85;1" calcMode="linear" path={ROUTE} />
        ) : (
          <animateMotion dur="0.01s" fill="freeze" keyPoints="0.45;0.45" keyTimes="0;1" calcMode="linear" path={ROUTE} />
        )}
      </g>

      <rect x="4" y="4" width="512" height="412" rx="28" fill="url(#hm-vignette)" pointerEvents="none" />
    </svg>
  );
}
