# -*- coding: utf-8 -*-
"""
사출성형 불량 예측 프로젝트 - 통합 UI (Streamlit)

탭 구조:
  tab1 -> 뉴스 크롤링 결과 (팀원 파트, 자리만 비워둠)
  tab2 -> 불량 분류 모델 (데이터 개요 -> 모델1 -> 모델2 -> 결론)
  tab3 -> 추후 추가될 파트 (지금은 주석 처리로 비워둠)

실행 방법: streamlit run app.py
"""

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report,
    ConfusionMatrixDisplay, RocCurveDisplay, roc_auc_score
)

plt.rcParams["axes.unicode_minus"] = False

st.set_page_config(page_title="사출성형 불량 예측 프로젝트", layout="wide")


# =========================================================
# 데이터 & 모델 로직 (캐싱해서 탭 전환/재실행해도 다시 안 돌게 함)
# =========================================================
CSV_PATH = "hyundai_autoever_injection_defect_classification_v2.csv"


@st.cache_data
def load_data():
    df = pd.read_csv(CSV_PATH)
    df = df.drop(columns=["timestamp"])
    X = df.drop(columns=["defect_label"])
    y = df["defect_label"]
    categorical_cols = X.select_dtypes(include=["object", "str"]).columns.tolist()
    numeric_cols = X.select_dtypes(include=["float64", "int64"]).columns.tolist()
    return df, X, y, categorical_cols, numeric_cols


df, X, y, categorical_cols, numeric_cols = load_data()

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)


def build_preprocessor():
    numeric_transformer = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="mean")),
        ("scaler", StandardScaler())
    ])
    categorical_transformer = Pipeline(steps=[
        ("onehot", OneHotEncoder(handle_unknown="ignore"))
    ])
    return ColumnTransformer(transformers=[
        ("num", numeric_transformer, numeric_cols),
        ("cat", categorical_transformer, categorical_cols)
    ])


@st.cache_resource
def train_logistic_regression():
    model = Pipeline(steps=[
        ("preprocessor", build_preprocessor()),
        ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced"))
    ])
    model.fit(X_train, y_train)
    y_proba = model.predict_proba(X_test)[:, 1]
    # threshold는 학습 결과에 고정하지 않고, UI 슬라이더에서 그때그때 적용
    return model, y_proba


@st.cache_resource
def train_random_forest():
    model = Pipeline(steps=[
        ("preprocessor", build_preprocessor()),
        ("classifier", RandomForestClassifier(
            n_estimators=300, class_weight="balanced_subsample",
            random_state=42, n_jobs=-1
        ))
    ])
    model.fit(X_train, y_train)
    y_proba = model.predict_proba(X_test)[:, 1]
    # threshold는 학습 결과에 고정하지 않고, UI 슬라이더에서 그때그때 적용
    # (모델 재학습 없이 판정 기준만 바꿔서 recall/precision 트레이드오프를 바로 확인하기 위함)
    return model, y_proba


def show_metrics(y_true, y_pred, y_proba):
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Accuracy", f"{accuracy_score(y_true, y_pred):.3f}")
    col2.metric("Precision", f"{precision_score(y_true, y_pred):.3f}")
    col3.metric("Recall", f"{recall_score(y_true, y_pred):.3f}")
    col4.metric("F1 Score", f"{f1_score(y_true, y_pred):.3f}")
    col5.metric("AUC", f"{roc_auc_score(y_true, y_proba):.3f}")


def plot_confusion_matrix(y_true, y_pred, model_name):
    fig, ax = plt.subplots(figsize=(4, 3.6))
    cm = confusion_matrix(y_true, y_pred)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=["Normal(0)", "Defect(1)"])
    disp.plot(ax=ax, cmap="Blues", colorbar=False)
    ax.set_title(f"Confusion Matrix - {model_name}")
    fig.tight_layout()
    return fig


def plot_roc_curve(y_true, y_proba, model_name):
    fig, ax = plt.subplots(figsize=(4, 3.6))
    RocCurveDisplay.from_predictions(y_true, y_proba, ax=ax)
    auc = roc_auc_score(y_true, y_proba)
    ax.set_title(f"ROC Curve - {model_name} (AUC={auc:.3f})")
    fig.tight_layout()
    return fig


def plot_feature_importance(model, model_name, top_n=15):
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
    return fig


# =========================================================
# 탭 구성
# =========================================================
tab1, tab2 = st.tabs(["📰 사출 관련 뉴스", "🔧 불량 예측 모델"])
# tab1, tab2, tab3 = st.tabs(["📰 사출 관련 뉴스", "🔧 불량 예측 모델", "추가 예정"])


# ---------------------------------------------------------
# tab1: 뉴스 크롤링 결과 (팀원 파트 - 자리만 비워둠)
# ---------------------------------------------------------
with tab1:
    st.header("사출 관련 뉴스")
    st.info("팀원이 크롤링한 뉴스 데이터가 여기에 들어갈 예정입니다.")
    # TODO: 팀원 크롤링 결과 연동
    # 예시:
    # news_df = pd.read_csv("news_crawling_result.csv")
    # st.dataframe(news_df)


# ---------------------------------------------------------
# tab2: 불량 예측 모델
# ---------------------------------------------------------
with tab2:

    # ---------- 1. 데이터 개요 ----------
    st.header("1. 데이터 개요")

    c1, c2, c3 = st.columns(3)
    c1.metric("전체 샘플 수", f"{len(df):,}")
    c2.metric("정상(0)", f"{(y == 0).sum():,} ({(y == 0).mean()*100:.1f}%)")
    c3.metric("불량(1)", f"{(y == 1).sum():,} ({(y == 1).mean()*100:.1f}%)")

    st.caption("정상:불량 비율이 약 8:2로 불균형한 데이터입니다.")

    with st.expander("데이터 미리보기"):
        st.dataframe(df.head(10))

    fig_dist, ax_dist = plt.subplots(figsize=(3, 2.2))
    y.value_counts().sort_index().plot(kind="bar", ax=ax_dist, color=["#1f77b4", "#d62728"])
    ax_dist.set_xticklabels(["Normal(0)", "Defect(1)"], rotation=0, fontsize=8)
    ax_dist.set_title("Class Distribution", fontsize=9)
    ax_dist.set_ylabel("Count", fontsize=8)
    ax_dist.tick_params(axis="y", labelsize=7)
    fig_dist.tight_layout()

    dist_col, _ = st.columns([1, 3])  # 왼쪽 1/4 폭만 사용, 나머지는 빈 공간
    with dist_col:
        st.pyplot(fig_dist, use_container_width=False)

    st.divider()

    # ---------- 2. Logistic Regression ----------
    st.header("2. 분류모델 1 - Logistic Regression")

    log_model, log_proba = train_logistic_regression()

    log_threshold = st.slider(
        "불량(1) 판정 기준 threshold — 이 값 이상이면 불량으로 판정",
        min_value=0.05, max_value=0.95, value=0.50, step=0.05,
        key="log_threshold"
    )
    log_pred = (log_proba >= log_threshold).astype(int)

    show_metrics(y_test, log_pred, log_proba)
    st.caption(
        f"현재 threshold = {log_threshold:.2f} → "
        f"Recall {recall_score(y_test, log_pred):.3f} / Precision {precision_score(y_test, log_pred):.3f} "
        "(threshold를 낮출수록 Recall↑ Precision↓, 높일수록 반대)"
    )

    lc1, lc2, lc3 = st.columns(3)
    with lc1:
        st.pyplot(plot_confusion_matrix(y_test, log_pred, f"Logistic Regression (th={log_threshold:.2f})"))
    with lc2:
        st.pyplot(plot_roc_curve(y_test, log_proba, "Logistic Regression"))
    with lc3:
        st.pyplot(plot_feature_importance(log_model, "Logistic Regression"))

    st.divider()

    # ---------- 3. Random Forest ----------
    st.header("3. 분류모델 2 - Random Forest")
    st.caption(
        "클래스 불균형(정상 80% : 불량 20%) 때문에 기본 threshold(0.5)에서는 "
        "불량 확률이 대부분 0.5를 못 넘어 전부 정상으로만 예측되는 문제가 있습니다. "
        "아래 슬라이더로 판정 기준(threshold)을 직접 낮춰보며 recall/precision이 어떻게 바뀌는지 확인해보세요."
    )

    rf_model, rf_proba = train_random_forest()

    rf_threshold = st.slider(
        "불량(1) 판정 기준 threshold — 이 값 이상이면 불량으로 판정",
        min_value=0.05, max_value=0.95, value=0.30, step=0.05,
        key="rf_threshold"
    )
    rf_pred = (rf_proba >= rf_threshold).astype(int)

    show_metrics(y_test, rf_pred, rf_proba)
    st.caption(
        f"현재 threshold = {rf_threshold:.2f} → "
        f"Recall {recall_score(y_test, rf_pred):.3f} / Precision {precision_score(y_test, rf_pred):.3f} "
        "(threshold를 낮출수록 Recall↑ Precision↓, 높일수록 반대)"
    )

    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        st.pyplot(plot_confusion_matrix(y_test, rf_pred, f"Random Forest (th={rf_threshold:.2f})"))
    with rc2:
        st.pyplot(plot_roc_curve(y_test, rf_proba, "Random Forest"))
    with rc3:
        st.pyplot(plot_feature_importance(rf_model, "Random Forest"))

    st.divider()

    # ---------- 4. 결론 ----------
    st.header("4. 결론")

    auc_log = roc_auc_score(y_test, log_proba)
    auc_rf = roc_auc_score(y_test, rf_proba)

    st.markdown(f"""
- **Logistic Regression**: AUC {auc_log:.3f}, Recall {recall_score(y_test, log_pred):.3f} (threshold={log_threshold:.2f}, 위 슬라이더 값)
- **Random Forest**: AUC {auc_rf:.3f}, Recall {recall_score(y_test, rf_pred):.3f} (threshold={rf_threshold:.2f}, 위 슬라이더 값)

두 모델의 AUC 차이가 크지 않습니다(약 {abs(auc_rf-auc_log):.3f} 차이).
모델을 더 복잡한 것으로 바꿔도 성능이 극적으로 개선되지 않는 것으로 보아,
현재 성능의 병목은 모델 종류보다 **불량(1) 데이터 수 자체가 적은(약 20%) 클래스 불균형**에
있는 것으로 판단됩니다. 두 모델 모두 threshold(판정 기준)를 낮출수록 recall이 오르고
precision이 떨어지는 트레이드오프를 보이며, 이는 AUC로 대표되는 모델의 잠재력과
실제 판정 결과(recall/precision)가 서로 다른 것임을 보여줍니다.
""")



    st.caption("Feature Importance 상 resin_moisture_pct(수지 수분율), "
               "injection_pressure_mpa(사출 압력) 등이 두 모델 모두에서 상위권으로 나타났습니다.")


# ---------------------------------------------------------
# tab3: 추후 추가될 파트 (미리 비워둠)
# ---------------------------------------------------------
# with tab3:
#     st.header("추가 예정 파트")
#     st.info("여기에 새로운 내용을 추가할 예정입니다.")