import joblib
import pandas as pd

from analysis.defect_classification import (
    DEFAULTS_PATH,
    LOG_THRESHOLD,
    MODEL_FILENAMES,
    MODELS_DIR,
    RF_THRESHOLD,
    analyze_defect_classification,
)

def analyze_default_csv(path):
    """data/ 폴더의 사출 불량 예측 CSV를 분석해 템플릿에서 쓸 결과 dict를 반환한다."""
    df = pd.read_csv(path)
    return analyze_defect_classification(df)


def predict_defect(model_name, input_values):
    """모델 예측 탭에서 호출. input_values는 폼에서 받은 10개 필드의 문자열 딕셔너리.
    나머지 피처는 학습 데이터 평균/최빈값으로 채워서 예측한다."""
    if model_name not in MODEL_FILENAMES:
        raise ValueError(f"알 수 없는 모델: {model_name}")

    model = joblib.load(MODELS_DIR / MODEL_FILENAMES[model_name])
    defaults = joblib.load(DEFAULTS_PATH)

    row = dict(defaults["values"])  # 기본값으로 전체 채운 뒤
    for key, raw in input_values.items():
        if raw == "" or raw is None:
            continue
        if key in defaults["numeric_cols"]:
            row[key] = float(raw)
        elif key in defaults["categorical_cols"]:
            row[key] = raw

    all_cols = defaults["numeric_cols"] + defaults["categorical_cols"]
    X_input = pd.DataFrame([{c: row[c] for c in all_cols}])

    proba = float(model.predict_proba(X_input)[:, 1][0])
    threshold = LOG_THRESHOLD if model_name == "Logistic Regression" else RF_THRESHOLD
    defect_label = int(proba >= threshold)

    return {
        "model_name": model_name,
        "inputs": input_values,  # 사용자가 실제로 입력한 10개만 결과표에 표시
        "probability": proba,
        "defect_label": defect_label,
    }