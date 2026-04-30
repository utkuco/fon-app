"use client";

import { useState } from "react";

// Wikimedia Commons logo URLs for known BIST stocks
// Format: ticker (without .E) -> Wikimedia Commons filename
const LOGO_MAP: Record<string, string> = {
  // Banks
  AKBNK: "Akbank%20logo.svg",
  GARAN: "Logo%20garanti%20bbva.jpg",
  ISCTR: "Isbank_logo.svg",
  YKBNK: "Yap%C4%B1%20kredi%20logo.png",
  HALKB: "Halkbank_logo.svg",
  QNBFL: "QNB%20Finansbank%20logo.svg",

  // Holdings & Finance
  KCHOL: "Ko%C3%A7%20Holding%20-%20logo%20(Turkey%2C%201984).svg",
  SAHOL: "Sabanc%C4%B1%20Holding%20logo.svg",

  // Industrials & Manufacturing
  ASELS: "ASELSAN%20logo.svg",
  FROTO: "Ford%20Otosan%20logo.svg",
  TOASO: "TOFA%C5%9E%20logo%20(2019-).svg",
  ARCLK: "Arcelik%20Logo.svg",
  VESTL: "Vestel_logo.svg",
  KARSN: "Karsan_logo.svg",
  BRSAN: "Borusan%20logo.svg",
  DSTKF: "DESTEK%20logo.svg",

  // Airlines
  THYAO: "Turkish_Airlines_logo_2012.svg",
  PGSUS: "Pegasus%20Airlines%20logo.svg",
  TAVHL: "TAV%20Havalimanlar%C4%B1%20logo.svg",

  // Energy & Petkim
  TUPRS: "T%C3%BCpra%C5%9F%20logo.svg",
  AKFGY: "Akfen%20logo.svg",
  ODAS: "Oda%C5%9F%20logo.svg",
  ZOREN: "Zoren%20logo.svg",

  // Telecom
  TCELL: "Turkcell%20yeni%204f007f5f.gif",

  // Consumer & Retail
  BIMAS: "Logo%20of%20B%C4%B0M.PNG",
  MAVI: "Mavi_logo.svg",
  CCOLA: "Coca-Cola_logo.svg",
  AEFES: "Anadolu%20Efes%20logo.svg",
  ULTXY: "%C3%9Clker%20logo.svg",
  SKBNK: "%C5%9Eekerbank%20logo.svg",

  // Cement & Construction
  SISE: "Logo%20de%20Sise.svg",
  CIMSA: "%C3%87imsa%20logo.svg",
  ENKAI: "Enka%20logo.svg",
  EKGYO: "Emlak%20Konut%20logo.svg",

  // Automotive & Parts
  EREGL: "Ere%C4%9Fli%20logo.svg",
  KRDMD: "Kardemir%20logo.svg",
  BYDCO: "BYD%20logo.svg",
  AVPGY: "Aksa%20Power%20logo.svg",

  // Mining & Steel
  ASTOR: "Astorlogo.png",
};

interface StockLogoProps {
  ticker: string;
  company?: string;
  size?: number;
  className?: string;
}

function getInitials(company: string): string {
  if (!company) return "??";
  // Clean company name - remove common suffixes
  const clean = company
    .replace(/\s+(A\.Ş\.|A.S\.|T.A.Ş\.|T.A.S\.|Inc\.|Corp\.|Ltd\.|SAN\.|S.A\.)$/gi, "")
    .replace(/[,.\-]/g, " ")
    .trim();

  const words = clean.split(/\s+/);
  if (words.length === 1) {
    return words[0].substring(0, 2).toUpperCase();
  }
  return (words[0][0] + words[1][0]).toUpperCase();
}

function getPlaceholderColor(ticker: string): string {
  // Generate a consistent color based on ticker
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
  for (let i = 0; i < ticker.length; i++) {
    hash = ticker.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

export function StockLogo({ ticker, company, size = 32, className = "" }: StockLogoProps) {
  const [imgError, setImgError] = useState(false);

  // Remove .E suffix for lookup
  const tickerKey = ticker.replace(/\.E$/, "");
  const logoFile = LOGO_MAP[tickerKey];

  if (!logoFile || imgError) {
    // Show initials placeholder
    const initials = getInitials(company || tickerKey);
    const bgColor = getPlaceholderColor(tickerKey);

    return (
      <div
        className={`rounded flex items-center justify-center shrink-0 font-bold text-white ${bgColor} ${className}`}
        style={{ width: size, height: size, fontSize: size * 0.35 }}
        title={company || ticker}
      >
        {initials}
      </div>
    );
  }

  const logoUrl = `https://commons.wikimedia.org/wiki/Special:FilePath/${logoFile}?width=${size * 2}`;

  return (
    <img
      src={logoUrl}
      alt={company || ticker}
      width={size}
      height={size}
      className={`rounded object-contain bg-white border border-neutral-100 ${className}`}
      onError={() => setImgError(true)}
      loading="lazy"
    />
  );
}
