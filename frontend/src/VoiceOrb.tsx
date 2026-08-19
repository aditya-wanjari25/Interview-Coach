import { useEffect, useRef } from "react";
import "./VoiceOrb.css";

interface VoiceOrbProps {
  speaking: boolean;
}

const SIZE = 240;
const CENTER = SIZE / 2;
const BASE_RADIUS = 78;
const POINTS = 10;

// deterministic pseudo-random per-point phase offset, so each bump on the blob
// moves independently instead of the whole shape pulsing in lockstep
const PHASES = Array.from({ length: POINTS }, (_, i) => i * 1.37);

export default function VoiceOrb({ speaking }: VoiceOrbProps) {
  const pathRef = useRef<SVGPathElement>(null);

  useEffect(() => {
    let t = 0;
    let frameId: number;

    function draw() {
      const amplitude = speaking ? 7 : 2;
      const speed = speaking ? 0.025 : 0.01;
      t += speed;

      const points: [number, number][] = [];
      for (let i = 0; i < POINTS; i++) {
        const angle = (i / POINTS) * Math.PI * 2;
        const wobble =
          Math.sin(t * 1.1 + PHASES[i]) * 0.6 + Math.sin(t * 1.7 + PHASES[i] * 1.9) * 0.4;
        const radius = BASE_RADIUS + wobble * amplitude;
        points.push([CENTER + Math.cos(angle) * radius, CENTER + Math.sin(angle) * radius]);
      }

      pathRef.current?.setAttribute("d", smoothPath(points));
      frameId = requestAnimationFrame(draw);
    }

    draw();
    return () => cancelAnimationFrame(frameId);
  }, [speaking]);

  return (
    <svg
      className={`voice-orb ${speaking ? "voice-orb--speaking" : ""}`}
      width={SIZE}
      height={SIZE}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
    >
      <defs>
        <radialGradient id="orb-gradient" cx="35%" cy="30%" r="75%">
          <stop offset="0%" stopColor="#99f6e4" />
          <stop offset="55%" stopColor="#2dd4bf" />
          <stop offset="100%" stopColor="#0f766e" />
        </radialGradient>
      </defs>
      <path ref={pathRef} fill="url(#orb-gradient)" />
    </svg>
  );
}

// Catmull-Rom-ish smoothing through a closed loop of points, rendered as a cubic bezier path
function smoothPath(points: [number, number][]): string {
  const n = points.length;
  const get = (i: number) => points[(i + n) % n];

  let d = `M ${points[0][0]} ${points[0][1]} `;
  for (let i = 0; i < n; i++) {
    const [x0, y0] = get(i - 1);
    const [x1, y1] = get(i);
    const [x2, y2] = get(i + 1);
    const [x3, y3] = get(i + 2);

    const cp1x = x1 + (x2 - x0) / 6;
    const cp1y = y1 + (y2 - y0) / 6;
    const cp2x = x2 - (x3 - x1) / 6;
    const cp2y = y2 - (y3 - y1) / 6;

    d += `C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${x2} ${y2} `;
  }
  return d + "Z";
}
