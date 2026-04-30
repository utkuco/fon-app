"use client";

interface ChangeBadgeProps {
  value: number | null;
  size?: "sm" | "md";
}

export function ChangeBadge({ value, size = "md" }: ChangeBadgeProps) {
  if (value == null) return null;

  const isPositive = value >= 0;
  const cls = size === "sm"
    ? `text-xs px-1 py-0.5 rounded font-semibold ${isPositive ? "text-green-600 bg-green-50" : "text-red-600 bg-red-50"}`
    : `text-xs px-1.5 py-0.5 rounded-md font-semibold ${isPositive ? "text-green-600 bg-green-100" : "text-red-600 bg-red-100"}`;

  return (
    <span className={cls}>
      {isPositive ? "+" : ""}{value.toFixed(2)}%
    </span>
  );
}
