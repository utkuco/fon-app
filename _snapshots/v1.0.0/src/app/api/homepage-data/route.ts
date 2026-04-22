import { NextResponse } from "next/server";
import { fetchHomePageData } from "@/lib/homepage-data";

// Simple, robust endpoint — no caching layer to avoid stale empty results
export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const data = await fetchHomePageData();
    return NextResponse.json(data, {
      headers: { "cache-control": "public, s-maxage=300, stale-while-revalidate=60" }
    });
  } catch (err) {
    console.error("[homepage] unexpected error:", err);
    return NextResponse.json({ error: "Data fetch failed", details: String(err) }, { status: 500 });
  }
}
