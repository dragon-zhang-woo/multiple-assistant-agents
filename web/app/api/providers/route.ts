import { NextResponse } from "next/server";
import { getProviderInfo } from "@/lib/server/providers";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export function GET() {
  return NextResponse.json(getProviderInfo(), {
    headers: {
      "Cache-Control": "no-store"
    }
  });
}
