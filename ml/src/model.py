"""
CPRI Thermal Model: Reference Parameter Prediction
Ensemble predictor using LightGBM and Gradient Boosting with physics-residual feature engineering.
"""
from typing import Tuple
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, ExtraTreesRegressor
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
        self.feature_means = {}

    def _prepare_features(self, df: pd.DataFrame, is_train: bool = False) -> pd.DataFrame:
        X = df[INPUT_FEATURES].copy()
        
        # Calculate or apply imputation means
        if is_train:
            for col in INPUT_FEATURES:
                self.feature_means[col] = X[col].median()
        for col in INPUT_FEATURES:
            X[col] = X[col].fillna(self.feature_means[col])

        # Engineering physics-based interaction features
        # Apparent Electrical Power Proxy (P ~ V * I)
        X['Power_Proxy_kVA'] = (X['Applied_Voltage_kV'] * X['Load_Current_A']) / 1000.0
        # Average Terminal Temperature Rise (Mean of S1 and S2)
        X['Terminal_TempRise_Mean'] = (X['Sensor_S1'] + X['Sensor_S2']) / 2.0
        # Temperature Gradient between critical sensor S3 and terminal S1
        X['Temp_Gradient_S3_S1'] = X['Sensor_S3'] - X['Sensor_S1']
        # Temperature Gradient between S2 and S1
        X['Temp_Gradient_S2_S1'] = X['Sensor_S2'] - X['Sensor_S1']
        # Absolute Hotspot Proxy: Ambient + Terminal Mean
        X['Ambient_Plus_Terminal'] = X['Ambient_Temperature_C'] + X['Terminal_TempRise_Mean']

        return X

    def fit(self, df_train: pd.DataFrame):
        """Fit ensemble regressor on engineer-verified Valid records."""
        valid_df = df_train[df_train['Validity_Label'] == 'Valid'].copy()
        X_train = self._prepare_features(valid_df, is_train=True)
        y_train = valid_df['Reference_Parameter'].values

        self.lgbm.fit(X_train, y_train)
        self.gbr.fit(X_train, y_train)
        self.etr.fit(X_train, y_train)
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Predict continuous Reference Parameter values using weighted ensemble."""
        X = self._prepare_features(df, is_train=False)
        p_lgbm = self.lgbm.predict(X)
        p_gbr = self.gbr.predict(X)
        p_etr = self.etr.predict(X)

        # Ensemble blend: 50% LightGBM + 30% GBR + 20% ExtraTrees
        ensemble_pred = 0.50 * p_lgbm + 0.30 * p_gbr + 0.20 * p_etr
        return np.round(ensemble_pred, 4)

# Calibrated ensemble blending: 50% LGBM + 30% GBR + 20% ExtraTrees
