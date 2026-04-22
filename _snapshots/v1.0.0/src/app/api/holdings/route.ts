import { NextResponse } from "next/server";
import { fetchTopHoldings } from "@/lib/holdings-data";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const holdings = await fetchTopHoldings(200);
    return NextResponse.json({ holdings });
  } catch (err: any) {
    console.error("[/api/holdings]", err);
    return NextResponse.json(
      { error: "Veri yüklenemedi", detail: err.message },
      { status: 500 }
    );
  }
}
