"""
Single/Batch CSV Evaluator for PowerNext-AI condition monitoring.
Accepts an arbitrary input CSV path and outputs complete JSON results.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import numpy as np
import pandas as pd

from src.anomaly import TestBenchAnomalyDetector
from src.model import ReferenceParameterPredictor

REQUIRED_COLUMNS = [
    'Applied_Voltage_kV',
    'Load_Current_A',
    'Ambient_Temperature_C',
    'Test_Duration_min',
    'Sensor_S1',
    'Sensor_S2',
    'Sensor_S3',
    'Sensor_S4'
]

NUMERIC_REQUIRED = REQUIRED_COLUMNS


def _load_saved_margin(project_dir: str):
    cal_path = os.path.join(project_dir, 'deliverables', 'conformal_calibration.json')
    if os.path.exists(cal_path):
        with open(cal_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        margin = data.get('conformal_margin_deg_C')
        if margin is not None:
            return float(margin), data
    return None, None


def validate_input_frame(df: pd.DataFrame) -> dict:
    if df is None or len(df) == 0:
        return {'ok': False, 'error': 'Empty file: CSV contains no data rows.'}

    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        return {
            'ok': False,
            'error': f"Missing required columns in CSV: {', '.join(missing_cols)}"
        }

    invalid_numeric = []
    for col in NUMERIC_REQUIRED:
        coerced = pd.to_numeric(df[col], errors='coerce')
        original_non_null = df[col].notna() & (df[col].astype(str).str.strip() != '')
        bad = original_non_null & coerced.isna()
        if bad.any():
            invalid_numeric.append(f"{col} ({int(bad.sum())} invalid value(s))")
    if invalid_numeric:
        return {
            'ok': False,
            'error': f"Invalid/non-numeric values: {'; '.join(invalid_numeric)}"
        }

    return {'ok': True}


def evaluate_csv_file(input_csv_path: str, train_csv_path: str) -> dict:
    if not os.path.exists(input_csv_path):
        return {'success': False, 'error': f'Input file not found: {input_csv_path}'}

    if os.path.getsize(input_csv_path) == 0:
        return {'success': False, 'error': 'Empty file: uploaded CSV has zero bytes.'}

    try:
        df_input = pd.read_csv(input_csv_path)
    except Exception as e:
        return {'success': False, 'error': f'Malformed CSV: failed to parse ({str(e)})'}

    check = validate_input_frame(df_input)
    if not check['ok']:
        return {'success': False, 'error': check['error']}

    for col in REQUIRED_COLUMNS:
        df_input[col] = pd.to_numeric(df_input[col], errors='coerce')

    if 'Test_ID' not in df_input.columns:
        df_input['Test_ID'] = [f"UPL-{i+1:04d}" for i in range(len(df_input))]

    df_train = pd.read_csv(train_csv_path)

    detector = TestBenchAnomalyDetector(residual_threshold=1.25)
    detector.fit(df_train)

    predictor = ReferenceParameterPredictor(random_state=42)
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    saved_margin, cal_meta = _load_saved_margin(project_dir)
    if saved_margin is not None:
        predictor.conformal_margin = saved_margin
        predictor.fit(df_train, calibrate_conformal=False)
        if cal_meta:
            predictor.conformal_meta = cal_meta
    else:
        predictor.fit(df_train, calibrate_conformal=True)

    labels, scores, reasons_df = detector.predict(df_input)
    preds, lowers, uppers, widths, margin = predictor.predict_with_intervals(df_input)
    shap_data = predictor.explain(df_input)

    records = []
    for i in range(len(df_input)):
        rec = {
            'Test_ID': str(df_input.iloc[i]['Test_ID']),
            'Applied_Voltage_kV': float(df_input.iloc[i]['Applied_Voltage_kV']),
            'Load_Current_A': float(df_input.iloc[i]['Load_Current_A']),
            'Ambient_Temperature_C': float(df_input.iloc[i]['Ambient_Temperature_C']),
            'Test_Duration_min': float(df_input.iloc[i]['Test_Duration_min']),
            'Sensor_S1': float(df_input.iloc[i]['Sensor_S1']) if not pd.isna(df_input.iloc[i]['Sensor_S1']) else None,
            'Sensor_S2': float(df_input.iloc[i]['Sensor_S2']) if not pd.isna(df_input.iloc[i]['Sensor_S2']) else None,
            'Sensor_S3': float(df_input.iloc[i]['Sensor_S3']) if not pd.isna(df_input.iloc[i]['Sensor_S3']) else None,
            'Sensor_S4': float(df_input.iloc[i]['Sensor_S4']) if not pd.isna(df_input.iloc[i]['Sensor_S4']) else None,
            'Predicted_Reference_Parameter': float(preds[i]),
            'Interval_95_Lower': float(lowers[i]),
            'Interval_95_Upper': float(uppers[i]),
            'Interval_Width': float(widths[i]),
            'Interval_Margin': float(margin),
            'Validity_Label': str(labels[i]),
            'Anomaly_Score': float(scores[i]),
            'Reason': str(reasons_df.iloc[i]['Reason']),
            'Fault_Detected': bool(reasons_df.iloc[i]['Fault_Detected']),
            'Fault_Type': str(reasons_df.iloc[i]['Fault_Type']),
            'Fault_Sensor': str(reasons_df.iloc[i]['Fault_Sensor']),
            'Fault_Severity': str(reasons_df.iloc[i]['Fault_Severity']),
            'Fault_Reason': str(reasons_df.iloc[i]['Fault_Reason']),
            'Fault_Confidence': str(reasons_df.iloc[i]['Fault_Confidence']),
            'Mahalanobis_Distance': float(reasons_df.iloc[i]['Mahalanobis_Distance']),
            'Cross_Sensor_Inconsistent': bool(reasons_df.iloc[i]['Cross_Sensor_Inconsistent']),
            'Contributing_Sensors': str(reasons_df.iloc[i]['Contributing_Sensors']),
            'Multivariate_Anomaly_Score': float(reasons_df.iloc[i]['Multivariate_Anomaly_Score']),
            'S1_Residual': float(reasons_df.iloc[i]['S1_Residual']),
            'S2_Residual': float(reasons_df.iloc[i]['S2_Residual']),
            'S3_Residual': float(reasons_df.iloc[i]['S3_Residual']),
            'SHAP': shap_data['sample_explanations'][i] if i < len(shap_data['sample_explanations']) else None
        }
        records.append(rec)

    invalid_count = int(np.sum(labels == 'Invalid'))
    summary = {
        'total_evaluated': len(df_input),
        'abnormal_count': invalid_count,
        'valid_count': len(df_input) - invalid_count,
        'min_hotspot_deg_C': float(np.min(preds)),
        'max_hotspot_deg_C': float(np.max(preds)),
        'mean_hotspot_deg_C': float(np.mean(preds)),
        'conformal_interval_margin_deg_C': float(margin),
        'global_shap_importance': shap_data['global_importance'],
        'shap_method': shap_data.get('method'),
        'covariance_method': detector.covariance_method
    }

    return {
        'success': True,
        'summary': summary,
        'records': records
    }


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'success': False, 'error': 'No input CSV path provided'}))
        sys.exit(1)

    in_csv = sys.argv[1]
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    trn_csv = os.path.join(project_dir, 'dataset', 'training_data.csv')
    res = evaluate_csv_file(in_csv, trn_csv)
    print(json.dumps(res))
