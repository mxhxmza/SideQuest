/** Tiny synthesized sound effects (Web Audio, no files). Off unless the player turns them on. */
let ctx: AudioContext | null = null;
let enabled = false;

export function setSfxEnabled(on: boolean) {
  enabled = on;
}

function tone(freq: number, dur: number, type: OscillatorType = "square", vol = 0.04, delay = 0) {
  if (!enabled) return;
  try {
    ctx ??= new AudioContext();
    if (ctx.state === "suspended") void ctx.resume();
    const t0 = ctx.currentTime + delay;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, t0);
    gain.gain.setValueAtTime(0.0001, t0);
    gain.gain.exponentialRampToValueAtTime(vol, t0 + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    osc.connect(gain).connect(ctx.destination);
    osc.start(t0);
    osc.stop(t0 + dur + 0.02);
  } catch {
    /* audio unavailable: stay silent */
  }
}

export const sfx = {
  click: () => tone(720, 0.05, "square", 0.025),
  start: () => [523, 659, 784].forEach((f, i) => tone(f, 0.12, "square", 0.035, i * 0.08)),
  star: (i: number) => tone(880 + i * 220, 0.16, "triangle", 0.05),
  coin: () => {
    tone(988, 0.08, "square", 0.03);
    tone(1319, 0.22, "square", 0.03, 0.08);
  },
  badge: () => [659, 784, 988, 1319].forEach((f, i) => tone(f, 0.16, "triangle", 0.05, i * 0.09)),
  levelUp: () => [523, 659, 784, 1047, 1319].forEach((f, i) => tone(f, 0.2, "square", 0.035, i * 0.1)),
  fail: () => [392, 330, 262].forEach((f, i) => tone(f, 0.22, "sawtooth", 0.03, i * 0.14)),
};
