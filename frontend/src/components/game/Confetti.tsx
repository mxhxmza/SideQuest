import { useEffect, useRef } from "react";

const COLORS = ["#34cfae", "#22d3ee", "#a78bfa", "#f472b6", "#fbbf24", "#ffffff"];
const LIFE_MS = 2800;

/** Canvas confetti. Fires whenever `burst` changes to a new non-zero value. */
export default function Confetti({ burst, power = 140 }: { burst: number; power?: number }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const c = ref.current;
    if (!burst || !c) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const W = window.innerWidth;
    const H = window.innerHeight;
    const dpr = window.devicePixelRatio || 1;
    c.width = W * dpr;
    c.height = H * dpr;
    ctx.scale(dpr, dpr);
    // two cannons in the bottom corners, aimed up and inwards
    const ps = Array.from({ length: power }, (_, i) => {
      const left = i % 2 === 0;
      return {
        x: left ? W * 0.05 : W * 0.95,
        y: H * 0.95,
        vx: (left ? 1 : -1) * (4 + Math.random() * 9),
        vy: -(12 + Math.random() * 12),
        w: 6 + Math.random() * 6,
        h: 8 + Math.random() * 8,
        r: Math.random() * Math.PI,
        vr: (Math.random() - 0.5) * 0.35,
        color: COLORS[i % COLORS.length],
        round: Math.random() < 0.3,
      };
    });
    let raf = 0;
    const start = performance.now();
    const step = (now: number) => {
      const t = now - start;
      ctx.clearRect(0, 0, W, H);
      ctx.globalAlpha = Math.max(0, 1 - Math.max(0, t - LIFE_MS * 0.6) / (LIFE_MS * 0.4));
      for (const p of ps) {
        p.vy += 0.32;
        p.vx *= 0.985;
        p.x += p.vx;
        p.y += p.vy;
        p.r += p.vr;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.r);
        ctx.fillStyle = p.color;
        if (p.round) {
          ctx.beginPath();
          ctx.arc(0, 0, p.w / 2, 0, Math.PI * 2);
          ctx.fill();
        } else {
          ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h * Math.abs(Math.cos(p.r * 2)) + 1);
        }
        ctx.restore();
      }
      if (t < LIFE_MS) raf = requestAnimationFrame(step);
      else ctx.clearRect(0, 0, W, H);
    };
    raf = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(raf);
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, c.width, c.height);
    };
  }, [burst, power]);

  return <canvas ref={ref} className="pointer-events-none fixed inset-0 z-[60] h-full w-full" aria-hidden />;
}
