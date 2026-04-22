"use client";

import { useEffect, useRef, useState } from "react";

export function useCounter(
  end: number,
  duration: number = 1200,
  decimals: number = 0,
  prefix: string = "",
  suffix: string = "",
  active: boolean = true
) {
  const [value, setValue] = useState(0);
  const startTime = useRef<number | null>(null);
  const rafId = useRef<number | null>(null);

  useEffect(() => {
    if (!active || end === 0) {
      setValue(end);
      return;
    }

    startTime.current = null;

    const animate = (timestamp: number) => {
      if (!startTime.current) startTime.current = timestamp;
      const elapsed = timestamp - startTime.current;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(parseFloat((end * eased).toFixed(decimals)));

      if (progress < 1) {
        rafId.current = requestAnimationFrame(animate);
      }
    };

    rafId.current = requestAnimationFrame(animate);
    return () => {
      if (rafId.current) cancelAnimationFrame(rafId.current);
    };
  }, [end, duration, decimals, active]);

  return `${prefix}${decimals > 0 ? value.toFixed(decimals) : Math.round(value).toLocaleString("tr-TR")}${suffix}`;
}
