# 사출 데이터 대시보드

Flask + Jinja2 기반 웹 UI로, 사출 CSV 데이터 분석과 관련 웹 크롤링 결과를 확인합니다.

- `pages/`가 아닌 `templates/`에 화면(HTML)을 두고, Jinja2로 파이썬 데이터를 렌더링합니다.
- 분석/크롤링 로직은 `analysis/analyzer.py`, `crawler/crawler.py`에 작성합니다.

## 실행 방법

```
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

브라우저에서 http://localhost:5000 접속.
