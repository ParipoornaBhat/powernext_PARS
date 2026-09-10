"""
CPRI Test Bench Automated Summary Generator
"""
from typing import Dict, Any, List
import numpy as np
import pandas as pd


def generate_automated_summary(
    df_test: pd.DataFrame,
    predictions: np.ndarray,
    validity_labels: np.ndarray,
    anomaly_scores: np.ndarray,
    reasons_df: pd.DataFrame,
    conformal_margin: float = None,
    conformal_meta: Dict[str, Any] = None
) -> Dict[str, Any]:
    total_records = int(len(df_test))
    abnormal_mask = (validity_labels == 'Invalid')
    num_abnormal = int(np.sum(abnormal_mask))

    min_ref = float(np.min(predictions))
    max_ref = float(np.max(predictions))
    avg_ref = float(np.mean(predictions))

    sorted_indices = np.argsort(-anomaly_scores)
    top_3_records = []
    top_3_test_ids = []

    for idx in sorted_indices[:3]:
        tid = str(df_test.iloc[idx]['Test_ID'])
        top_3_test_ids.append(tid)
        row_detail = {
            'test_id': tid,
            'anomaly_score': float(anomaly_scores[idx]),
            'validity': str(validity_labels[idx]),
            'predicted_ref': float(predictions[idx]),
            'reason': str(reasons_df.iloc[idx]['Reason'])
        }
        if 'Fault_Type' in reasons_df.columns:
            row_detail['fault_type'] = str(reasons_df.iloc[idx]['Fault_Type'])
            row_detail['fault_sensor'] = str(reasons_df.iloc[idx]['Fault_Sensor'])
            row_detail['fault_severity'] = str(reasons_df.iloc[idx]['Fault_Severity'])
            row_detail['fault_confidence'] = str(reasons_df.iloc[idx]['Fault_Confidence'])
        top_3_records.append(row_detail)

    approach_explanation = (
        "We formulated a physics-grounded verification framework coupling electro-thermal conservation "
        "with gradient-boosted ensemble modeling. First, physical residual boundaries between applied load "
        "(V, I) and primary terminal sensors (S1, S2, S3) detect sensor dropouts and physical spikes while "
        "preserving genuine operating regimes, combined with operational collision auditing. Auxiliary sensor "
        "S4 was isolated as uncorrelated ambient noise. Second, a cross-validated ensemble of LightGBM, "
        "Gradient Boosting, and ExtraTrees trained on verified records predicts the critical hotspot reference "
        "parameter with high thermodynamic fidelity."
    )

    summary_data = {
        "number_of_records_analysed": total_records,
        "number_of_abnormal_records_identified": num_abnormal,
        "minimum_predicted_reference_parameter": round(min_ref, 4),
        "maximum_predicted_reference_parameter": round(max_ref, 4),
        "average_predicted_reference_parameter": round(avg_ref, 4),
        "three_test_ids_requiring_highest_attention": top_3_test_ids,
        "top_three_attention_details": top_3_records,
        "methodology_explanation": approach_explanation,
        "explanation_word_count": len(approach_explanation.split())
    }

    if conformal_margin is not None:
        summary_data["conformal_prediction_margin_deg_C"] = round(float(conformal_margin), 4)
        summary_data["conformal_interval_width_deg_C"] = round(float(2.0 * conformal_margin), 4)
    if conformal_meta:
        summary_data["conformal_calibration"] = conformal_meta

    if 'Fault_Type' in reasons_df.columns:
        summary_data["fault_type_distribution"] = reasons_df['Fault_Type'].value_counts().to_dict()
    if 'Cross_Sensor_Inconsistent' in reasons_df.columns:
        summary_data["cross_sensor_inconsistent_count"] = int(reasons_df['Cross_Sensor_Inconsistent'].sum())

    return summary_data
