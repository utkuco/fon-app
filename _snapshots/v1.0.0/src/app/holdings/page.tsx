import { Metadata } from "next";
import { fetchTopHoldings, type AggregatedHolding } from "@/lib/holdings-data";
import HoldingsClient from "./HoldingsClient";

const BASE_URL = "https://fonrapor.com";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: "Hisse Tercihleri | FonRapor",
    description:
      "Fonların en çok tercih ettiği hisse senetleri ve varlıklar. Her varlığın kaç fon tarafından tutulduğunu keşfedin.",
    openGraph: {
      type: "website",
      locale: "tr_TR",
      url: `${BASE_URL}/holdings`,
      siteName: "FonRapor",
      title: "Hisse Tercihleri | FonRapor",
      description:
        "Fonların en çok tercih ettiği hisse senetleri ve varlıklar.",
    },
    alternates: { canonical: `${BASE_URL}/holdings` },
  };
}

export default async function HoldingsPage() {
  // Fetch on the server, pass to client for interactivity
  let initialHoldings: AggregatedHolding[] = [];
  try {
    initialHoldings = await fetchTopHoldings(200);
  } catch (e) {
    console.error("[/holdings] Failed to fetch holdings:", e);
  }

  return <HoldingsClient initialHoldings={initialHoldings} />;
}
