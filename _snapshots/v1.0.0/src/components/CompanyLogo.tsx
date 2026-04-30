"use client";

import Image from "next/image";
import { useState } from "react";

function getInitials(displayText: string): string {
  if (!displayText || displayText === "??") return "??";
  const clean = displayText.trim();
  // Try to extract meaningful acronym
  const words = clean.split(/\s+/);
  if (words.length === 1) {
    // Single word — take first 2 chars, removing common suffixes
    const stripped = clean.replace(/(AŞ|VE|EĞİTİM|PORTFÖY|EMDK|ARACI|YLIK|YATIRIM)$/i, "");
    return stripped.substring(0, 2).toUpperCase();
  }
  // Multi-word: first letter of first 2 words
  return (words[0][0] + words[1][0]).toUpperCase();
}

function getPlaceholderColor(displayText: string): string {
  const colors = [
    "bg-blue-500",
    "bg-violet-500",
    "bg-emerald-500",
    "bg-amber-500",
    "bg-rose-500",
    "bg-cyan-500",
    "bg-indigo-500",
    "bg-orange-500",
    "bg-teal-500",
    "bg-pink-500",
  ];
  let hash = 0;
  for (let i = 0; i < displayText.length; i++) {
    hash = displayText.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

interface CompanyLogoProps {
  /** Fund name — used for initials when no logo */
  name?: string | null;
  /** Logo filename from data (e.g. "ATA.jpg", "garanti.png") OR full URL */
  logoFile?: string | null;
  /** Company identifier slug (e.g. "garanti", "ata") */
  company?: string | null;
  /** Fund code — used as last-resort initials fallback */
  code?: string;
  size?: number;
  className?: string;
}

export function CompanyLogo({
  name,
  logoFile,
  company,
  code,
  size = 32,
  className = "",
}: CompanyLogoProps) {
  const [imgError, setImgError] = useState(false);

  // If logoFile is a URL, try it; if it's a local filename, try /logos/
  const isUrl = logoFile?.startsWith("http://") || logoFile?.startsWith("https://");
  const logoSrc = isUrl
    ? logoFile
    : logoFile
      ? `/logos/${logoFile}`
      : null;

  // If no logo or image error → show initials
  if (!logoSrc || imgError) {
    // Priority for initials: name > company > code
    const displayText = name || company || code || "??";
    const initials = getInitials(displayText);
    const bgColor = getPlaceholderColor(displayText);

    return (
      <div
        className={`rounded flex items-center justify-center shrink-0 font-bold text-white ${bgColor} ${className}`}
        style={{ width: size, height: size, fontSize: size * 0.35 }}
        title={displayText}
      >
        {initials}
      </div>
    );
  }

  return (
    <Image
      src={logoSrc}
      alt={name || code || "logo"}
      width={size}
      height={size}
      className={`rounded object-contain bg-white border border-neutral-100 ${className}`}
      onError={() => setImgError(true)}
    />
  );
}
