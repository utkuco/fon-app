"use client";

interface LogoProps {
  className?: string;
  variant?: "full" | "icon";
  iconSize?: number;
}

export function Logo({ className = "", variant = "full", iconSize = 32 }: LogoProps) {
  if (variant === "icon") {
    return (
      <svg
        width={iconSize}
        height={iconSize}
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className={className}
        aria-label="FonRapor"
      >
        <rect width="32" height="32" rx="8" fill="#2563EB" />
        <path
          d="M6 24 L11 18 L16 21 L21 11 L27 14"
          stroke="white"
          strokeWidth="2.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="6" cy="24" r="2" fill="white" />
        <circle cx="11" cy="18" r="2" fill="white" />
        <circle cx="16" cy="21" r="2" fill="white" />
        <circle cx="21" cy="11" r="2.5" fill="white" />
        <circle cx="27" cy="14" r="2" fill="white" />
      </svg>
    );
  }

  return (
    <svg
      width="auto"
      height="32"
      viewBox="0 0 148 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="FonRapor"
    >
      {/* Icon */}
      <g>
        <rect width="32" height="32" rx="8" fill="#2563EB" />
        {/* Rising chart line */}
        <path
          d="M6 24 L11 18 L16 21 L21 11 L27 14"
          stroke="white"
          strokeWidth="2.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Chart dots */}
        <circle cx="6" cy="24" r="2" fill="white" />
        <circle cx="11" cy="18" r="2" fill="white" />
        <circle cx="16" cy="21" r="2" fill="white" />
        <circle cx="21" cy="11" r="2.5" fill="white" />
        <circle cx="27" cy="14" r="2" fill="white" />
      </g>

      {/* Wordmark */}
      <text
        x="40"
        y="22"
        fontFamily="'Inter', system-ui, -apple-system, sans-serif"
        fontSize="16"
        fontWeight="800"
        letterSpacing="-0.4"
        fill="#0F172A"
      >
        Fon
      </text>
      <text
        x="74"
        y="22"
        fontFamily="'Inter', system-ui, -apple-system, sans-serif"
        fontSize="16"
        fontWeight="800"
        letterSpacing="-0.4"
        fill="#2563EB"
      >
        Rapor
      </text>
    </svg>
  );
}
