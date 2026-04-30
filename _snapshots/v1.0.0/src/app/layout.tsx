import "./globals.css";
import type { Metadata } from "next";
import { supabaseAdmin } from "@/lib/supabase-admin";
import Footer from "@/components/Footer";
import CookieBanner from "@/components/CookieBanner";

const BASE_URL = "https://fonrapor.com";

const WEBSITE_SCHEMA = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "FonRapor",
  url: BASE_URL,
  description: "Türkiye'nin kapsamlı yatırım fonu analiz platformu. Tefas ve KAP verileriyle fon performansı, portföy dağılımı, günlük değişimler ve karşılaştırma.",
  inLanguage: "tr-TR",
  isAccessibleForFree: "True",
  about: {
    "@type": "Thing",
    name: "Yatırım Fonları",
    description: "Türkiye yatırım fonları analiz ve karşılaştırma",
  },
  audience: {
    "@type": "Audience",
    name: "Yatırımcılar",
  },
  potentialAction: {
    "@type": "SearchAction",
    target: {
      "@type": "EntryPoint",
      urlTemplate: `${BASE_URL}/?q={search_term_string}`,
    },
    "query-input": "required name=search_term_string",
  },
};

const ORGANIZATION_SCHEMA = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "FonRapor",
  url: BASE_URL,
  logo: {
    "@type": "ImageObject",
    url: `${BASE_URL}/favicon.svg`,
  },
  sameAs: [],
  contactPoint: {
    "@type": "ContactPoint",
    contactType: "customer service",
    availableLanguage: "Turkish",
  },
};

const FAQ_SCHEMA = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: [
    {
      "@type": "Question",
      name: "FonRapor'da hangi yatırım fonları var?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "FonRapor'da Türkiye'deki 2.400'den fazla yatırım fonu bulunmaktadır. Bu fonlar fon türüne göre (hisse, tahvil, altın, döviz, karma, değişken) ve yönetim şirketine göre filtrelenebilir.",
      },
    },
    {
      "@type": "Question",
      name: "Fon performans verileri ne kadar sürede güncellenir?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "Fon verileri TEFAS ve KAP'tan günlük olarak güncellenmektedir. Fiyatlar, günlük değişimler ve dönemsel getiriler her işlem günü sonrası yansımaktadır.",
      },
    },
    {
      "@type": "Question",
      name: "Fon karşılaştırması nasıl yapılır?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "Karşılaştırmak istediğiniz fonları seçerek fiyat performansı grafiği üzerinden dönemsel getiri karşılaştırması yapabilirsiniz. Maksimum 3 fon karşılaştırılabilir.",
      },
    },
    {
      "@type": "Question",
      name: "Fonların portföy dağılımı nerden alınıyor?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "Fon portföy dağılımları KAP (Kamuyu Aydınlatma Platformu) verilerinden alınmaktadır. Hisse senedi, tahvil ve diğer varlık türleri sektör bazında gösterilmektedir.",
      },
    },
    {
      "@type": "Question",
      name: "FonRapor ücretsiz mi?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "Evet, FonRapor tamamen ücretsiz bir platformdur. Tüm fon verileri, performans karşılaştırmaları ve portföy analizleri ücretsiz olarak kullanılabilir.",
      },
    },
  ],
};

const WEB_APPLICATION_SCHEMA = {
  "@context": "https://schema.org",
  "@type": "WebApplication",
  name: "FonRapor",
  description: "Türkiye'nin kapsamlı yatırım fonu analiz platformu. 2.400+ fon, 70 şirket, anlık performans takibi.",
  url: BASE_URL,
  applicationCategory: "FinanceApplication",
  operatingSystem: "Web Browser",
  offers: {
    "@type": "Offer",
    price: "0",
    priceCurrency: "TRY",
    availability: "https://schema.org/InStock",
  },
  featureList: [
    "Yatırım fonu filtreleme ve sıralama",
    "Fon performans karşılaştırması",
    "Portföy dağılımı analizi",
    "Günlük ve dönemsel getiri takibi",
    "Fon türü bazlı analiz",
    "Yönetim şirketi bazlı analiz",
  ],
  browserRequirements: "Requires modern web browser with JavaScript enabled.",
  softwareVersion: "1.0",
};

export const metadata: Metadata = {
  metadataBase: new URL(BASE_URL),
  title: {
    default: "FonRapor — Türk Yatırım Fonları Portföy Analizi",
    template: "%s | FonRapor",
  },
  description:
    "Türkiye'nin kapsamlı yatırım fonu analiz platformu. Tefas ve KAP verileriyle fon performansı, portföy dağılımı, günlük değişimler ve karşılaştırma.",
  keywords: [
    "yatırım fonu",
    "tefas",
    "KAP",
    "fon analizi",
    "portföy",
    "borsa",
    "TL fon",
    "döviz fon",
    "altın fon",
    "hisse fon",
  ],
  authors: [{ name: "FonRapor" }],
  creator: "FonRapor",
  openGraph: {
    type: "website",
    locale: "tr_TR",
    url: BASE_URL,
    siteName: "FonRapor",
    title: "FonRapor — Türk Yatırım Fonları Portföy Analizi",
    description:
      "Türkiye'nin kapsamlı yatırım fonu analiz platformu. Tefas ve KAP verileriyle fon performansı ve portföy dağılımı.",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "FonRapor — Türk Yatırım Fonları",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "FonRapor — Türk Yatırım Fonları Portföy Analizi",
    description:
      "Türkiye'nin kapsamlı yatırım fonu analiz platformu.",
    images: ["/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Note: lastUpdated date is now fetched client-side in Footer
  // to avoid Vercel->Supabase timeouts blocking the entire page render.
  const lastUpdated = null;

  const schemas = [WEBSITE_SCHEMA, ORGANIZATION_SCHEMA, FAQ_SCHEMA, WEB_APPLICATION_SCHEMA];
  const schemaJson = JSON.stringify(schemas);

  return (
    <html lang="tr">
      <head>
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: schemaJson }}
        />
      </head>
      <body>
        {children}
        <Footer lastUpdated={lastUpdated} />
        <CookieBanner />
      </body>
    </html>
  );
}
