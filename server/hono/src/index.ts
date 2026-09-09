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

// Health Check
app.get('/api/health', (c) => {
  return c.json({
    status: 'ok',
    system: 'CPRI PowerNext-AI Test Bench Gateway',
    timestamp: new Date().toISOString()
  });
});

// Automated Summary
app.get('/api/data/summary', (c) => {
  const summaryPath = path.join(rootDir, 'deliverables', 'summary.json');
  if (!fs.existsSync(summaryPath)) {
    return c.json({ error: 'Summary not generated yet. Run ML pipeline.' }, 404);
  }
  const summaryData = JSON.parse(fs.readFileSync(summaryPath, 'utf-8'));
  return c.json(summaryData);
});

// Predictions list
app.get('/api/data/predictions', (c) => {
  const csvPath = path.join(rootDir, 'deliverables', 'PARS.csv');
  if (!fs.existsSync(csvPath)) {
    return c.json({ error: 'PARS.csv not found' }, 404);
  }
  const content = fs.readFileSync(csvPath, 'utf-8');
  const lines = content.trim().split('\n');
  const headers = lines[0].split(',');
  const records = lines.slice(1).map((line) => {
    const parts = line.split(',');
    return {
      Test_ID: parts[0],
      Predicted_Reference_Parameter: parseFloat(parts[1]),
      Validity_Label: parts[2]
    };
  });
  return c.json({ total: records.length, records });
});

// Trigger pipeline
app.post('/api/pipeline/run', async (c) => {
  const result = await new Promise<{ success: boolean; stdout?: string; stderr?: string; code?: number | null }>((resolve) => {
    const isWin = process.platform === 'win32';
    const pyCmd = 'uv';
    const args = ['run', '--python', '3.12', '--with-requirements', 'ml/requirements.txt', 'python', 'ml/run_pipeline.py'];

    const child = spawn(pyCmd, args, { cwd: rootDir, shell: true });
    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (d) => { stdout += d.toString(); });
    child.stderr.on('data', (d) => { stderr += d.toString(); });

    child.on('close', (code) => {
      if (code === 0) {
        resolve({ success: true, stdout });
      } else {
        resolve({ success: false, code, stderr });
      }
    });
  });

  if (result.success) {
    return c.json({ success: true, message: 'Pipeline executed successfully', stdout: result.stdout });
  } else {
    return c.json({ success: false, code: result.code, stderr: result.stderr }, 500);
  }
});

const port = Number(process.env.PORT) || 3001;
console.log('PowerNext Hono API server listening on http://localhost:' + port);
serve({
  fetch: app.fetch,
  port
});
