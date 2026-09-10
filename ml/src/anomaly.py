"""
CPRI Electrical Test Bench Anomaly & Validity Detection Module
Distinguishes genuine operating-regime changes from erroneous measurements.
Includes robust multi-sensor consistency (MinCovDet + Mahalanobis) and fault classification.
"""
from typing import Tuple, Dict, Any, List
import numpy as np
import pandas as pd
from sklearn.linear_model import HuberRegressor
from sklearn.covariance import MinCovDet, EmpiricalCovariance
from scipy import stats

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

PRIMARY_SENSORS = ['Sensor_S1', 'Sensor_S2', 'Sensor_S3']


class TestBenchAnomalyDetector:
    def __init__(self, residual_threshold: float = 1.25):
        self.residual_threshold = residual_threshold
        self.models: Dict[str, HuberRegressor] = {}
        self.reference_set = set()

        self.residual_mean: np.ndarray = np.zeros(3)
        self.residual_cov: np.ndarray = np.eye(3)
        self.residual_inv_cov: np.ndarray = np.eye(3)
        self.residual_stds: Dict[str, float] = {}
        self.covariance_method: str = "unfitted"
        # 99% Chi-square cutoff for 3 degrees of freedom
        self.mahalanobis_threshold = float(np.sqrt(stats.chi2.ppf(0.99, df=3)))

    def fit(self, df_train: pd.DataFrame):
        """Fit physics-guided residual models and robust residual covariance on Valid records."""
        valid_df = df_train[df_train['Validity_Label'] == 'Valid'].copy()

        X_vi = valid_df[['Applied_Voltage_kV', 'Load_Current_A']].values
        res_list = []
        for sensor in PRIMARY_SENSORS:
            y_sensor = valid_df[sensor].values
            hr = HuberRegressor(epsilon=1.35)
            hr.fit(X_vi, y_sensor)
            self.models[sensor] = hr
            res = y_sensor - hr.predict(X_vi)
            res_list.append(res)
            self.residual_stds[sensor] = float(np.std(res, ddof=1))

        residuals_train = np.array(res_list).T
        try:
            mcd = MinCovDet(random_state=42, support_fraction=0.75)
            mcd.fit(residuals_train)
            self.residual_mean = np.asarray(mcd.location_, dtype=float)
            self.residual_cov = np.asarray(mcd.covariance_, dtype=float)
            self.covariance_method = "MinCovDet"
        except Exception:
            emp = EmpiricalCovariance().fit(residuals_train)
            self.residual_mean = np.asarray(emp.location_, dtype=float)
            self.residual_cov = np.asarray(emp.covariance_, dtype=float)
            self.covariance_method = "EmpiricalCovariance"

        self.residual_inv_cov = np.linalg.pinv(self.residual_cov)

        for _, row in valid_df[ALL_FEATURE_COLS].iterrows():
            fp = tuple(np.round(row.values.astype(float), 3))
            self.reference_set.add(fp)

        return self

    def _mahalanobis(self, res_vec: np.ndarray) -> Tuple[float, np.ndarray]:
        delta = res_vec - self.residual_mean
        md = float(np.sqrt(max(0.0, float(np.dot(np.dot(delta, self.residual_inv_cov), delta)))))
        # Quadratic-form contributions (which sensors pulled the joint residual off-manifold)
        contrib = np.abs(delta * (self.residual_inv_cov @ delta))
        return md, contrib

    def predict(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame]:
        n = len(df)
        labels = np.array(['Valid'] * n, dtype=object)
        anomaly_scores = np.zeros(n, dtype=float)
        reasons = []

        fault_detected_list = []
        fault_type_list = []
        fault_sensor_list = []
        fault_severity_list = []
        fault_reason_list = []
        fault_confidence_list = []
        mahalanobis_list = []
        inconsistent_list = []
        contributing_list = []
        s1_res_list = []
        s2_res_list = []
        s3_res_list = []

        duplicated_mask = df.duplicated(subset=ALL_FEATURE_COLS, keep=False).values
        X_vi = df[['Applied_Voltage_kV', 'Load_Current_A']].values

        for i in range(n):
            row = df.iloc[i]
            row_reasons = []
            max_res = 0.0

            signed_residuals: Dict[str, float] = {}
            abs_residuals: Dict[str, float] = {}
            exceeded_sensors = []
            z_scores: Dict[str, float] = {}

            null_sensors = [s for s in PRIMARY_SENSORS if pd.isna(row[s])]
            if len(null_sensors) > 0:
                row_reasons.append(f"Missing readings in critical sensors: {', '.join(null_sensors)}")
                max_res = max(max_res, 10.0)

            for sensor in PRIMARY_SENSORS:
                val = row[sensor]
                if not pd.isna(val):
                    expected = self.models[sensor].predict(X_vi[i:i+1])[0]
                    diff = float(val - expected)
                    signed_residuals[sensor] = diff
                    res = abs(diff)
                    abs_residuals[sensor] = res
                    std_k = max(self.residual_stds.get(sensor, 0.35), 1e-6)
                    z_scores[sensor] = res / std_k

                    if res > max_res:
                        max_res = res
                    if res > self.residual_threshold:
                        exceeded_sensors.append(sensor)
                        row_reasons.append(
                            f"{sensor} physical deviation ({res:.2f} deg C > threshold {self.residual_threshold})"
                        )
                else:
                    signed_residuals[sensor] = 0.0
                    abs_residuals[sensor] = 10.0
                    z_scores[sensor] = 10.0

            s1_res_list.append(round(signed_residuals.get('Sensor_S1', 0.0), 3))
            s2_res_list.append(round(signed_residuals.get('Sensor_S2', 0.0), 3))
            s3_res_list.append(round(signed_residuals.get('Sensor_S3', 0.0), 3))

            md_val = 0.0
            contrib = np.zeros(3)
            if len(null_sensors) == 0:
                res_vec = np.array([
                    signed_residuals['Sensor_S1'],
                    signed_residuals['Sensor_S2'],
                    signed_residuals['Sensor_S3']
                ], dtype=float)
                md_val, contrib = self._mahalanobis(res_vec)
            mahalanobis_list.append(round(md_val, 3))

            contrib_sensors = []
            if md_val > self.mahalanobis_threshold and len(null_sensors) == 0:
                order = np.argsort(-contrib)
                total_c = float(np.sum(contrib)) + 1e-12
                for idx in order:
                    if contrib[idx] / total_c >= 0.20:
                        contrib_sensors.append(PRIMARY_SENSORS[idx])
                if not contrib_sensors:
                    contrib_sensors = [PRIMARY_SENSORS[int(np.argmax(contrib))]]
            contributing_list.append(", ".join(contrib_sensors) if contrib_sensors else "None")

            cross_inconsistent = bool(
                len(null_sensors) == 0 and md_val > self.mahalanobis_threshold
            )
            inconsistent_list.append(cross_inconsistent)

            if duplicated_mask[i]:
                row_reasons.append("Identical duplicate operational setpoint with conflicting record")
                max_res = max(max_res, 5.0)

            is_invalid = len(row_reasons) > 0
            if is_invalid:
                labels[i] = 'Invalid'
            else:
                labels[i] = 'Valid'
            anomaly_scores[i] = max_res
            combined_reason = "; ".join(row_reasons) if row_reasons else "Normal Operating Condition"
            reasons.append(combined_reason)

            load_current = float(row['Load_Current_A']) if not pd.isna(row['Load_Current_A']) else 0.0
            s1_val = float(row['Sensor_S1']) if not pd.isna(row['Sensor_S1']) else 0.0
            s2_val = float(row['Sensor_S2']) if not pd.isna(row['Sensor_S2']) else 0.0
            s3_val = float(row['Sensor_S3']) if not pd.isna(row['Sensor_S3']) else 0.0
            avg_thermal = (s1_val + s2_val + s3_val) / 3.0

            fault_detected = False
            fault_type = "None"
            fault_sensor = "None"
            fault_severity = "Normal"
            fault_reason = "Sensor readings conform to physical electro-thermal equilibrium"
            fault_conf_str = "N/A (Normal)"

            if len(null_sensors) > 0:
                fault_detected = True
                fault_type = "Missing Critical Sensor"
                fault_sensor = ", ".join(null_sensors)
                fault_severity = "Critical"
                fault_reason = f"Channel communication loss or unrecorded sensor in {fault_sensor}"
                fault_conf_str = "100.0% (Deterministic Rule)"

            elif duplicated_mask[i]:
                fault_detected = True
                fault_type = "Duplicate Setpoint Conflict"
                fault_sensor = "Multiple"
                fault_severity = "Critical"
                fault_reason = "Test bench data acquisition logged duplicate operational setpoints with conflicting records"
                fault_conf_str = "100.0% (Deterministic Rule)"

            elif len(exceeded_sensors) > 0:
                fault_detected = True
                primary_fault_sensor = max(exceeded_sensors, key=lambda s: abs_residuals[s])
                signed_val = signed_residuals[primary_fault_sensor]
                max_z = z_scores[primary_fault_sensor]
                p_conf = min(99.99, max(95.0, (1.0 - 2.0 * (1.0 - stats.norm.cdf(max_z))) * 100.0))

                if len(exceeded_sensors) == 1:
                    fault_sensor = primary_fault_sensor
                    if signed_val > 0:
                        fault_type = "Sensor Spike"
                        fault_severity = "Critical" if abs_residuals[primary_fault_sensor] > 3.0 else "Warning"
                        fault_reason = (
                            f"{primary_fault_sensor} registered abrupt positive spike of "
                            f"{abs_residuals[primary_fault_sensor]:.2f} deg C above thermodynamic expectation"
                        )
                    else:
                        fault_type = "Sensor Dropout"
                        fault_severity = "Critical"
                        fault_reason = (
                            f"{primary_fault_sensor} registered negative drop of "
                            f"{abs_residuals[primary_fault_sensor]:.2f} deg C below expectation (potential loose thermocouple)"
                        )
                    fault_conf_str = f"{p_conf:.1f}% (Z={max_z:.2f}, residual={abs_residuals[primary_fault_sensor]:.2f} C)"
                else:
                    fault_sensor = ", ".join(exceeded_sensors)
                    fault_type = "Other Sensor Anomaly"
                    fault_severity = "Critical"
                    fault_reason = f"Simultaneous multi-sensor deviation on {fault_sensor}"
                    fault_conf_str = f"{p_conf:.1f}% (Max Z={max_z:.2f})"

            elif (not is_invalid) and (md_val > self.mahalanobis_threshold):
                # Joint pattern is rare even though no single residual exceeds the 1.25 C Tier-1 gate
                fault_detected = True
                fault_type = "Multi-Sensor Correlation Anomaly"
                fault_sensor = ", ".join(contrib_sensors) if contrib_sensors else "Coupled S1-S3"
                fault_severity = "Warning"
                chi_p = 1.0 - stats.chi2.cdf(md_val ** 2, df=3)
                fault_reason = (
                    f"Cross-sensor residuals disagree with the robust covariance pattern "
                    f"(Mahalanobis D={md_val:.2f} > {self.mahalanobis_threshold:.2f})"
                )
                fault_conf_str = f"{(1.0 - chi_p) * 100.0:.1f}% (chi2 p={chi_p:.4f})"

            elif (not is_invalid) and (max_res > 0.85):
                fault_detected = True
                drift_sensor = max(PRIMARY_SENSORS, key=lambda s: abs_residuals.get(s, 0.0))
                fault_type = "Calibration Drift"
                fault_sensor = drift_sensor
                fault_severity = "Warning"
                fault_reason = f"{drift_sensor} shows borderline persistent bias of {abs_residuals[drift_sensor]:.2f} deg C"
                z_drift = z_scores[drift_sensor]
                p_drift = (1.0 - 2.0 * (1.0 - stats.norm.cdf(z_drift))) * 100.0
                fault_conf_str = f"{p_drift:.1f}% (Z={z_drift:.2f})"

            elif (not is_invalid) and (load_current > 85.0) and (avg_thermal > 19.5):
                # Physically consistent high-load / high-temperature operation — not a sensor fault
                fault_detected = True
                fault_type = "Genuine High-Temperature Operation"
                fault_sensor = "None (Equipment Alert)"
                fault_severity = "Warning"
                fault_reason = (
                    "Sensors remain within physical residual bounds (|e| <= 1.25 deg C) and are jointly consistent; "
                    "elevated temperature is consistent with high load rather than a sensor fault."
                )
                fault_conf_str = f"Physical Equilibrium Confirmed (MD={md_val:.2f})"

            fault_detected_list.append(fault_detected)
            fault_type_list.append(fault_type)
            fault_sensor_list.append(fault_sensor)
            fault_severity_list.append(fault_severity)
            fault_reason_list.append(fault_reason)
            fault_confidence_list.append(fault_conf_str)

        details_df = pd.DataFrame({
            'Test_ID': df['Test_ID'].values,
            'Validity_Label': labels,
            'Anomaly_Score': np.round(anomaly_scores, 4),
            'Reason': reasons,
            'Fault_Detected': fault_detected_list,
            'Fault_Type': fault_type_list,
            'Fault_Sensor': fault_sensor_list,
            'Fault_Severity': fault_severity_list,
            'Fault_Reason': fault_reason_list,
            'Fault_Confidence': fault_confidence_list,
            'Mahalanobis_Distance': mahalanobis_list,
            'Cross_Sensor_Inconsistent': inconsistent_list,
            'Contributing_Sensors': contributing_list,
            'Multivariate_Anomaly_Score': mahalanobis_list,
            'S1_Residual': s1_res_list,
            'S2_Residual': s2_res_list,
            'S3_Residual': s3_res_list
        })

        return labels, anomaly_scores, details_df
