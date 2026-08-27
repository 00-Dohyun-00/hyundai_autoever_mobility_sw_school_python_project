# -*- coding: utf-8 -*-
"""classification.py의 사출성형 불량 예측 분석(데이터 개요 -> 모델1 -> 모델2 -> 결론)을
Streamlit이 아닌 Flask/Jinja2 페이지에서 보여주기 위해 이식한 모듈.
"""

import base64
import io
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    ConfusionMatrixDisplay,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    RocCurveDisplay,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

plt.rcParams["axes.unicode_minus"] = False

# classification.py의 슬라이더 기본값을 그대로 고정 threshold로 사용한다.
LOG_THRESHOLD = 0.50
RF_THRESHOLD = 0.30

# 예측 탭에서 재사용할 학습된 모델/기본값 저장 위치.
# 이 파일 기준 analysis/ 의 부모(=project_root)/models 에 저장한다.
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)

MODEL_FILENAMES = {
    "Logistic Regression": "logistic_regression.joblib",
    "Random Forest": "random_forest.joblib",
}
DEFAULTS_PATH = MODELS_DIR / "feature_defaults.joblib"


def _fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _build_preprocessor(numeric_cols, categorical_cols):
    numeric_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="mean")),
        ("scaler", StandardScaler()),
    ])
    categorical_transformer = Pipeline(steps=[
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    return ColumnTransformer(transformers=[
        ("num", numeric_transformer, numeric_cols),
        ("cat", categorical_transformer, categorical_cols),
    ])


def _plot_class_distribution(y):
    fig, ax = plt.subplots(figsize=(3, 2.2))
    y.value_counts().sort_index().plot(kind="bar", ax=ax, color=["#1f77b4", "#d62728"])
    ax.set_xticklabels(["Normal(0)", "Defect(1)"], rotation=0, fontsize=8)
    ax.set_title("Class Distribution", fontsize=9)
    ax.set_ylabel("Count", fontsize=8)
    ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _plot_confusion_matrix(y_true, y_pred, model_name):
    fig, ax = plt.subplots(figsize=(4, 3.6))
    cm = confusion_matrix(y_true, y_pred)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=["Normal(0)", "Defect(1)"])
    disp.plot(ax=ax, cmap="Blues", colorbar=False)
    ax.set_title(f"Confusion Matrix - {model_name}")
    fig.tight_layout()
    return _fig_to_base64(fig)


def _plot_roc_curve(y_true, y_proba, model_name):
    fig, ax = plt.subplots(figsize=(4, 3.6))
    RocCurveDisplay.from_predictions(y_true, y_proba, ax=ax)
    auc = roc_auc_score(y_true, y_proba)
    ax.set_title(f"ROC Curve - {model_name} (AUC={auc:.3f})")
    fig.tight_layout()
    return _fig_to_base64(fig)


def _plot_feature_importance(model, numeric_cols, categorical_cols, model_name, top_n=15):
    classifier = model.named_steps["classifier"]
    ohe = model.named_steps["preprocessor"].named_transformers_["cat"].named_steps["onehot"]
    cat_feature_names = ohe.get_feature_names_out(categorical_cols)
    all_feature_names = np.array(numeric_cols + list(cat_feature_names))

    if hasattr(classifier, "coef_"):
        values = classifier.coef_[0]
        signed, xlabel = True, "Coefficient value"
    else:
        values = classifier.feature_importances_
        signed, xlabel = False, "Importance"

    order = np.argsort(np.abs(values))[::-1][:top_n]
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    colors = (["#d62728" if v > 0 else "#1f77b4" for v in values[order]]
              if signed else ["#2ca02c"] * len(order))
    ax.barh(all_feature_names[order][::-1], values[order][::-1], color=colors[::-1])
    ax.set_title(f"Top {top_n} Feature Importance - {model_name}")
    ax.set_xlabel(xlabel)
    fig.tight_layout()
    return _fig_to_base64(fig)


def _model_result(name, model, y_test, y_proba, threshold, numeric_cols, categorical_cols):
    y_pred = (y_proba >= threshold).astype(int)
    return {
        "name": name,
        "threshold": threshold,
        "metrics": {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred),
            "recall": recall_score(y_test, y_pred),
            "f1": f1_score(y_test, y_pred),
            "auc": roc_auc_score(y_test, y_proba),
        },
        "confusion_matrix_img": _plot_confusion_matrix(y_test, y_pred, f"{name} (th={threshold:.2f})"),
        "roc_curve_img": _plot_roc_curve(y_test, y_proba, name),
        "feature_importance_img": _plot_feature_importance(model, numeric_cols, categorical_cols, name),
    }


def analyze_defect_classification(df):
    """사출 불량 예측 CSV를 분석해 템플릿에서 쓸 결과 dict를 반환한다."""
    df = df.copy()
    if "timestamp" in df.columns:
        df = df.drop(columns=["timestamp"])

    X = df.drop(columns=["defect_label"])
    y = df["defect_label"]
    categorical_cols = X.select_dtypes(include=["object"]).columns.tolist()
    numeric_cols = X.select_dtypes(include=["float64", "int64"]).columns.tolist()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    log_model = Pipeline(steps=[
        ("preprocessor", _build_preprocessor(numeric_cols, categorical_cols)),
        ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])
    log_model.fit(X_train, y_train)
    log_proba = log_model.predict_proba(X_test)[:, 1]

    rf_model = Pipeline(steps=[
        ("preprocessor", _build_preprocessor(numeric_cols, categorical_cols)),
        ("classifier", RandomForestClassifier(
            n_estimators=300, class_weight="balanced_subsample",
            random_state=42, n_jobs=-1,
        )),
    ])
    rf_model.fit(X_train, y_train)
    rf_proba = rf_model.predict_proba(X_test)[:, 1]

    # --- 예측 탭(/model)에서 재사용할 모델과 피처 기본값 저장 ---
    joblib.dump(log_model, MODELS_DIR / MODEL_FILENAMES["Logistic Regression"])
    joblib.dump(rf_model, MODELS_DIR / MODEL_FILENAMES["Random Forest"])

    feature_defaults = {
        "numeric_cols": numeric_cols,
        "categorical_cols": categorical_cols,
        # 폼에 없는 피처는 수치형=평균, 범주형=최빈값으로 채운다.
        "values": {
            **X[numeric_cols].mean().to_dict(),
            **{c: X[c].mode().iloc[0] for c in categorical_cols},
        },
    }
    joblib.dump(feature_defaults, DEFAULTS_PATH)
    # --- 저장 끝 ---

    log_result = _model_result(
        "Logistic Regression", log_model, y_test, log_proba, LOG_THRESHOLD,
        numeric_cols, categorical_cols,
    )
    rf_result = _model_result(
        "Random Forest", rf_model, y_test, rf_proba, RF_THRESHOLD,
        numeric_cols, categorical_cols,
    )

    auc_log = log_result["metrics"]["auc"]
    auc_rf = rf_result["metrics"]["auc"]

    return {
        "overview": {
            "total": len(df),
            "normal_count": int((y == 0).sum()),
            "normal_pct": (y == 0).mean() * 100,
            "defect_count": int((y == 1).sum()),
            "defect_pct": (y == 1).mean() * 100,
            "class_distribution_img": _plot_class_distribution(y),
            "preview": df.head(10).to_dict(orient="records"),
            "columns": list(df.columns),
        },
        "models": [log_result, rf_result],
        "conclusion": {
            "auc_diff": abs(auc_rf - auc_log),
            "top_features": "resin_moisture_pct(수지 수분율), injection_pressure_mpa(사출 압력)",
        },
    }
