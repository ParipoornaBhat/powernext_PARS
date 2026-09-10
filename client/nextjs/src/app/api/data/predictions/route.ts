import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

export const dynamic = "force-dynamic";

function parseCsvRecords(content: string): Record<string, any>[] {
  const lines = content.trim().split("\n");
  if (lines.length < 2) return [];
  const headers = lines[0].split(",").map((h) => h.trim().replace(/^"|"$/g, ""));
  return lines.slice(1).map((line) => {
    const rawTokens = line.split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/);
    const rec: Record<string, any> = {};
    headers.forEach((h, idx) => {
      const val = rawTokens[idx]?.trim().replace(/^"|"$/g, "");
      if (val === "True") rec[h] = true;
      else if (val === "False") rec[h] = false;
      else if (val !== undefined && val !== "" && !isNaN(Number(val))) rec[h] = Number(val);
      else rec[h] = val ?? null;
    });
    return rec;
  });
}

export async function GET() {
  try {
    const csvPath = path.resolve(process.cwd(), "..", "..", "deliverables", "PARS.csv");
    if (!fs.existsSync(csvPath)) {
      return NextResponse.json({ error: "PARS.csv not found. Run ML pipeline." }, { status: 404 });
    }
    const content = fs.readFileSync(csvPath, "utf-8");
    const records = parseCsvRecords(content);

    // Merge SHAP data if available
    const shapPath = path.resolve(process.cwd(), "..", "..", "deliverables", "shap_explanations.json");
    if (fs.existsSync(shapPath)) {
      const shapData = JSON.parse(fs.readFileSync(shapPath, "utf-8"));
      const byId = new Map<string, any>(
        (shapData.sample_explanations || []).map((s: any) => [s.test_id, s])
      );
      for (const rec of records) {
        const expl = byId.get(rec.Test_ID);
        if (expl) rec.SHAP = expl;
      }
    }

    return NextResponse.json({ total: records.length, records });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
