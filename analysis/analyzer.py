import pandas as pd

from analysis.defect_classification import analyze_defect_classification


def analyze_default_csv(path):
    """data/ 폴더의 사출 불량 예측 CSV를 분석해 템플릿에서 쓸 결과 dict를 반환한다."""
    df = pd.read_csv(path)
    return analyze_defect_classification(df)
