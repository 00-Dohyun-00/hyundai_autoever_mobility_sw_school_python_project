사전 검색 기능

Flask + Jinja2 기반 웹 화면에서 사용자가 검색 방식을 선택한 뒤 단어를 검색하고, 검색 결과의 뜻과 출처를 확인할 수 있는 기능입니다.

기존 Selenium 기반 네이버 국어사전 동적 크롤링 기능을 유지하면서, 배포 환경에서도 사용할 수 있도록 국립국어원 언어정보나눔터 · 온용어 Open API 검색 방식을 추가했습니다.

검색 방식은 서로 다르지만 최근 검색어와 메모는 공통으로 공유합니다.

<details>
<summary><strong>요약보기</strong></summary>

주요 기능

네이버 국어사전 Selenium 동적 크롤링

국립국어원 언어정보나눔터 · 온용어 Open API 검색

검색 방식 선택 화면

검색 방식에 따른 제목 / 설명 / 출처 자동 변경

검색 결과 뜻 자동 추출

입력 검색어와 실제 결과 단어 비교

검색 결과가 없는 경우 NO_RESULTS 안내

뜻별 결과 카드 표시

검색 중 로딩 화면

오류 유형별 안내 및 유지보수 로그

최근 검색어 최대 5개 관리

Selenium / API 간 최근 검색어 공유

검색 결과 메모 및 중복 저장 방지

Selenium / API 간 메모 공유

메모별 데이터 출처 저장

전체 뜻 한 번에 메모

메모 개별 / 전체 삭제

메모 TXT 파일 저장

사용 기술

Backend

Python

Flask

Jinja2

Crawling

Selenium

Chrome

ChromeDriver

Open API

국립국어원 언어정보나눔터 · 온용어 Open API

Python urllib

python-dotenv

Environment Variables

Frontend

HTML

CSS

JavaScript

sessionStorage

주요 파일

crawler/
├─ __init__.py
└─ crawler.py

templates/
└─ crawl_result.html

파일

역할

crawler/crawler.py

Selenium 검색, Open API 검색, 결과 파싱, 오류 처리

templates/crawl_result.html

검색 방식 선택, 검색창, 결과 카드, 로딩, 오류, 최근 검색어, 메모 UI

전체 검색 구조

/crawl-result
      ↓
검색 방식 선택
      ↓
┌──────────────────────┬──────────────────────────┐
│ 네이버 국어사전      │ 언어정보나눔터 · 온용어 │
│ Selenium             │ Open API                 │
└──────────┬───────────┴─────────────┬────────────┘
           ↓                         ↓
source=naver                    source=kli
           ↓                         ↓
Chrome 실행                    API 요청
           ↓                         ↓
동적 크롤링                    JSON 응답 파싱
           └─────────────┬───────────┘
                         ↓
                    결과 화면 출력
                         ↓
             최근 검색어 / 메모 공유

검색 URL

검색 방식 선택:

/crawl-result

네이버 Selenium 검색:

/crawl-result?source=naver

온용어 Open API 검색:

/crawl-result?source=kli

검색어가 포함되면:

/crawl-result?source=naver&keyword=사출

/crawl-result?source=kli&keyword=사출

최근 검색어와 메모 공유

두 검색 방식은 동일한 sessionStorage Key를 사용합니다.

const RECENT_SEARCH_KEY = "crawl_recent_searches";
const MEMO_KEY = "crawl_dictionary_memos";

따라서 네이버 Selenium에서 검색하거나 메모한 내용은 온용어 API 검색 화면에서도 그대로 사용할 수 있습니다.

단, sessionStorage를 사용하므로 현재 브라우저 세션이 종료되면 초기화됩니다.

환경 변수

온용어 Open API를 사용하려면 프로젝트 루트에 .env 파일을 생성합니다.

KLI_API_KEY="발급받은_API_KEY"

.env는 GitHub에 올라가지 않도록 .gitignore에서 제외합니다.

.env

배포 환경에서는 .env 파일 대신 Vercel의 Environment Variables에 같은 이름으로 등록합니다.

KLI_API_KEY

실행 방법

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py

브라우저에서:

http://localhost:5000/crawl-result

</details>

<details>
<summary><strong>자세히 보기</strong></summary>

1. 기능 개요

기존 기능은 Selenium을 이용해 네이버 국어사전의 실제 검색 화면을 자동으로 조작하고 결과의 뜻을 가져오는 구조였습니다.

로컬 환경에서는 정상 작동했지만 배포 환경에서는 Chrome / WebDriver 실행 환경에 영향을 받을 수 있기 때문에, 기존 Selenium 기능을 제거하지 않고 별도의 Open API 검색 방식을 추가했습니다.

현재 구조는 다음 두 가지 검색 방식을 제공합니다.

네이버 국어사전

Selenium
→ Chrome 실행
→ 네이버 국어사전 접속
→ 검색어 입력
→ 동적 검색 결과 로딩
→ 뜻 및 실제 결과 단어 추출

언어정보나눔터 · 온용어

Open API
→ 검색어 전달
→ JSON 응답 수신
→ 결과 파싱
→ 용어 / 뜻 / 출처 추출

2. 검색 방식 선택

사용자가 /crawl-result에 처음 접속하면 바로 검색을 실행하지 않고 검색 방법을 선택합니다.

[ 네이버 국어사전 ]
Selenium 동적 크롤링
[ 크롤링 검색 창으로 이동 ]

[ 언어정보나눔터 · 온용어 ]
Open API
[ API 검색 창으로 이동 ]

검색 방식을 선택하면 같은 crawl_result.html 안에서 선택한 방식에 맞게 제목, 설명, 검색 출처와 실행 로직이 변경됩니다.

3. 검색 모드 구분

검색 방식은 URL의 source Query Parameter를 사용하여 구분합니다.

source=naver
source=kli

예:

/crawl-result?source=naver&keyword=사출

/crawl-result?source=kli&keyword=사출

crawler.py에서는 source 값에 따라 실제 검색 함수를 분기합니다.

if source == "naver":
    return get_naver_results(keyword)

if source == "kli":
    return get_kli_results(keyword)

4. Selenium 검색

Chrome Driver

네이버 검색은 Selenium의 Chrome WebDriver를 사용합니다.

driver = webdriver.Chrome(
    options=options
)

기본적으로 Headless 모드를 사용합니다.

options.add_argument(
    "--headless=new"
)

네이버 국어사전 접속

NAVER_DICT_URL = "https://ko.dict.naver.com/#/main"

검색 입력창은 XPath를 기준으로 확인합니다.

SEARCH_XPATH = '//*[@id="ac_input"]'

검색어를 입력하고 ENTER를 전달합니다.

search_box.clear()
search_box.send_keys(keyword)
search_box.send_keys(Keys.ENTER)

검색 결과 대기

네이버 검색 결과는 동적으로 표시되므로 WebDriverWait을 사용합니다.

검색 결과가 표시되기 전에 DOM을 읽는 상황을 줄이고, 뜻 영역 또는 추가 결과 요소가 나타난 이후 다음 작업을 진행합니다.

5. Selenium 뜻 추출

뜻 영역은 다음 Selector를 사용합니다.

MEAN_SELECTOR = 'p.mean[lang="ko"]'

mean_elements = driver.find_elements(
    By.CSS_SELECTOR,
    MEAN_SELECTOR,
)

다음 항목은 제외합니다.

빈 텍스트

읽을 수 없는 요소

이미 추가된 동일한 뜻

최종 결과는 뜻 하나마다 별도의 결과 카드로 표시합니다.

6. 실제 결과 단어 확인

사용자가 입력한 검색어와 네이버가 실제 표시하는 결과 단어가 다를 수 있기 때문에 결과 단어를 별도로 읽습니다.

예:

입력 검색어: 사추
실제 결과: 사출

검색 결과 단어가 다르더라도 정상적으로 확보한 뜻은 삭제하지 않고 경고를 표시합니다.

검색어와 실제 검색 결과 단어가 다릅니다.

입력 검색어: 사추
네이버 국어사전 결과: 사출

실제 결과 단어를 읽지 못하더라도 뜻이 정상적으로 확보된 경우 입력 검색어를 제목으로 사용하고 검색 결과는 유지합니다.

7. 추가 검색 결과

추가 뜻이 존재하는 경우 네이버 국어사전의 단어 더보기 버튼을 확인합니다.

MORE_BUTTON_XPATH = '//*[@id="searchPage_word_more"]'

일반 클릭이 실패하면 JavaScript 클릭도 시도합니다.

driver.execute_script(
    "arguments[0].click();",
    more_button,
)

추가 결과가 로딩되면 뜻 목록을 다시 읽어 최종 결과에 포함합니다.

8. 온용어 Open API

Open API 검색은 Chrome이나 Selenium을 실행하지 않고 API 서버에 직접 요청합니다.

환경 변수에서 API Key를 읽습니다.

api_key = os.getenv(
    "KLI_API_KEY",
    "",
).strip()

검색 요청에는 검색어와 API Key를 전달합니다.

params = {
    "key": api_key,
    "apiSearchWord": keyword,
    "start": "1",
    "num": "100",
    "sort": "wt",
}

API 응답에서는 검색 결과의 용어, 정의와 출처 정보를 파싱해 화면에 전달합니다.

9. 검색 결과 없음 처리

검색 결과가 존재하지 않는 상황은 시스템 오류와 구분합니다.

기존처럼 모든 예외를 UNEXPECTED_ERROR로 처리하지 않고, 실제 검색 결과가 없으면 별도의 NO_RESULTS 오류를 반환합니다.

NO_RESULTS

검색 결과 없음

'검색어'에 대한 검색 결과를 찾지 못했습니다.

확인해볼 내용
검색어의 철자와 띄어쓰기를 확인하거나
다른 단어로 검색해주세요.

이렇게 하면 사용자는 시스템 장애와 단순 검색 결과 없음을 구분할 수 있습니다.

10. 데이터 출처 표시

검색 방식에 따라 화면의 출처가 변경됩니다.

Selenium

출처 · 네이버 국어사전
방식 · Selenium 동적 크롤링

Open API

출처 · 국립국어원 언어정보나눔터 · 온용어
방식 · Open API

Open API 결과에 세부 출처 정보가 포함된 경우 각 뜻 결과에도 해당 정보를 표시합니다.

메모에도 실제 검색 결과의 출처를 함께 저장합니다.

11. 검색 중 로딩 화면

검색 요청을 시작하면 로딩 화면을 표시합니다.

적용되는 상태:

Spinner 표시

검색 버튼 비활성화

버튼 문구를 검색 중...으로 변경

현재 선택한 검색 방식 표시

Selenium 검색과 Open API 검색 모두 같은 UI 구조를 사용하지만 로딩 안내 문구는 현재 검색 방식에 맞게 변경됩니다.

12. 최근 검색어

최근 검색어는 JavaScript의 sessionStorage에 최대 5개까지 저장합니다.

지원 기능:

최근 검색어 최대 5개

동일 검색어 중복 방지

다시 검색한 단어를 가장 앞으로 이동

최근 검색어 클릭 시 재검색

개별 삭제

전체 삭제

두 검색 방식은 동일한 Key를 사용합니다.

const RECENT_SEARCH_KEY =
    "crawl_recent_searches";

따라서 예를 들어 Selenium에서 자동차를 검색한 뒤 Open API 검색 화면으로 이동해도 최근 검색어에 자동차가 그대로 표시됩니다.

13. 공유 메모장

검색 결과 중 필요한 뜻을 메모에 추가할 수 있습니다.

저장 정보:

검색 결과 단어

뜻

출처

저장 시간

두 검색 방식은 동일한 메모 Key를 사용합니다.

const MEMO_KEY =
    "crawl_dictionary_memos";

따라서 Selenium과 Open API에서 추가한 메모를 하나의 메모장에서 함께 관리합니다.

예:

자동차

뜻: ...
출처: 네이버 국어사전 · Selenium 동적 크롤링

인공지능

뜻: ...
출처: 국립국어원 언어정보나눔터 · 온용어

검색 방식은 분리되어 있지만 사용자의 메모 데이터는 하나로 연결됩니다.

14. 중복 메모 방지

같은 검색 결과를 반복해서 저장하는 것을 막기 위해 중복 여부를 확인합니다.

현재 메모에는 출처 정보도 포함되므로 단어, 뜻과 출처를 기준으로 동일한 메모인지 판단할 수 있습니다.

단어
+
뜻
+
출처
    ↓
중복 확인
    ↓
이미 존재하면 추가하지 않음

15. 모든 뜻 메모 추가

현재 검색 결과에 표시된 뜻 전체를 한 번에 메모에 추가할 수 있습니다.

모든 뜻 메모에 추가

이미 저장된 항목은 다시 저장하지 않고 새로운 결과만 추가합니다.

16. 메모 삭제 및 초기화

각 메모는 개별 삭제가 가능합니다.

×

전체 메모를 삭제하려면:

메모 초기화

기능을 사용할 수 있습니다.

전체 삭제 전에는 확인창을 표시하여 실수로 데이터를 삭제하는 상황을 줄입니다.

17. 메모 TXT 저장

현재 메모 내용을 TXT 파일로 저장할 수 있습니다.

TXT에는 단어, 뜻, 실제 검색 출처와 저장 시간이 포함됩니다.

예:

사전 검색 공유 메모
========================================

1. 자동차
뜻: ...
출처: 네이버 국어사전 · Selenium 동적 크롤링
저장일시: ...
----------------------------------------

2. 인공지능
뜻: ...
출처: 국립국어원 언어정보나눔터 · 온용어
저장일시: ...
----------------------------------------

별도의 Flask 저장 Route를 사용하지 않고 브라우저에 저장된 데이터를 이용해 파일을 생성합니다.

18. 오류 처리

Selenium과 Open API는 서로 다른 외부 환경에 의존하기 때문에 오류 원인을 구분하여 처리합니다.

Selenium 관련 오류

오류 코드

설명

EMPTY_KEYWORD

검색어가 입력되지 않은 경우

DRIVER_START_FAILED

Chrome 실행 실패

SITE_CONNECTION_FAILED

네이버 국어사전 접속 실패

SEARCH_BOX_NOT_FOUND

검색 입력창 탐색 실패

SEARCH_INPUT_FAILED

검색 실행 실패

ACCESS_BLOCKED

자동화 접근 제한

NO_RESULTS

검색 결과 없음

RESULT_LOAD_TIMEOUT

검색 결과 로딩 시간 초과

DOM_READ_FAILED

검색 결과 HTML 요소 읽기 실패

MEANING_NOT_FOUND

뜻 영역을 찾지 못함

BROWSER_COMMUNICATION_FAILED

Selenium과 Chrome 통신 오류

UNEXPECTED_ERROR

분류되지 않은 기타 예외

Open API 관련 오류

Open API에서는 다음과 같은 상황을 별도로 처리합니다.

API Key 누락

API 인증 오류

HTTP 요청 실패

네트워크 연결 실패

잘못된 API 응답

검색 결과 없음

분류되지 않은 기타 예외

사용자 화면에는 오류 코드와 해결 방향을 표시하고, 기술적인 상세 정보는 서버 로그를 통해 확인할 수 있도록 구성합니다.

19. 부분 실패 처리

부가 기능에서 문제가 발생했더라도 이미 정상적인 검색 결과를 확보했다면 전체 검색을 실패로 처리하지 않습니다.

예:

실제 결과 단어 확인 실패

단어 더보기 클릭 실패

추가 결과 로딩 시간 초과

검색 결과 확보
    +
부가 기능 일부 실패
    ↓
검색 결과 유지
    +
경고 표시

20. 결과 데이터 구조

두 검색 방식은 화면에서 동일하게 처리할 수 있도록 최대한 공통된 결과 형태를 사용합니다.

예:

{
    "status": "ok",
    "input_keyword": "사출",
    "title": "사출",
    "url": "검색 결과 또는 출처 URL",
    "meanings": [
        "첫 번째 뜻",
        "두 번째 뜻"
    ],
    "count": 2,
    "word_detected": True,
    "mismatch": False,
    "warnings": [],
    "source_name": "검색 출처",
    "source_method": "검색 방식"
}

오류 데이터:

{
    "status": "error",
    "error": {
        "code": "NO_RESULTS",
        "title": "검색 결과 없음",
        "message": "'검색어'에 대한 검색 결과를 찾지 못했습니다.",
        "hint": "다른 단어로 검색해주세요."
    }
}

21. 환경 변수 설정

로컬

프로젝트 루트에 .env 파일을 생성합니다.

KLI_API_KEY="발급받은_API_KEY"

.env 파일은 Git에 포함하지 않습니다.

.gitignore

.env

Vercel

Vercel 프로젝트의 Environment Variables에 다음 값을 등록합니다.

Name
KLI_API_KEY

Value
발급받은 실제 API Key

Production 환경에 적용한 뒤 새로운 Deployment에 환경 변수가 반영되도록 재배포합니다.

22. 실행 방법

가상환경 생성

python -m venv .venv

가상환경 활성화

Windows:

.venv\Scripts\activate

패키지 설치

pip install -r requirements.txt

Flask 실행

python app.py

검색 화면

http://localhost:5000/crawl-result

23. 사용 방법

/crawl-result 화면에 접속합니다.

네이버 Selenium 또는 온용어 Open API 중 검색 방식을 선택합니다.

검색창에 단어를 입력합니다.

검색 버튼을 클릭합니다.

검색 중에는 로딩 화면이 표시됩니다.

선택한 검색 방식으로 결과를 가져옵니다.

뜻별 결과 카드와 데이터 출처를 확인합니다.

필요한 결과를 메모에 추가합니다.

다른 검색 방식으로 이동해도 최근 검색어와 메모가 유지됩니다.

필요한 메모는 TXT 파일로 저장할 수 있습니다.

24. 구현 시 주의사항

Selenium

Selenium 검색은 Chrome과 WebDriver 실행 환경에 영향을 받습니다.

로컬에서 정상 작동하더라도 배포 플랫폼의 실행 환경에 따라 Chrome 구동이 제한될 수 있습니다.

네이버 페이지 구조

Selenium 검색은 네이버 국어사전의 HTML 구조에 의존합니다.

SEARCH_XPATH = '//*[@id="ac_input"]'
MORE_BUTTON_XPATH = '//*[@id="searchPage_word_more"]'
MEAN_SELECTOR = 'p.mean[lang="ko"]'

네이버가 HTML 구조를 변경하면 Selector 수정이 필요할 수 있습니다.

자동화 접근 제한

짧은 시간에 지나치게 많은 검색 요청을 보내면 자동화 접근 제한이 발생할 수 있습니다.

Open API

API 검색을 사용하려면 유효한 KLI_API_KEY가 필요합니다.

API Key를 Python 코드에 직접 작성하거나 GitHub에 업로드하지 않습니다.

최근 검색어와 메모

최근 검색어와 메모는 sessionStorage를 사용하므로 브라우저 세션 종료 시 삭제됩니다.

필요한 메모는 TXT 파일로 별도 저장합니다.

전체 흐름

flowchart TD

    A["/crawl-result 접속"]
    --> B{"검색 방식 선택"}

    B -- "네이버" --> C["source=naver"]
    B -- "온용어 API" --> D["source=kli"]

    C --> E["Selenium / Chrome 실행"]
    E --> F["네이버 국어사전 검색"]
    F --> G["뜻 / 실제 결과 단어 추출"]

    D --> H["Open API 요청"]
    H --> I["JSON 응답 파싱"]
    I --> J["용어 / 뜻 / 출처 추출"]

    G --> K["공통 결과 구조"]
    J --> K

    K --> L["Jinja2 결과 화면"]

    L --> M["최근 검색어"]
    L --> N["공유 메모장"]

    M --> O["sessionStorage"]
    N --> O

    N --> P["TXT 파일 저장"]

요약

현재 사전 검색 기능은 기존 Selenium 크롤링 기능을 유지하면서 Open API 검색 기능을 함께 사용할 수 있도록 구성했습니다.

검색 방식 선택
        ↓
┌─────────────────┬─────────────────────┐
│ Selenium        │ Open API            │
│ 네이버 국어사전 │ 언어정보나눔터      │
└────────┬────────┴──────────┬──────────┘
         ↓                   ↓
     동적 크롤링          API 요청
         ↓                   ↓
         └────────┬──────────┘
                  ↓
             검색 결과
                  ↓
          출처 정보 표시
                  ↓
      최근 검색어 / 공유 메모
                  ↓
              TXT 저장

검색 기술은 서로 독립적으로 유지하면서 최근 검색어와 메모는 하나의 사용자 작업 흐름으로 연결했습니다.

</details>

실행 방법

python -m venv .venv          # 최초 1회
.venv\Scripts\activate
pip install -r requirements.txt
python app.py

브라우저에서:

http://localhost:5000/crawl-result

로 접속한 뒤 사용할 검색 방식을 선택합니다.
