import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

FEATURES = ['Applied_Voltage_kV', 'Load_Current_A', 'Ambient_Temperature_C', 'Test_Duration_min']

class ReferenceParameterPredictor:
    def __init__(self):
        self.model = LinearRegression()

    def fit(self, df_train: pd.DataFrame):
        valid = df_train[df_train['Validity_Label'] == 'Valid'].dropna(subset=FEATURES)
        self.model.fit(valid[FEATURES], valid['Reference_Parameter'])
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return self.model.predict(df[FEATURES])
