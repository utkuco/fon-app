import { NextResponse } from "next/server";
import { fetchHoldingDetail } from "@/lib/holdings-data";

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ isin: string }> }
) {
  const { isin } = await params;

  if (!isin) {
    return NextResponse.json({ error: "ISIN gerekli" }, { status: 400 });
  }

  try {
    const detail = await fetchHoldingDetail(isin);
    if (!detail) {
      return NextResponse.json({ error: "Varlık bulunamadı" }, { status: 404 });
    }
    return NextResponse.json(detail);
  } catch (err: any) {
    console.error("[/api/holdings/:isin]", err);
    return NextResponse.json(
      { error: "Veri yüklenemedi", detail: err.message },
      { status: 500 }
    );
  }
}
