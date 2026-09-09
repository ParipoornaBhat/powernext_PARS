"""
CPRI Electrical Test Bench Anomaly & Validity Detection Module
Distinguishes between genuine operating regime changes and erroneous measurements.
"""
from typing import Tuple, Dict, Any
import numpy as np
import pandas as pd
from sklearn.linear_model import HuberRegressor

OPERATING_COLS = [
    'Applied_Voltage_kV',
    'Load_Current_A',
    'Ambient_Temperature_C',
    'Test_Duration_min'
]

ALL_FEATURE_COLS = [
    'Applied_Voltage_kV',
    'Load_Current_A',
    'Ambient_Temperature_C',
    'Test_Duration_min',
    'Sensor_S1',
    'Sensor_S2',
    'Sensor_S3',
    'Sensor_S4'
]

class TestBenchAnomalyDetector:
    def __init__(self, residual_threshold: float = 1.25):
        self.residual_threshold = residual_threshold
        self.models = {}
        self.reference_set = set()

    def fit(self, df_train: pd.DataFrame):
        """Fit baseline physical coupling models on engineer-verified Valid records."""
        valid_df = df_train[df_train['Validity_Label'] == 'Valid'].copy()
        
        # Fit robust physics-guided estimators for sensors S1, S2, S3 against (V, I)
        X_vi = valid_df[['Applied_Voltage_kV', 'Load_Current_A']].values
        for sensor in ['Sensor_S1', 'Sensor_S2', 'Sensor_S3']:
            y_sensor = valid_df[sensor].values
            hr = HuberRegressor(epsilon=1.35)
            hr.fit(X_vi, y_sensor)
            self.models[sensor] = hr

        # Store known parameter fingerprints to track duplicate setpoints
        for _, row in valid_df[ALL_FEATURE_COLS].iterrows():
            fp = tuple(np.round(row.values.astype(float), 3))
            self.reference_set.add(fp)

        return self

    def predict(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame]:
        """
        Predict validity and anomaly scores.
        Returns:
            labels: np.ndarray of 'Valid' or 'Invalid'
            anomaly_scores: np.ndarray of continuous float anomaly intensity
            details_df: pd.DataFrame with breakdown of reasons
        """
        n = len(df)
        labels = np.array(['Valid'] * n, dtype=object)
        anomaly_scores = np.zeros(n, dtype=float)
        reasons = []

        # 1. Check for duplicate operational setpoints within the input set
        duplicated_mask = df.duplicated(subset=ALL_FEATURE_COLS, keep=False).values

        X_vi = df[['Applied_Voltage_kV', 'Load_Current_A']].values

        for i in range(n):
            row = df.iloc[i]
            row_reasons = []
            max_res = 0.0

            # Check for critical missing values in primary sensors
            null_sensors = [s for s in ['Sensor_S1', 'Sensor_S2', 'Sensor_S3'] if pd.isna(row[s])]
            if len(null_sensors) > 0:
                row_reasons.append(f"Missing readings in critical sensors: {', '.join(null_sensors)}")
                max_res = max(max_res, 10.0)

            # Check physical residual bounds for available sensors
            for sensor in ['Sensor_S1', 'Sensor_S2', 'Sensor_S3']:
                val = row[sensor]
                if not pd.isna(val):
                    expected = self.models[sensor].predict(X_vi[i:i+1])[0]
                    residual = abs(val - expected)
                    if residual > max_res:
                        max_res = residual
                    if residual > self.residual_threshold:
                        row_reasons.append(f"{sensor} physical deviation ({residual:.2f} deg C > threshold {self.residual_threshold})")

            # Check duplicate conflict
            if duplicated_mask[i]:
                row_reasons.append("Identical duplicate operational setpoint with conflicting record")
                max_res = max(max_res, 5.0)

            # Assign label
            if len(row_reasons) > 0:
                labels[i] = 'Invalid'
                anomaly_scores[i] = max_res
            else:
                labels[i] = 'Valid'
                anomaly_scores[i] = max_res

            reasons.append("; ".join(row_reasons) if row_reasons else "Normal Operating Condition")

        details_df = pd.DataFrame({
            'Test_ID': df['Test_ID'].values,
            'Validity_Label': labels,
            'Anomaly_Score': anomaly_scores,
            'Reason': reasons
        })

        return labels, anomaly_scores, details_df

# Audited multi-variable operational setpoint collisions

# Fine-tuned physical residual boundary thresholds
