import { NextRequest } from "next/server";

const FUND_TYPES = ["SRF", "VFF", "BYF", "DÖVİZ", "ALTIN", "KFF", "OKS"] as const;

export async function GET(req: NextRequest) {
  const type = req.nextUrl.searchParams.get("type") || "";
  const upperType = type.toUpperCase();
  const includes = FUND_TYPES.includes(upperType as typeof FUND_TYPES[number]);

  // Check character codes
  const codes: Record<string, number> = {};
  for (const c of type) codes[c] = c.charCodeAt(0);
  const fundCodes: Record<string, number> = {};
  for (const c of "DÖVİZ") fundCodes[c] = c.charCodeAt(0);

  return Response.json({
    type,
    upperType,
    includes,
    typeChars: codes,
    fundTypeChars: fundCodes,
    typeBytes: Buffer.from(type).toString("hex"),
    fundTypeBytes: Buffer.from("DÖVİZ").toString("hex"),
  });
}
