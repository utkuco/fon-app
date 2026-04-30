import { Metadata } from "next";
import ComparePageClient from "./ComparePageClient";

const BASE_URL = "https://fonrapor.com";

export const metadata: Metadata = {
  title: "Karşılaştır | FonRapor",
  description:
    "En fazla 3 yatırım fonunu karşılaştır. Fiyat performansı grafiği ve dönemsel getiri karşılaştırması.",
  openGraph: {
    type: "website",
    locale: "tr_TR",
    url: `${BASE_URL}/compare`,
    siteName: "FonRapor",
    title: "Karşılaştır | FonRapor",
    description: "En fazla 3 yatırım fonunu karşılaştır.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Karşılaştır | FonRapor",
    description: "En fazla 3 yatırım fonunu karşılaştır.",
  },
  alternates: { canonical: `${BASE_URL}/compare` },
  robots: {
    index: true,
    follow: true,
  },
};

export default function ComparePage() {
  return <ComparePageClient />;
}
