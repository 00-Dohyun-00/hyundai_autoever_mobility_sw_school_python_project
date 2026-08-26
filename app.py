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


@app.route("/crawl-result")
def crawl_result():
    results = get_crawl_results()
    return render_template("crawl_result.html", results=results)


if __name__ == "__main__":
    app.run(debug=True)
