import { revalidatePath } from "next/cache";
import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const path = searchParams.get("path") || "/";
  const secret = searchParams.get("secret");

  // Simple secret check (optional)
  if (secret !== process.env.REVALIDATE_SECRET && process.env.REVALIDATE_SECRET) {
    return NextResponse.json({ error: "Invalid secret" }, { status: 401 });
  }

  revalidatePath(path);
  return NextResponse.json({ revalidated: true, path, timestamp: Date.now() });
}
