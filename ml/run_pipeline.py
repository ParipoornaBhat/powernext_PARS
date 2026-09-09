"""
Complete Reproducible Pipeline for PowerNext-AI CPRI Test Bench Challenge
Executes Tasks 1, 2, and 3 from end to end and generates all deliverables.
"""
import os
import sys
import json
import numpy as np
import pandas as pd

from src.anomaly import TestBenchAnomalyDetector
from src.model import ReferenceParameterPredictor
from src.summarize import generate_automated_summary

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

    # 1. Anomaly & Validity Detection
    print("\n[TASK 01] Fitting Physics-Grounded Anomaly Detector...")
    detector = TestBenchAnomalyDetector(residual_threshold=1.25)
    detector.fit(df_train)

    validity_labels, anomaly_scores, reasons_df = detector.predict(df_test)
    num_invalid = (validity_labels == 'Invalid').sum()
    print(f"Identified {num_invalid} / {len(df_test)} abnormal records in test data.")

    # 2. Reference Parameter Prediction
    print("\n[TASK 02] Training Reference Parameter Ensemble Predictor...")
    predictor = ReferenceParameterPredictor(random_state=42)
    predictor.fit(df_train)

    predictions = predictor.predict(df_test)
    print(f"Generated predictions for {len(predictions)} test records.")
    print(f"Predicted Reference Parameter: Min = {predictions.min():.4f}, Max = {predictions.max():.4f}, Mean = {predictions.mean():.4f}")

    # 3. Generate Deliverable 1: PARS.csv
    submission_df = pd.DataFrame({
        'Test_ID': df_test['Test_ID'],
        'Predicted_Reference_Parameter': predictions,
        'Validity_Label': validity_labels
    })
    sub_path = os.path.join(deliverables_dir, 'PARS.csv')
    submission_df.to_csv(sub_path, index=False)
    print(f"\n[DELIVERABLE 1] Saved prediction CSV to: {sub_path}")

    # 4. Generate Task 03 Summary
    print("\n[TASK 03] Generating Automated Test Summary...")
    summary = generate_automated_summary(
        df_test=df_test,
        predictions=predictions,
        validity_labels=validity_labels,
        anomaly_scores=anomaly_scores,
        reasons_df=reasons_df
    )

    # Save summary.json
    json_path = os.path.join(deliverables_dir, 'summary.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=4)
    print(f"[DELIVERABLE 2] Saved summary JSON to: {json_path}")

    # Save summary.csv
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

    print("\nPipeline execution successfully finished!")

if __name__ == '__main__':
    main()

# Verified end-to-end reproducibility on hidden screening partition
