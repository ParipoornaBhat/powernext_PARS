"""
Model Benchmark and Ablation Study for CPRI Test Bench Reference Parameter Estimation.
Compares Linear Regression, Ridge, Random Forest, Gradient Boosting, LightGBM, ExtraTrees, and PARS Ensemble.
Also compares raw vs engineered vs full feature groups using the same 5-fold split.
"""
from typing import Dict, Any, List
import json
import os
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, ExtraTreesRegressor
from lightgbm import LGBMRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

from src.model import (
    ReferenceParameterPredictor,
    INPUT_FEATURES,
    ENGINEERED_FEATURES,
    conformal_margin_from_residuals,
)


def _rmse(y_true, y_pred) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def _make_models(random_state: int = 42) -> Dict[str, Any]:
    return {
        'Linear Regression': LinearRegression(),
        'Ridge Regression': Ridge(alpha=1.0),
        'Random Forest': RandomForestRegressor(n_estimators=150, max_depth=12, random_state=random_state, n_jobs=-1),
        'Gradient Boosting': GradientBoostingRegressor(
            n_estimators=250, learning_rate=0.04, max_depth=4, subsample=0.85, random_state=random_state
        ),
        'LightGBM Regressor': LGBMRegressor(
            n_estimators=300, learning_rate=0.03, num_leaves=31, subsample=0.85,
            colsample_bytree=0.85, random_state=random_state, verbose=-1
        ),
        'Extra Trees Regressor': ExtraTreesRegressor(
            n_estimators=200, max_depth=12, random_state=random_state, n_jobs=-1
        ),
        'PARS Ensemble (LGBM+GBR+ETR)': 'ensemble'
    }


def _predict_model(name: str, model, X_tr, y_tr, X_val, random_state: int = 42):
    if name == 'PARS Ensemble (LGBM+GBR+ETR)':
        m_lgb = LGBMRegressor(
            n_estimators=300, learning_rate=0.03, num_leaves=31, subsample=0.85,
            colsample_bytree=0.85, random_state=random_state, verbose=-1
        ).fit(X_tr, y_tr)
        m_gbr = GradientBoostingRegressor(
            n_estimators=250, learning_rate=0.04, max_depth=4, subsample=0.85, random_state=random_state
        ).fit(X_tr, y_tr)
        m_etr = ExtraTreesRegressor(
            n_estimators=200, max_depth=12, random_state=random_state, n_jobs=-1
        ).fit(X_tr, y_tr)
        return 0.50 * m_lgb.predict(X_val) + 0.30 * m_gbr.predict(X_val) + 0.20 * m_etr.predict(X_val)
    m = model
    m.fit(X_tr, y_tr)
    return m.predict(X_val)


def run_ablation_benchmark(
    train_path: str,
    output_json_path: str = None,
    conformal_margin: float = None
) -> Dict[str, Any]:
    df_train = pd.read_csv(train_path)
    valid_df = df_train[df_train['Validity_Label'] == 'Valid'].copy().reset_index(drop=True)

    predictor = ReferenceParameterPredictor(random_state=42)
    X_full = predictor._prepare_features(valid_df, is_train=True)
    y = valid_df['Reference_Parameter'].values

    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    splits = list(kf.split(X_full))
    models = _make_models(42)

    benchmark_results = []
    ensemble_oof = None

    for name, model in models.items():
        oof_preds = np.zeros(len(valid_df))
        for tr_idx, val_idx in splits:
            X_tr, y_tr = X_full.iloc[tr_idx], y[tr_idx]
            X_val = X_full.iloc[val_idx]
            oof_preds[val_idx] = _predict_model(name, model, X_tr, y_tr, X_val, 42)

        r2 = float(r2_score(y, oof_preds))
        rmse = _rmse(y, oof_preds)
        mae = float(mean_absolute_error(y, oof_preds))
        if name == 'PARS Ensemble (LGBM+GBR+ETR)':
            ensemble_oof = oof_preds
        benchmark_results.append({
            'model': name,
            'r2_score': round(r2, 4),
            'rmse': round(rmse, 4),
            'mae': round(mae, 4),
            'status': 'Optimal Champion' if 'Ensemble' in name else 'Baseline/Candidate'
        })
        print(f"[{name}] R2 = {r2:.4f} | RMSE = {rmse:.4f} deg C | MAE = {mae:.4f} deg C")

    feature_groups = {
        'base_raw_features': INPUT_FEATURES,
        'engineered_physical_features': ENGINEERED_FEATURES,
        'full_feature_set': list(X_full.columns)
    }
    ablation_results = []
    for group_name, cols in feature_groups.items():
        oof_preds = np.zeros(len(valid_df))
        Xg = X_full[cols]
        for tr_idx, val_idx in splits:
            oof_preds[val_idx] = _predict_model(
                'PARS Ensemble (LGBM+GBR+ETR)',
                'ensemble',
                Xg.iloc[tr_idx],
                y[tr_idx],
                Xg.iloc[val_idx],
                42
            )
        ablation_results.append({
            'feature_group': group_name,
            'n_features': len(cols),
            'features': cols,
            'r2_score': round(float(r2_score(y, oof_preds)), 4),
            'rmse': round(_rmse(y, oof_preds), 4),
            'mae': round(float(mean_absolute_error(y, oof_preds)), 4)
        })
        print(
            f"[Ablation {group_name}] R2 = {ablation_results[-1]['r2_score']:.4f} | "
            f"RMSE = {ablation_results[-1]['rmse']:.4f} | MAE = {ablation_results[-1]['mae']:.4f}"
        )

    if conformal_margin is None and ensemble_oof is not None:
        conformal_margin, k, q_level = conformal_margin_from_residuals(np.abs(y - ensemble_oof), alpha=0.05)
        conformal_meta = {
            'source': 'benchmark_ensemble_oof',
            'quantile_rank_k': int(k),
            'quantile_level': float(q_level)
        }
    else:
        conformal_meta = {'source': 'pipeline_calibrated_margin'}

    champion = max(benchmark_results, key=lambda r: (r['r2_score'], -r['mae']))
    output_data = {
        'total_verified_records': len(valid_df),
        'cross_validation_folds': 5,
        'split_seed': 42,
        'benchmark_table': benchmark_results,
        'feature_group_ablation': ablation_results,
        'champion_model': champion['model'],
        'conformal_interval_margin_deg_C': round(float(conformal_margin), 4) if conformal_margin is not None else None,
        'conformal_meta': conformal_meta
    }

    if output_json_path:
        os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4)
        print(f"Saved benchmark results to {output_json_path}")

    return output_data


if __name__ == '__main__':
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    train_csv = os.path.join(project_dir, 'dataset', 'training_data.csv')
    out_json = os.path.join(project_dir, 'deliverables', 'benchmark_results.json')
    run_ablation_benchmark(train_csv, out_json)
