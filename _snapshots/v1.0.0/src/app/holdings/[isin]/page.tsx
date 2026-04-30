import { Metadata } from "next";
import { notFound } from "next/navigation";
import { fetchHoldingDetail, displayName } from "@/lib/holdings-data";

const BASE_URL = "https://fonrapor.com";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ isin: string }>;
}): Promise<Metadata> {
  const { isin } = await params;
  const decodedIsin = decodeURIComponent(isin);
  const detail = await fetchHoldingDetail(decodedIsin);

  if (!detail) {
    return { title: "Varlık Bulunamadı | FonRapor" };
  }

  const name = displayName(detail.isin, detail.company);

  return {
    title: `${name} — Hangi Fonlarda | FonRapor`,
    description: `${name} (${detail.isin}) varlığını tutan fonlar. Toplam ${detail.funds.length} fon.`,
    openGraph: {
      type: "website",
      locale: "tr_TR",
      url: `${BASE_URL}/holdings/${isin}`,
      siteName: "FonRapor",
      title: `${name} — Hangi Fonlarda | FonRapor`,
      description: `${name} varlığını tutan ${detail.funds.length} fon.`,
    },
    alternates: { canonical: `${BASE_URL}/holdings/${isin}` },
  };
}

export default async function HoldingsDetailPage({
  params,
}: {
  params: Promise<{ isin: string }>;
}) {
  const { isin } = await params;
  const decodedIsin = decodeURIComponent(isin);
  const detail = await fetchHoldingDetail(decodedIsin);

  if (!detail) notFound();

  return <HoldingsDetailClient detail={detail} />;
}

// Client component for interactivity
import HoldingsDetailClient from "./HoldingsDetailClient";
