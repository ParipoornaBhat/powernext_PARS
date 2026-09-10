import { serve } from '@hono/node-server';
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '../../..');

const app = new Hono();

app.use('*', cors());

function spawnUvPython(scriptAndArgs: string[], stdinPayload?: string): Promise<{ code: number | null; stdout: string; stderr: string }> {
  return new Promise((resolve) => {
    const args = ['--system-certs', 'run', '--python', '3.12', '--with-requirements', 'ml/requirements.txt', 'python', ...scriptAndArgs];
    const child = spawn('uv', args, { cwd: rootDir, shell: true });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (d) => { stdout += d.toString(); });
    child.stderr.on('data', (d) => { stderr += d.toString(); });
    if (stdinPayload !== undefined) {
      child.stdin.write(stdinPayload);
      child.stdin.end();
    }
    child.on('close', (code) => resolve({ code, stdout, stderr }));
  });
}

function parseCsvRecords(content: string): Record<string, any>[] {
  const lines = content.trim().split('\n');
  if (lines.length < 2) return [];
  const headers = lines[0].split(',').map((h) => h.trim());
  return lines.slice(1).map((line) => {
    const rawTokens = line.split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/);
    const rec: Record<string, any> = {};
    headers.forEach((h, idx) => {
      const val = rawTokens[idx]?.trim().replace(/^"|"$/g, '');
      if (val === 'True') rec[h] = true;
      else if (val === 'False') rec[h] = false;
      else if (val !== undefined && val !== '' && !isNaN(Number(val))) rec[h] = Number(val);
      else rec[h] = val ?? null;
    });
    return rec;
  });
}

app.get('/api/health', (c) => {
  return c.json({
    status: 'ok',
    system: 'CPRI PowerNext-AI Test Bench Gateway',
    timestamp: new Date().toISOString()
  });
});

app.get('/api/data/summary', (c) => {
  const summaryPath = path.join(rootDir, 'deliverables', 'summary.json');
  if (!fs.existsSync(summaryPath)) {
    return c.json({ error: 'Summary not generated yet. Run ML pipeline.' }, 404);
  }
  const summaryData = JSON.parse(fs.readFileSync(summaryPath, 'utf-8'));
  return c.json(summaryData);
});

app.get('/api/data/predictions', (c) => {
  const csvPath = path.join(rootDir, 'deliverables', 'PARS.csv');
  if (!fs.existsSync(csvPath)) {
    return c.json({ error: 'PARS.csv not found' }, 404);
  }
  const content = fs.readFileSync(csvPath, 'utf-8');
  const records = parseCsvRecords(content);
  const shapPath = path.join(rootDir, 'deliverables', 'shap_explanations.json');
  if (fs.existsSync(shapPath)) {
    const shapData = JSON.parse(fs.readFileSync(shapPath, 'utf-8'));
    const byId = new Map((shapData.sample_explanations || []).map((s: any) => [s.test_id, s]));
    for (const rec of records) {
      const expl = byId.get(rec.Test_ID);
      if (expl) rec.SHAP = expl;
    }
  }
  return c.json({ total: records.length, records });
});

app.get('/api/data/benchmark', (c) => {
  const benchPath = path.join(rootDir, 'deliverables', 'benchmark_results.json');
  if (!fs.existsSync(benchPath)) {
    return c.json({ error: 'Benchmark results not generated yet. Run ML pipeline.' }, 404);
  }
  const benchData = JSON.parse(fs.readFileSync(benchPath, 'utf-8'));
  return c.json(benchData);
});

app.get('/api/data/shap', (c) => {
  const shapPath = path.join(rootDir, 'deliverables', 'shap_explanations.json');
  if (!fs.existsSync(shapPath)) {
    return c.json({ error: 'SHAP explanations not generated yet. Run ML pipeline.' }, 404);
  }
  const shapData = JSON.parse(fs.readFileSync(shapPath, 'utf-8'));
  return c.json(shapData);
});

app.post('/api/evaluate/csv', async (c) => {
  try {
    const body = await c.req.json();
    const csvContent = body.csvContent;
    if (!csvContent || typeof csvContent !== 'string' || csvContent.trim().length === 0) {
      return c.json({ success: false, error: 'Empty file: invalid or empty CSV content provided.' }, 400);
    }

    const tempDir = path.join(rootDir, 'ml', 'temp');
    fs.mkdirSync(tempDir, { recursive: true });
    const tempFile = path.join(tempDir, `upload_${Date.now()}.csv`);
    fs.writeFileSync(tempFile, csvContent, 'utf-8');

    const py = await spawnUvPython(['ml/src/evaluate_csv.py', tempFile]);
    try {
      if (fs.existsSync(tempFile)) fs.unlinkSync(tempFile);
    } catch (_) {}

    if (py.code === 0) {
      const jsonStart = py.stdout.indexOf('{');
      const jsonEnd = py.stdout.lastIndexOf('}');
      if (jsonStart !== -1 && jsonEnd !== -1) {
        const parsed = JSON.parse(py.stdout.slice(jsonStart, jsonEnd + 1));
        if (parsed.success) return c.json(parsed);
        return c.json({ success: false, error: parsed.error || 'Evaluation failed' }, 400);
      }
      return c.json({ success: false, error: 'Failed to parse evaluator output' }, 500);
    }
    return c.json({ success: false, error: py.stderr || py.stdout || 'Evaluation failed' }, 400);
  } catch (err: any) {
    return c.json({ success: false, error: err.message }, 500);
  }
});

app.post('/api/certificate/pdf', async (c) => {
  try {
    const body = await c.req.json();
    const record = body.record;
    if (!record || !record.Test_ID) {
      return c.json({ success: false, error: 'record.Test_ID is required' }, 400);
    }

    const shapPath = path.join(rootDir, 'deliverables', 'shap_explanations.json');
    if (!record.SHAP && fs.existsSync(shapPath)) {
      const shapData = JSON.parse(fs.readFileSync(shapPath, 'utf-8'));
      const match = (shapData.sample_explanations || []).find((s: any) => s.test_id === record.Test_ID);
      if (match) record.SHAP = match;
    }

    const outDir = path.join(rootDir, 'ml', 'temp');
    fs.mkdirSync(outDir, { recursive: true });
    const outFile = path.join(outDir, `PARS_report_${String(record.Test_ID)}.pdf`);
    const payload = JSON.stringify({ record, output_path: outFile });
    const py = await spawnUvPython(['ml/src/certificate.py'], payload);
    if (py.code !== 0 || !fs.existsSync(outFile)) {
      return c.json({ success: false, error: py.stderr || py.stdout || 'PDF generation failed' }, 500);
    }
    const pdf = fs.readFileSync(outFile);
    try { fs.unlinkSync(outFile); } catch (_) {}
    return new Response(pdf, {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': `attachment; filename="PARS_analytical_report_${record.Test_ID}.pdf"`
      }
    });
  } catch (err: any) {
    return c.json({ success: false, error: err.message }, 500);
  }
});

app.post('/api/pipeline/run', async (c) => {
  const py = await spawnUvPython(['ml/run_pipeline.py']);
  if (py.code === 0) {
    return c.json({ success: true, message: 'Pipeline executed successfully', stdout: py.stdout });
  }
  return c.json({ success: false, code: py.code, stderr: py.stderr }, 500);
});

const port = Number(process.env.PORT) || 3001;
console.log('PowerNext Hono API server listening on http://localhost:' + port);
serve({
  fetch: app.fetch,
  port
});
