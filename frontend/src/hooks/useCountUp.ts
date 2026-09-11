import { useEffect, useRef, useState } from "react";

/**
 * Animate a number from its previous value to a new one.
 *
 * Used for the KPI tiles so a figure arriving from the API counts up rather than
 * snapping into place. On a monitoring console the movement also carries meaning:
 * a value that visibly climbs reads as live telemetry, where a static number reads
 * as a screenshot.
 *
 * Honours prefers-reduced-motion by jumping straight to the target.
 */
export function useCountUp(target: number | null | undefined, durationMs = 900): number {
  const safeTarget = Number.isFinite(Number(target)) ? Number(target) : 0;
  const [display, setDisplay] = useState(safeTarget);
  const fromRef = useRef(safeTarget);
  const frameRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    if (reduced || durationMs <= 0) {
      fromRef.current = safeTarget;
      setDisplay(safeTarget);
      return;
    }

    const from = fromRef.current;
    const delta = safeTarget - from;
    if (delta === 0) return;

    const start = performance.now();

    // easeOutExpo: fast départ, long settle. Reads as a value "arriving" and
    // locking on, which suits telemetry better than a linear ramp.
    const ease = (t: number) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));

    const tick = (now: number) => {
      const t = Math.min((now - start) / durationMs, 1);
      setDisplay(from + delta * ease(t));
      if (t < 1) {
        frameRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = safeTarget;
        setDisplay(safeTarget);
      }
    };

    frameRef.current = requestAnimationFrame(tick);

    return () => {
      if (frameRef.current !== undefined) cancelAnimationFrame(frameRef.current);
      // Keep the last rendered value as the next animation's origin so a re-render
      // mid-flight does not restart from the old number.
      fromRef.current = display;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [safeTarget, durationMs]);

  return display;
}

/**
 * Format a counted value for display. Integers stay integers while animating -
 * a KPI flickering through 17 decimal places looks broken, not lively.
 */
export function formatCounted(value: number, decimals = 0): string {
  if (!Number.isFinite(value)) return "—";
  return value.toLocaleString("en-IN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}
