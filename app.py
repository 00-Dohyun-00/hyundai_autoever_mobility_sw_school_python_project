from pathlib import Path

from flask import Flask, render_template, request

from analysis.analyzer import analyze_default_csv, predict_defect
from crawler.crawler import get_crawl_results

app = Flask(__name__)

DEFAULT_CSV_PATH = Path(__file__).parent / "data" / "hyundai_autoever_injection_defect_classification_v2.csv"

# 예측 화면의 입력 필드. label은 화면 표시용, name은 request.form 키로 쓰인다.
PREDICT_FEATURE_FIELDS = [
    {"name": "resin_moisture_pct", "label": "수지 수분율 (%)"},
    {"name": "mold_temp_c", "label": "금형 온도 (°C)"},
    {"name": "injection_pressure_mpa", "label": "사출 압력 (MPa)"},
    {"name": "holding_pressure_mpa", "label": "보압 (MPa)"},
    {"name": "injection_speed_mm_s", "label": "사출 속도 (mm/s)"},
    {"name": "fill_time_s", "label": "충전 시간 (s)"},
    {"name": "cooling_time_s", "label": "냉각 시간 (s)"},
    {"name": "screw_rpm", "label": "스크류 회전수 (rpm)"},
    {"name": "back_pressure_mpa", "label": "배압 (MPa)"},
    {"name": "clamping_force_kn", "label": "형체력 (kN)"},
]

# 선택 가능한 모델과, 가운데 패널에 보여줄 모델 종류/파라미터.
# defect_classification.py에서 실제로 학습에 쓰는 하이퍼파라미터와 맞춰뒀다.
PREDICT_MODEL_INFO = {
    "Logistic Regression": {
        "type": "LogisticRegression",
        "params": {"max_iter": 1000, "class_weight": "balanced"},
    },
    "Random Forest": {
        "type": "RandomForestClassifier",
        "params": {
            "n_estimators": 300,
            "class_weight": "balanced_subsample",
            "random_state": 42,
        },
    },
}


@app.route("/")
def home():
    return render_template("csv_analysis.html", csv_name=DEFAULT_CSV_PATH.name)


@app.route("/analysis-content")
def analysis_content():
    result = analyze_default_csv(DEFAULT_CSV_PATH)
    return render_template("_analysis_result.html", result=result)


@app.route("/model", methods=["GET", "POST"])
def model_predict():
    model_options = list(PREDICT_MODEL_INFO.keys())
    selected_model = request.form.get("model_name", model_options[0])
    if selected_model not in PREDICT_MODEL_INFO:
        selected_model = model_options[0]
    prediction = None
    if request.method == "POST":
        input_values = {
            field["name"]: request.form.get(field["name"], "")
            for field in PREDICT_FEATURE_FIELDS
        }
        try:
            prediction = predict_defect(selected_model, input_values)
        except FileNotFoundError:
            # 아직 홈 화면에서 분석(학습)이 한 번도 실행되지 않은 경우
            prediction = None
    return render_template(
        "model.html",
        model_options=model_options,
        model_info=PREDICT_MODEL_INFO,
        selected_model=selected_model,
        feature_fields=PREDICT_FEATURE_FIELDS,
        prediction=prediction,
    )

@app.route("/crawl-result")
def crawl_result():
    results = get_crawl_results()
    return render_template("crawl_result.html", results=results)


if __name__ == "__main__":
    app.run(debug=True)
