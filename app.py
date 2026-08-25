from flask import Flask, render_template, request

from analysis.analyzer import analyze_csv
from crawler.crawler import get_crawl_results

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/csv-analysis", methods=["GET", "POST"])
def csv_analysis():
    result = None
    error = None

    if request.method == "POST":
        file = request.files.get("csv_file")
        if file is None or file.filename == "":
            error = "CSV 파일을 선택해주세요."
        else:
            result = analyze_csv(file)

    return render_template("csv_analysis.html", result=result, error=error)


@app.route("/crawl-result")
def crawl_result():
    results = get_crawl_results()
    return render_template("crawl_result.html", results=results)


if __name__ == "__main__":
    app.run(debug=True)
