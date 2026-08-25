import pandas as pd


def analyze_csv(file):
    """업로드된 CSV 파일을 분석해서 결과를 dict로 반환한다.

    Args:
        file: Flask가 전달하는 업로드 파일 객체 (request.files["csv_file"])

    Returns:
        템플릿에서 사용할 분석 결과 dict.
    """
    df = pd.read_csv(file)

    return {
        "columns": list(df.columns),
        "row_count": len(df),
        "preview": df.head(10).to_dict(orient="records"),
    }
