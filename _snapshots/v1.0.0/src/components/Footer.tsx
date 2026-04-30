import { Database } from "lucide-react";
import Link from "next/link";

interface FooterProps {
  lastUpdated: string | null;
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "short", year: "numeric" });
}

export default function Footer({ lastUpdated }: FooterProps) {
  return (
    <footer className="border-t border-neutral-200 bg-white mt-8">
      {/* Top row: data source + legal links */}
      <div className="max-w-7xl mx-auto px-4 py-4 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-1.5 text-xs text-neutral-400">
          <Database className="w-3.5 h-3.5" />
          <span>Veri kaynağı: TEFAS / KAP</span>
          <span className="text-neutral-300 mx-1">·</span>
          <span className={lastUpdated ? "text-emerald-600" : "text-neutral-400"}>
            {lastUpdated ? "●" : "○"}
          </span>
          <span>
            Son veri:{" "}
            <span className="font-medium text-neutral-600">
              {formatDate(lastUpdated || "")}
            </span>
          </span>
        </div>

        <nav className="flex items-center gap-4 text-xs text-neutral-500">
          <Link href="/yasal-uyari" className="hover:text-neutral-800 transition-colors">
            Yasal Uyarı
          </Link>
          <Link href="/cerez-politikasi" className="hover:text-neutral-800 transition-colors">
            Çerez Politikası
          </Link>
          <Link href="/iletisim" className="hover:text-neutral-800 transition-colors">
            İletişim
          </Link>
        </nav>
      </div>

      {/* Bottom row: copyright */}
      <div className="border-t border-neutral-100">
        <div className="max-w-7xl mx-auto px-4 py-3 text-center">
          <p className="text-xs text-neutral-400">
            © {new Date().getFullYear()} fonrapor.com — Bilgi amaçlı içerik. Yatırım tavsiyesi değildir.
          </p>
        </div>
      </div>
    </footer>
  );
}
