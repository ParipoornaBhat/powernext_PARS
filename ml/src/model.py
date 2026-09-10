"""
CPRI Thermal Model: Reference Parameter Prediction
Ensemble predictor using LightGBM, Gradient Boosting, and ExtraTrees with physics-residual features.
Includes 95% conformal prediction intervals (out-of-fold residuals) and Tree SHAP.
"""
from typing import Tuple, Dict, Any, List, Optional
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, ExtraTreesRegressor
from sklearn.model_selection import KFold
from lightgbm import LGBMRegressor

INPUT_FEATURES = [
    'Applied_Voltage_kV',
    'Load_Current_A',
    'Ambient_Temperature_C',
    'Test_Duration_min',
    'Sensor_S1',
    'Sensor_S2',
    'Sensor_S3',
    'Sensor_S4'
]

FEATURE_COLUMNS = [
    'Applied_Voltage_kV',
    'Load_Current_A',
    'Ambient_Temperature_C',
    'Test_Duration_min',
    'Sensor_S1',
    'Sensor_S2',
    'Sensor_S3',
    'Sensor_S4',
    'Power_Proxy_kVA',
    'Terminal_TempRise_Mean',
    'Temp_Gradient_S3_S1',
    'Temp_Gradient_S2_S1',
    'Ambient_Plus_Terminal'
]

ENGINEERED_FEATURES = [
    'Power_Proxy_kVA',
    'Terminal_TempRise_Mean',
    'Temp_Gradient_S3_S1',
    'Temp_Gradient_S2_S1',
    'Ambient_Plus_Terminal'
]


def conformal_quantile_level(n: int, alpha: float = 0.05) -> float:
    """Finite-sample split-conformal quantile index as a fraction of n."""
    if n <= 0:
        return 1.0
    return min(1.0, float(np.ceil((n + 1) * (1.0 - alpha)) / n))


def conformal_margin_from_residuals(abs_residuals: np.ndarray, alpha: float = 0.05) -> Tuple[float, int, float]:
    """
    Empirical (1-alpha) conformal radius from absolute residuals.
    Uses the standard finite-sample rank: k = ceil((n+1)(1-alpha)), then the k-th order statistic.
    """
    errors = np.sort(np.asarray(abs_residuals, dtype=float))
    n = int(errors.size)
    if n == 0:
        return 0.0, 0, 1.0
    k = int(np.ceil((n + 1) * (1.0 - alpha)))
    k = min(max(k, 1), n)
    margin = float(errors[k - 1])
    q_level = conformal_quantile_level(n, alpha)
    return margin, k, q_level


class ReferenceParameterPredictor:
    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.lgbm = LGBMRegressor(
            n_estimators=300,
            learning_rate=0.03,
            num_leaves=31,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=random_state,
            verbose=-1
        )
        self.gbr = GradientBoostingRegressor(
            n_estimators=250,
            learning_rate=0.04,
            max_depth=4,
            subsample=0.85,
            random_state=random_state
        )
        self.etr = ExtraTreesRegressor(
            n_estimators=200,
            max_depth=12,
            random_state=random_state
        )
        self.feature_means: Dict[str, float] = {}
        self.conformal_margin: Optional[float] = None
        self.conformal_meta: Dict[str, Any] = {}
        self.base_value: float = 0.0
        self.shap_method: str = ""

    def _prepare_features(self, df: pd.DataFrame, is_train: bool = False) -> pd.DataFrame:
        X = df[INPUT_FEATURES].copy()

        if is_train:
            for col in INPUT_FEATURES:
                self.feature_means[col] = float(X[col].median())
        for col in INPUT_FEATURES:
            X[col] = X[col].fillna(self.feature_means[col])

        X['Power_Proxy_kVA'] = (X['Applied_Voltage_kV'] * X['Load_Current_A']) / 1000.0
        X['Terminal_TempRise_Mean'] = (X['Sensor_S1'] + X['Sensor_S2']) / 2.0
        X['Temp_Gradient_S3_S1'] = X['Sensor_S3'] - X['Sensor_S1']
        X['Temp_Gradient_S2_S1'] = X['Sensor_S2'] - X['Sensor_S1']
        X['Ambient_Plus_Terminal'] = X['Ambient_Temperature_C'] + X['Terminal_TempRise_Mean']

        return X[FEATURE_COLUMNS]

    def _ensemble_predict_arrays(self, p_lgbm, p_gbr, p_etr) -> np.ndarray:
        return 0.50 * p_lgbm + 0.30 * p_gbr + 0.20 * p_etr

    def fit(self, df_train: pd.DataFrame, calibrate_conformal: bool = True):
        """Fit ensemble on engineer-verified Valid records and calibrate conformal margin."""
        valid_df = df_train[df_train['Validity_Label'] == 'Valid'].copy().reset_index(drop=True)
        X_train = self._prepare_features(valid_df, is_train=True)
        y_train = valid_df['Reference_Parameter'].values

        self.lgbm.fit(X_train, y_train)
        self.gbr.fit(X_train, y_train)
        self.etr.fit(X_train, y_train)

        if calibrate_conformal and len(valid_df) > 50:
            kf = KFold(n_splits=5, shuffle=True, random_state=self.random_state)
            oof_errors: List[float] = []
            for tr_idx, val_idx in kf.split(valid_df):
                X_tr, y_tr = X_train.iloc[tr_idx], y_train[tr_idx]
                X_val, y_val = X_train.iloc[val_idx], y_train[val_idx]

                m_lgb = LGBMRegressor(
                    n_estimators=300, learning_rate=0.03, num_leaves=31,
                    subsample=0.85, colsample_bytree=0.85,
                    random_state=self.random_state, verbose=-1
                ).fit(X_tr, y_tr)
                m_gbr = GradientBoostingRegressor(
                    n_estimators=250, learning_rate=0.04, max_depth=4,
                    subsample=0.85, random_state=self.random_state
                ).fit(X_tr, y_tr)
                m_etr = ExtraTreesRegressor(
                    n_estimators=200, max_depth=12, random_state=self.random_state
                ).fit(X_tr, y_tr)

                pred_val = self._ensemble_predict_arrays(
                    m_lgb.predict(X_val), m_gbr.predict(X_val), m_etr.predict(X_val)
                )
                oof_errors.extend(np.abs(y_val - pred_val).tolist())

            margin, k, q_level = conformal_margin_from_residuals(np.asarray(oof_errors), alpha=0.05)
            self.conformal_margin = margin
            self.conformal_meta = {
                'method': 'split_conformal_absolute_residual_5fold_oof',
                'alpha': 0.05,
                'nominal_coverage': 0.95,
                'n_calibration_residuals': int(len(oof_errors)),
                'quantile_rank_k': int(k),
                'quantile_level': float(q_level),
                'mean_abs_oof_error_deg_C': float(np.mean(oof_errors)),
                'median_abs_oof_error_deg_C': float(np.median(oof_errors)),
                'conformal_margin_deg_C': float(margin),
                'interval_width_deg_C': float(2.0 * margin)
            }
        elif self.conformal_margin is not None:
            pass  # Retain pre-assigned conformal margin

        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        X = self._prepare_features(df, is_train=False)
        ensemble_pred = self._ensemble_predict_arrays(
            self.lgbm.predict(X), self.gbr.predict(X), self.etr.predict(X)
        )
        return np.round(ensemble_pred, 4)

    def predict_with_intervals(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
        """
        Predict Reference_Parameter with 95% conformal intervals.
        Returns predictions, lower_95, upper_95, interval_width (per row), and the calibrated margin.
        """
        if self.conformal_margin is None:
            raise ValueError("Conformal margin has not been calibrated.")
        preds = self.predict(df)
        margin = float(self.conformal_margin)
        lowers = np.round(np.maximum(0.0, preds - margin), 4)
        uppers = np.round(preds + margin, 4)
        widths = np.round(uppers - lowers, 4)
        return preds, lowers, uppers, widths, round(margin, 4)

    def explain(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Per-record and global SHAP for the linear ensemble:
        0.50 * LightGBM + 0.30 * GBR + 0.20 * ExtraTrees.
        TreeExplainer is applied to each member; attributions are combined with the same weights.
        This is the valid additive explanation for a convex combination of tree models.
        """
        X = self._prepare_features(df, is_train=False)
        shap_values = None
        base_val = 0.0
        method_notes = []

        try:
            import shap
            expl_lgbm = shap.TreeExplainer(self.lgbm)
            expl_gbr = shap.TreeExplainer(self.gbr)
            expl_etr = shap.TreeExplainer(self.etr)

            sv_lgbm = np.asarray(expl_lgbm.shap_values(X))
            sv_gbr = np.asarray(expl_gbr.shap_values(X))
            sv_etr = np.asarray(expl_etr.shap_values(X))

            ev_lgbm = expl_lgbm.expected_value
            ev_gbr = expl_gbr.expected_value
            ev_etr = expl_etr.expected_value
            if isinstance(ev_lgbm, (list, np.ndarray)):
                ev_lgbm = float(np.asarray(ev_lgbm).reshape(-1)[0])
            if isinstance(ev_gbr, (list, np.ndarray)):
                ev_gbr = float(np.asarray(ev_gbr).reshape(-1)[0])
            if isinstance(ev_etr, (list, np.ndarray)):
                ev_etr = float(np.asarray(ev_etr).reshape(-1)[0])

            shap_values = 0.50 * sv_lgbm + 0.30 * sv_gbr + 0.20 * sv_etr
            base_val = float(0.50 * ev_lgbm + 0.30 * ev_gbr + 0.20 * ev_etr)
            method_notes.append(
                "Weighted Tree SHAP over the PARS ensemble (0.50 LightGBM + 0.30 GBR + 0.20 ExtraTrees)."
            )
            self.shap_method = "weighted_tree_shap_ensemble"
        except Exception as exc:
            contribs = self.lgbm.booster_.predict(X, pred_contrib=True)
            shap_values = contribs[:, :-1]
            base_val = float(contribs[0, -1])
            method_notes.append(
                f"shap.TreeExplainer unavailable ({type(exc).__name__}: {exc}). "
                "Fell back to LightGBM pred_contrib (50% ensemble member only)."
            )
            self.shap_method = "lightgbm_pred_contrib_fallback"

        self.base_value = base_val
        mean_abs_shap = np.mean(np.abs(shap_values), axis=0)
        global_importance = {
            feat: round(float(imp), 4)
            for feat, imp in sorted(zip(FEATURE_COLUMNS, mean_abs_shap), key=lambda x: -x[1])
        }

        sample_explanations = []
        for i in range(len(df)):
            test_id = str(df.iloc[i].get('Test_ID', f"TST-{i:04d}"))
            row_contribs = {
                feat: round(float(val), 4)
                for feat, val in zip(FEATURE_COLUMNS, shap_values[i])
            }
            pos_drivers = [
                {'feature': feat, 'delta_deg_C': val}
                for feat, val in sorted(row_contribs.items(), key=lambda x: -x[1])
                if val > 0.0
            ]
            neg_drivers = [
                {'feature': feat, 'delta_deg_C': val}
                for feat, val in sorted(row_contribs.items(), key=lambda x: x[1])
                if val < 0.0
            ]
            sample_explanations.append({
                'test_id': test_id,
                'base_value': round(base_val, 4),
                'contributions': row_contribs,
                'top_positive': pos_drivers[:4],
                'top_negative': neg_drivers[:3],
                'increased_hotspot': [d['feature'] for d in pos_drivers[:4]],
                'decreased_hotspot': [d['feature'] for d in neg_drivers[:3]]
            })

        return {
            'feature_names': FEATURE_COLUMNS,
            'base_value': round(base_val, 4),
            'global_importance': global_importance,
            'sample_explanations': sample_explanations,
            'method': self.shap_method,
            'method_notes': method_notes
        }
