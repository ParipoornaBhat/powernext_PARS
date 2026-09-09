# PowerNext-AI | CPRI Black-Box Test Bench Challenge

**Screening Round Challenge Solution by Team PARS**  
*Organized by Central Power Research Institute (CPRI) with institutional partner MIT Bengaluru*

---

## 👥 Team Details (Team PARS)
- **Paripoorna**
- **Anusha**
- **Reegan**
- **Shravya**

---

## ⚡ Project Overview & Architecture
This repository implements an end-to-end reproducible solution for analyzing laboratory electrical test-bench data, identifying measurement anomalies and sensor faults, predicting ground-truth critical hot-spot temperature rises (Reference_Parameter), and serving interactive test bench simulations.

### Project Structure:
- **client/nextjs**: Next.js 15+ App Router, React 19, Tailwind CSS, Lucide icons, interactive test bench metrics, and live streaming simulator.
- **server/hono**: High-performance Hono API server exposing telemetry analysis, summary reports, and pipeline automation.
- **packages/shared**: Shared TypeScript types and Zod schemas for test records and statistical summaries.
- **ml/**: Python ML workspace with physics-residual anomaly filters, LightGBM/GBR regression ensemble, and reproducible pipelines.
- **deliverables/**: Competition deliverables (PARS.csv, summary.json, summary.csv, METHODOLOGY.md).

---

## 📊 Key Results
1. **Task 01: Anomaly Detection**
   - 100% anomaly detection on historical records via coupled electro-thermal residual analysis ($|S_i - \hat{S}_i| > 1.25^\circ	ext{C}$) and duplicate collision auditing.
   - Auxiliary sensor $ verified as uncorrelated noise.

2. **Task 02: Reference Parameter Prediction (^2 = 0.9884$)**
   - Ensemble of LightGBM (50%) + Gradient Boosting (30%) + ExtraTrees (20%) using power proxy ( \cdot I$), terminal mean, and inter-sensor temperature gradients.

3. **Task 03: Automated Summary**
   - 350 test records analyzed; 46 invalid records identified.
   - Priority attention test benches: TST-0258, TST-0142, TST-0178.

---

## 🚀 Getting Started

### 1. Run Machine Learning Pipeline
`powershell
pnpm ml:pipeline
`

### 2. Run Full-Stack Web Application & API
`powershell
# Terminal 1 (Hono API):
pnpm --filter @powernext/hono-server dev

# Terminal 2 (Next.js UI):
pnpm --filter @powernext/web dev
`
Open [http://localhost:3000](http://localhost:3000) to view the dashboard.

### 3. Create Submission ZIP Archive
`powershell
Compress-Archive -Path 
  "deliverables/PARS.csv", 
  "deliverables/summary.json", 
  "deliverables/summary.csv", 
  "deliverables/METHODOLOGY.md", 
  "ml/run_pipeline.py", 
  "ml/src", 
  "ml/requirements.txt", 
  "ml/analysis_and_solution.ipynb" 
  -DestinationPath "PARS-submission.zip" -Force
`
