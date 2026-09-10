import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const filePath = path.resolve(process.cwd(), "..", "..", "deliverables", "benchmark_results.json");
    if (!fs.existsSync(filePath)) {
      return NextResponse.json({ error: "Benchmark not generated yet. Run ML pipeline." }, { status: 404 });
    }
    const data = JSON.parse(fs.readFileSync(filePath, "utf-8"));
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
