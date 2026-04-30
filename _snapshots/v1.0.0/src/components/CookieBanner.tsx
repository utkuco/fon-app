"use client";

import { useState, useEffect } from "react";

const COOKIE_CONSENT_KEY = "fonrapor_cookie_consent";

export default function CookieBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const consent = localStorage.getItem(COOKIE_CONSENT_KEY);
    if (!consent) {
      // Small delay so it doesn't flash on page load
      const timer = setTimeout(() => setVisible(true), 800);
      return () => clearTimeout(timer);
    }
  }, []);

  const accept = () => {
    localStorage.setItem(COOKIE_CONSENT_KEY, "accepted");
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-between gap-4 px-4 py-4 bg-white border-t border-gray-200 shadow-[0_-4px_24px_rgba(0,0,0,0.08)]"
      role="dialog"
      aria-label="Çerez bildirimi"
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-700 leading-relaxed">
          FonRapor, deneyiminizi iyileştirmek için minimal çerezler kullanmaktadır.
          Sitemizi kullanmaya devam ederek{" "}
          <a
            href="/yasal-uyari"
            className="underline underline-offset-2 text-gray-900 hover:text-primary transition-colors"
            target="_blank"
            rel="noopener noreferrer"
          >
            çerez politikamızı
          </a>{" "}
          kabul etmiş olursunuz.
        </p>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <button
          onClick={accept}
          className="px-4 py-2 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-900"
        >
          Kabul Et
        </button>
      </div>
    </div>
  );
}
