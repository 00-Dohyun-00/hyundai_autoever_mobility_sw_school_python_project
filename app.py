from pathlib import Path

from flask import Flask, render_template

from analysis.analyzer import analyze_default_csv
from crawler.crawler import get_crawl_results

app = Flask(__name__)

DEFAULT_CSV_PATH = Path(__file__).parent / "data" / "hyundai_autoever_injection_defect_classification_v2.csv"


@app.route("/")
def home():
    return render_template("csv_analysis.html", csv_name=DEFAULT_CSV_PATH.name)


@app.route("/analysis-content")
def analysis_content():
    result = analyze_default_csv(DEFAULT_CSV_PATH)
    return render_template("_analysis_result.html", result=result)



# ============================================================
# 크롤링 검색 / 결과 페이지
#
# 예:
# /crawl-result
# /crawl-result?keyword=사출
# /crawl-result?keyword=금형
# ============================================================

@app.route("/crawl-result")
def crawl_result():

    # --------------------------------------------------------
    # URL에서 keyword 받기
    # --------------------------------------------------------

    keyword = request.args.get(
        "keyword",
        ""
    ).strip()


    # --------------------------------------------------------
    # 기본값
    # --------------------------------------------------------

    results = []
    searched = False


    # --------------------------------------------------------
    # 검색어가 있으면 실제 크롤링 실행
    # --------------------------------------------------------

    if keyword:

        searched = True

        print(
            f"[Flask] 검색 시작: {keyword}"
        )

        results = get_crawl_results(
            keyword
        )

        print(
            f"[Flask] 검색 완료: {len(results)}개"
        )


    # --------------------------------------------------------
    # Jinja2로 전달
    # --------------------------------------------------------

    return render_template(
        "crawl_result.html",
        results=results,
        keyword=keyword,
        searched=searched
    )


if __name__ == "__main__":
    app.run(debug=True)
