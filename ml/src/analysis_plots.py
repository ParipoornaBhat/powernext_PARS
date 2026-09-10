"""Generate analysis figures from actual pipeline deliverables (no fabricated values)."""
from typing import Optional
import os
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def generate_analysis_figures(
    train_path: str,
    test_path: str,
    pars_path: str,
    summary_path: str,
    benchmark_path: str,
    shap_path: str,
    out_dir: str
) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    train = pd.read_csv(train_path)
    test = pd.read_csv(test_path)
    pars = pd.read_csv(pars_path)
    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)
    with open(benchmark_path, "r", encoding="utf-8") as f:
        bench = json.load(f)
    with open(shap_path, "r", encoding="utf-8") as f:
        shap = json.load(f)

    saved = []

    # 1. Target distribution (verified training)
    fig, ax = plt.subplots(figsize=(7, 4))
    valid = train[train["Validity_Label"] == "Valid"]
    ax.hist(valid["Reference_Parameter"], bins=30, color="#c4824d", edgecolor="white")
    ax.set_title("Verified training Reference_Parameter distribution")
    ax.set_xlabel("Reference_Parameter (°C)")
    ax.set_ylabel("Count")
    path = os.path.join(out_dir, "target_distribution.png")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    saved.append(path)

    # 2. Correlation matrix on numeric training columns
    cols = [
        "Applied_Voltage_kV", "Load_Current_A", "Ambient_Temperature_C", "Test_Duration_min",
        "Sensor_S1", "Sensor_S2", "Sensor_S3", "Sensor_S4", "Reference_Parameter"
    ]
    corr = valid[cols].corr()
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(corr.values, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(cols)))
    ax.set_yticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=60, ha="right", fontsize=7)
    ax.set_yticklabels(cols, fontsize=7)
    ax.set_title("Correlation matrix (verified training records)")
    fig.colorbar(im, ax=ax, fraction=0.046)
    path = os.path.join(out_dir, "correlation_matrix.png")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    saved.append(path)

    # 3. Global SHAP importance
    gi = shap["global_importance"]
    feats = list(gi.keys())
    vals = [gi[k] for k in feats]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.barh(feats[::-1], vals[::-1], color="#8c562c")
    ax.set_xlabel("Mean |SHAP| (°C)")
    ax.set_title(f"Global feature importance ({shap.get('method', 'SHAP')})")
    path = os.path.join(out_dir, "feature_importance.png")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    saved.append(path)

    # 4. Actual vs predicted on verified training is not in PARS; use test predictions vs sensors as proxy is wrong.
    # Plot predicted vs interval mid / residual width, and if training labels exist we skip test actuals.
    # Residual-like view: interval width vs prediction.
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.scatter(pars["Predicted_Reference_Parameter"], pars["Interval_95_Upper"] - pars["Interval_95_Lower"],
               s=12, alpha=0.6, color="#4b7a47")
    ax.set_xlabel("Predicted Reference_Parameter (°C)")
    ax.set_ylabel("95% interval width (°C)")
    ax.set_title("Conformal prediction interval width vs predicted hotspot (test)")
    path = os.path.join(out_dir, "conformal_intervals.png")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    saved.append(path)

    # 5. Anomaly score distribution
    if "Anomaly_Score" in pars.columns:
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.hist(pars["Anomaly_Score"], bins=30, color="#a64b2a", edgecolor="white")
        ax.set_title("Test-set anomaly score distribution")
        ax.set_xlabel("Anomaly score (°C residual)")
        path = os.path.join(out_dir, "anomaly_distribution.png")
        fig.tight_layout()
        fig.savefig(path, dpi=140)
        plt.close(fig)
        saved.append(path)

    # 6. Fault type distribution
    if "Fault_Type" in pars.columns:
        counts = pars["Fault_Type"].value_counts()
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.barh(counts.index.astype(str)[::-1], counts.values[::-1], color="#c4824d")
        ax.set_title("Sensor/equipment diagnostic distribution (test)")
        ax.set_xlabel("Count")
        path = os.path.join(out_dir, "sensor_fault_distribution.png")
        fig.tight_layout()
        fig.savefig(path, dpi=140)
        plt.close(fig)
        saved.append(path)

    # 7. Benchmark comparison
    table = bench["benchmark_table"]
    names = [r["model"] for r in table]
    r2s = [r["r2_score"] for r in table]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(names[::-1], r2s[::-1], color="#4b7a47")
    ax.set_xlim(0.8, 1.0)
    ax.set_xlabel("5-fold OOF R²")
    ax.set_title("Model benchmark (verified training, same KFold)")
    path = os.path.join(out_dir, "model_benchmark.png")
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    saved.append(path)

    # 8. Residual distribution from conformal calibration metadata if present
    # Use S residuals on test as physical residual view
    fig, ax = plt.subplots(figsize=(7, 4))
    if {"S1_Residual", "S2_Residual", "S3_Residual"}.issubset(pars.columns):
        ax.hist(pars["S1_Residual"], bins=25, alpha=0.5, label="S1", color="#c4824d")
        ax.hist(pars["S2_Residual"], bins=25, alpha=0.5, label="S2", color="#4b7a47")
        ax.hist(pars["S3_Residual"], bins=25, alpha=0.5, label="S3", color="#8c562c")
        ax.legend()
        ax.set_title("Physics residual distribution on test records")
        ax.set_xlabel("Signed residual (°C)")
        path = os.path.join(out_dir, "residual_distribution.png")
        fig.tight_layout()
        fig.savefig(path, dpi=140)
        plt.close(fig)
        saved.append(path)
    else:
        plt.close(fig)

    return {"figures": saved, "summary_keys": list(summary.keys())}
