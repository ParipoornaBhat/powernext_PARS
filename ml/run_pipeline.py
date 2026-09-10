"""
Complete Reproducible Pipeline for PowerNext-AI CPRI Test Bench Challenge
Executes Tasks 1, 2, and 3 from end to end and generates all deliverables.
Includes 95% Conformal Prediction Intervals, Sensor Fault Diagnostics,
Multi-Sensor Mahalanobis Consistency, SHAP Explainability, and Model Benchmarks.
"""
import os
import sys
import json
import numpy as np
import pandas as pd

from src.anomaly import TestBenchAnomalyDetector
from src.model import ReferenceParameterPredictor
from src.summarize import generate_automated_summary
from src.benchmark import run_ablation_benchmark
from src.analysis_plots import generate_analysis_figures

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(root_dir)
    dataset_dir = os.path.join(project_dir, 'dataset')
    deliverables_dir = os.path.join(project_dir, 'deliverables')
    os.makedirs(deliverables_dir, exist_ok=True)

    train_path = os.path.join(dataset_dir, 'training_data.csv')
    test_path = os.path.join(dataset_dir, 'test_data.csv')

    print(f"Loading training data from {train_path}...")
    df_train = pd.read_csv(train_path)
    print(f"Loaded {len(df_train)} training records.")

    print(f"Loading test data from {test_path}...")
    df_test = pd.read_csv(test_path)
    print(f"Loaded {len(df_test)} test records.")

    print("\n[TASK 01] Fitting Physics-Grounded Anomaly & Consistency Detector...")
    detector = TestBenchAnomalyDetector(residual_threshold=1.25)
    detector.fit(df_train)

    validity_labels, anomaly_scores, reasons_df = detector.predict(df_test)
    num_invalid = (validity_labels == 'Invalid').sum()
    print(f"Identified {num_invalid} / {len(df_test)} abnormal records in test data.")
    print(f"Covariance estimator: {detector.covariance_method}")
    print("Fault breakdown on test records:")
    for ftype, count in reasons_df['Fault_Type'].value_counts().items():
        print(f"  - {ftype}: {count}")

    print("\n[TASK 02] Training Reference Parameter Ensemble & Calibrating Conformal Intervals...")
    predictor = ReferenceParameterPredictor(random_state=42)
    predictor.fit(df_train, calibrate_conformal=True)

    predictions, lowers, uppers, widths, margin = predictor.predict_with_intervals(df_test)
    print(f"Generated predictions for {len(predictions)} test records.")
    print(f"Predicted Reference Parameter: Min = {predictions.min():.4f}, Max = {predictions.max():.4f}, Mean = {predictions.mean():.4f}")
    print(f"Conformal 95% Prediction Interval Margin: +/- {margin:.4f} deg C")
    print(f"Calibration meta: {predictor.conformal_meta}")

    cal_path = os.path.join(deliverables_dir, 'conformal_calibration.json')
    with open(cal_path, 'w', encoding='utf-8') as f:
        json.dump(predictor.conformal_meta, f, indent=4)
    print(f"Saved conformal calibration to: {cal_path}")

    print("\n[TASK 02b] Computing Tree SHAP Attributions for Explainability...")
    shap_data = predictor.explain(df_test)
    shap_path = os.path.join(deliverables_dir, 'shap_explanations.json')
    with open(shap_path, 'w', encoding='utf-8') as f:
        json.dump(shap_data, f, indent=4)
    print(f"Saved SHAP explanations to: {shap_path}")
    print(f"SHAP method: {shap_data.get('method')}")
    print("Top 3 Global Feature Drivers (Mean Absolute SHAP):")
    for feat, imp in list(shap_data['global_importance'].items())[:3]:
        print(f"  - {feat}: {imp:.4f} deg C")

    print("\n[BENCHMARK] Running Model Benchmark & Ablation Study...")
    bench_path = os.path.join(deliverables_dir, 'benchmark_results.json')
    run_ablation_benchmark(train_path, bench_path, conformal_margin=margin)

    shap_by_id = {row['test_id']: row for row in shap_data['sample_explanations']}
    shap_pos = []
    shap_neg = []
    for tid in df_test['Test_ID'].astype(str):
        expl = shap_by_id.get(tid, {})
        shap_pos.append("; ".join(expl.get('increased_hotspot') or []))
        shap_neg.append("; ".join(expl.get('decreased_hotspot') or []))

    submission_df = pd.DataFrame({
        'Test_ID': df_test['Test_ID'],
        'Predicted_Reference_Parameter': predictions,
        'Validity_Label': validity_labels,
        'Interval_95_Lower': lowers,
        'Interval_95_Upper': uppers,
        'Interval_Width': widths,
        'Interval_Margin': [margin] * len(df_test),
        'Applied_Voltage_kV': df_test['Applied_Voltage_kV'],
        'Load_Current_A': df_test['Load_Current_A'],
        'Ambient_Temperature_C': df_test['Ambient_Temperature_C'],
        'Test_Duration_min': df_test['Test_Duration_min'],
        'Sensor_S1': df_test['Sensor_S1'],
        'Sensor_S2': df_test['Sensor_S2'],
        'Sensor_S3': df_test['Sensor_S3'],
        'Sensor_S4': df_test['Sensor_S4'],
        'Anomaly_Score': np.round(anomaly_scores, 4),
        'Reason': reasons_df['Reason'],
        'Fault_Detected': reasons_df['Fault_Detected'],
        'Fault_Type': reasons_df['Fault_Type'],
        'Fault_Sensor': reasons_df['Fault_Sensor'],
        'Fault_Severity': reasons_df['Fault_Severity'],
        'Fault_Reason': reasons_df['Fault_Reason'],
        'Fault_Confidence': reasons_df['Fault_Confidence'],
        'Mahalanobis_Distance': reasons_df['Mahalanobis_Distance'],
        'Cross_Sensor_Inconsistent': reasons_df['Cross_Sensor_Inconsistent'],
        'Contributing_Sensors': reasons_df['Contributing_Sensors'],
        'Multivariate_Anomaly_Score': reasons_df['Multivariate_Anomaly_Score'],
        'S1_Residual': reasons_df['S1_Residual'],
        'S2_Residual': reasons_df['S2_Residual'],
        'S3_Residual': reasons_df['S3_Residual'],
        'SHAP_Increased_Hotspot': shap_pos,
        'SHAP_Decreased_Hotspot': shap_neg
    })
    sub_path = os.path.join(deliverables_dir, 'PARS.csv')
    submission_df.to_csv(sub_path, index=False)
    print(f"\n[DELIVERABLE 1] Saved prediction CSV to: {sub_path}")

    print("\n[TASK 03] Generating Automated Test Summary...")
    summary = generate_automated_summary(
        df_test=df_test,
        predictions=predictions,
        validity_labels=validity_labels,
        anomaly_scores=anomaly_scores,
        reasons_df=reasons_df,
        conformal_margin=margin,
        conformal_meta=predictor.conformal_meta
    )

    json_path = os.path.join(deliverables_dir, 'summary.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=4)
    print(f"[DELIVERABLE 2] Saved summary JSON to: {json_path}")

    csv_path = os.path.join(deliverables_dir, 'summary.csv')
    flat_summary = {
        'Metric': [
            'number_of_records_analysed',
            'number_of_abnormal_records_identified',
            'minimum_predicted_reference_parameter',
            'maximum_predicted_reference_parameter',
            'average_predicted_reference_parameter',
            'three_test_ids_requiring_highest_attention',
            'methodology_explanation'
        ],
        'Value': [
            summary['number_of_records_analysed'],
            summary['number_of_abnormal_records_identified'],
            summary['minimum_predicted_reference_parameter'],
            summary['maximum_predicted_reference_parameter'],
            summary['average_predicted_reference_parameter'],
            ", ".join(summary['three_test_ids_requiring_highest_attention']),
            summary['methodology_explanation']
        ]
    }
    pd.DataFrame(flat_summary).to_csv(csv_path, index=False)
    print(f"[DELIVERABLE 2] Saved summary CSV to: {csv_path}")

    print("\n[PLOTS] Generating analysis figures from actual results...")
    fig_dir = os.path.join(deliverables_dir, 'analysis_figures')
    generate_analysis_figures(
        train_path, test_path, sub_path, json_path, bench_path, shap_path, fig_dir
    )

    print("\nPipeline execution successfully finished!")

if __name__ == '__main__':
    main()
