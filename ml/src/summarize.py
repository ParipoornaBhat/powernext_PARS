"""
CPRI Test Bench Automated Summary Generator
Generates statistical reporting, critical anomaly detection, and methodology statement.
"""
from typing import Dict, Any, List
import json
import numpy as np
import pandas as pd

def generate_automated_summary(
    df_test: pd.DataFrame,
    predictions: np.ndarray,
    validity_labels: np.ndarray,
    anomaly_scores: np.ndarray,
    reasons_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Computes Task 3 automated test summary:
    - Number of records analysed
    - Number of abnormal / invalid records identified
    - Minimum and maximum predicted Reference Parameter
    - Average predicted Reference Parameter
    - Three Test IDs requiring the highest attention
    - Under 100-word explanation of how the team approached the problem
    """
    total_records = int(len(df_test))
    abnormal_mask = (validity_labels == 'Invalid')
    num_abnormal = int(np.sum(abnormal_mask))

    min_ref = float(np.min(predictions))
    max_ref = float(np.max(predictions))
    avg_ref = float(np.mean(predictions))

    # Rank highest attention test benches by Anomaly Score
    sorted_indices = np.argsort(-anomaly_scores)
    top_3_records = []
    top_3_test_ids = []
    
    for idx in sorted_indices[:3]:
        tid = str(df_test.iloc[idx]['Test_ID'])
        top_3_test_ids.append(tid)
        top_3_records.append({
            'test_id': tid,
            'anomaly_score': float(anomaly_scores[idx]),
            'validity': str(validity_labels[idx]),
            'predicted_ref': float(predictions[idx]),
            'reason': str(reasons_df.iloc[idx]['Reason'])
        })

    approach_explanation = (
        "We formulated a physics-grounded verification framework coupling electro-thermal conservation "
        "with gradient-boosted ensemble modeling. First, physical residual boundaries between applied load "
        "(V, I) and primary terminal sensors (S1, S2, S3) detect sensor dropouts and physical spikes while "
        "preserving genuine operating regimes, combined with operational collision auditing. Auxiliary sensor "
        "S4 was isolated as uncorrelated ambient noise. Second, a cross-validated ensemble of LightGBM, "
        "Gradient Boosting, and ExtraTrees trained on verified records predicts the critical hotspot reference "
        "parameter with high thermodynamic fidelity."
    )

    word_count = len(approach_explanation.split())

    summary_data = {
        "number_of_records_analysed": total_records,
        "number_of_abnormal_records_identified": num_abnormal,
        "minimum_predicted_reference_parameter": round(min_ref, 4),
        "maximum_predicted_reference_parameter": round(max_ref, 4),
        "average_predicted_reference_parameter": round(avg_ref, 4),
        "three_test_ids_requiring_highest_attention": top_3_test_ids,
        "top_three_attention_details": top_3_records,
        "methodology_explanation": approach_explanation,
        "explanation_word_count": word_count
    }

    return summary_data
