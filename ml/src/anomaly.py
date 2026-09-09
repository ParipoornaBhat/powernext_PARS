import numpy as np
import pandas as pd

class TestBenchAnomalyDetector:
    def __init__(self, threshold=2.0):
        self.threshold = threshold

    def fit(self, df_train: pd.DataFrame):
        return self

    def predict(self, df: pd.DataFrame):
        invalid_mask = df[['Sensor_S1', 'Sensor_S2', 'Sensor_S3']].isna().any(axis=1)
        labels = np.where(invalid_mask, 'Invalid', 'Valid')
        scores = invalid_mask.astype(float) * 10.0
        details = pd.DataFrame({'Test_ID': df['Test_ID'], 'Validity_Label': labels, 'Anomaly_Score': scores})
        return labels, scores, details
