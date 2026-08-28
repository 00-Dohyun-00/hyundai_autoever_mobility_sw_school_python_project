import html
import json
import os
import re
import unicodedata

from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import os

from dotenv import load_dotenv

load_dotenv()

# ============================================================
# 국립국어원 언어정보나눔터 - 온용어 Open API
# ============================================================

OPEN_API_URL = "https://kli.korean.go.kr/term/api/search.do"

OPEN_API_KEY_ENV = "KLI_API_KEY"

OPEN_API_TIMEOUT = 10


# ============================================================
# 오류 클래스
# ============================================================

class CrawlerError(Exception):

    def __init__(
        self,
        code,
        title,
        message,
        hint,
        technical_detail="",
    ):
        super().__init__(message)

        self.code = code
        self.title = title
        self.message = message
        self.hint = hint
        self.technical_detail = technical_detail


# ============================================================
# 오류 결과 생성
# ============================================================

def make_error_result(error):

    return [
        {
            "status": "error",

            "error": {
                "code": error.code,
                "title": error.title,
                "message": error.message,
                "hint": error.hint,
            },
        }
    ]


# ============================================================
# Flask에서 검색어 가져오기
# ============================================================

def get_keyword_from_flask():

    try:
        from flask import request

        keyword = request.args.get(
            "keyword",
            "",
        )

        if keyword is None:
            return ""

        return keyword.strip()

    except RuntimeError:
        return ""

    except Exception:
        return ""


# ============================================================
# 문자열 비교용 정규화
# ============================================================

def normalize_for_compare(text):

    if text is None:
        return ""

    text = unicodedata.normalize(
        "NFKC",
        str(text),
    )

    text = "".join(
        text.split()
    )

    text = text.replace(
        "^",
        "",
    )

    return text.casefold()


# ============================================================
# API HTML 태그 제거
# ============================================================

def clean_text(text):

    if text is None:
        return ""

    text = str(text)

    text = re.sub(
        r"<[^>]+>",
        "",
        text,
    )

    text = html.unescape(
        text
    )

    return text.strip()


# ============================================================
# 온용어 표제어 표시용 정리
#
# 예:
# 학술^용어
# → 학술 용어
# ============================================================

def clean_word(word):

    word = clean_text(
        word
    )

    return word.replace(
        "^",
        " ",
    ).strip()


# ============================================================
# 값이 dict일 수도 있고 list일 수도 있어서
# 항상 list 형태로 변환
# ============================================================

def as_list(value):

    if value is None:
        return []

    if isinstance(
        value,
        list,
    ):
        return value

    return [
        value
    ]


# ============================================================
# API 인증키
# ============================================================

def get_api_key():

    api_key = os.getenv(
        OPEN_API_KEY_ENV,
        "",
    ).strip()

    if not api_key:

        raise CrawlerError(
            code="API_KEY_MISSING",
            title="API 인증키 없음",
            message=(
                "언어정보나눔터 Open API 인증키가 "
                "설정되어 있지 않습니다."
            ),
            hint=(
                "KLI_API_KEY 환경 변수에 "
                "발급받은 인증키를 설정해주세요."
            ),
        )

    return api_key


# ============================================================
# 온용어 Open API 호출
# ============================================================

def request_dictionary_api(
    keyword,
):

    api_key = get_api_key()

    params = {
        "key": api_key,
        "apiSearchWord": keyword,
        "start": "1",
        "num": "100",
        "sort": "wt",
    }

    request_url = (
        OPEN_API_URL
        + "?"
        + urlencode(params)
    )

    request = Request(
        request_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "Hyundai-AutoEver-Dictionary-Project"
            )
        },
    )

    try:

        with urlopen(
            request,
            timeout=OPEN_API_TIMEOUT,
        ) as response:

            raw_data = response.read()

            text = raw_data.decode(
                "utf-8"
            )

    except HTTPError as e:

        raise CrawlerError(
            code="API_HTTP_ERROR",
            title="API 요청 실패",
            message=(
                "언어정보나눔터 API 요청 중 "
                "HTTP 오류가 발생했습니다."
            ),
            hint=(
                "잠시 후 다시 검색해주세요."
            ),
            technical_detail=str(e),
        ) from e

    except URLError as e:

        raise CrawlerError(
            code="API_CONNECTION_FAILED",
            title="API 연결 실패",
            message=(
                "언어정보나눔터 API 서버에 "
                "연결하지 못했습니다."
            ),
            hint=(
                "인터넷 연결 상태를 확인한 뒤 "
                "다시 시도해주세요."
            ),
            technical_detail=str(e),
        ) from e

    except TimeoutError as e:

        raise CrawlerError(
            code="API_TIMEOUT",
            title="API 응답 시간 초과",
            message=(
                "API 서버의 응답이 너무 늦어 "
                "검색을 완료하지 못했습니다."
            ),
            hint=(
                "잠시 후 다시 시도해주세요."
            ),
            technical_detail=str(e),
        ) from e

    try:

        return json.loads(
            text
        )

    except json.JSONDecodeError as e:

        raise CrawlerError(
            code="API_INVALID_RESPONSE",
            title="API 응답 오류",
            message=(
                "API에서 받은 데이터를 "
                "읽지 못했습니다."
            ),
            hint=(
                "잠시 후 다시 검색해주세요."
            ),
            technical_detail=str(e),
        ) from e


# ============================================================
# API 응답 오류 확인
# ============================================================

def check_api_error(
    data,
):

    channel = data.get(
        "channel",
        {},
    )

    return_objects = as_list(
        channel.get(
            "return_object"
        )
    )

    if not return_objects:
        return

    return_code = str(
        return_objects[0].get(
            "returnCode",
            "1",
        )
    )

    if return_code == "1":
        return

    error_messages = {
        "000": (
            "API 서버에서 시스템 오류가 발생했습니다."
        ),
        "020": (
            "등록되지 않은 API 인증키입니다."
        ),
        "021": (
            "현재 사용할 수 없는 API 인증키입니다."
        ),
        "022": (
            "Open API의 일일 사용 한도를 초과했습니다."
        ),
        "100": (
            "API 요청 형식이 올바르지 않습니다."
        ),
    }

    message = error_messages.get(
        return_code,
        (
            "Open API 요청 중 알 수 없는 "
            "오류가 발생했습니다."
        ),
    )

    raise CrawlerError(
        code=f"API_ERROR_{return_code}",
        title="Open API 오류",
        message=message,
        hint=(
            "인증키 상태와 API 사용 가능 여부를 "
            "확인해주세요."
        ),
    )


# ============================================================
# 검색 결과 추출
# ============================================================

def parse_dictionary_result(
    keyword,
    data,
):

    check_api_error(
        data
    )

    channel = data.get(
        "channel",
        {},
    )

    total = int(
        channel.get(
            "total",
            0,
        )
        or 0
    )

    if total <= 0:

        raise CrawlerError(
            code="NO_RESULTS",
            title="검색 결과 없음",
            message=(
                f"'{keyword}'에 대한 검색 결과를 "
                "찾지 못했습니다."
            ),
            hint=(
                "다른 검색어로 다시 검색해주세요."
            ),
        )

    items = []

    for return_object in as_list(
        channel.get(
            "return_object"
        )
    ):

        items.extend(
            as_list(
                return_object.get(
                    "resultlist"
                )
            )
        )

    if not items:

        raise CrawlerError(
            code="NO_RESULTS",
            title="검색 결과 없음",
            message=(
                f"'{keyword}'에 대한 검색 결과를 "
                "찾지 못했습니다."
            ),
            hint=(
                "다른 검색어로 다시 검색해주세요."
            ),
        )

    first_item = items[0]

    result_word = clean_word(
        first_item.get(
            "word",
            keyword,
        )
    )

    meanings = []

    for item in items:

        definition = clean_text(
            item.get(
                "definition",
                "",
            )
        )

        if (
            definition
            and
            definition not in meanings
        ):
            meanings.append(
                definition
            )

    if not meanings:

        raise CrawlerError(
            code="MEANING_NOT_FOUND",
            title="뜻풀이 없음",
            message=(
                "검색 결과는 존재하지만 "
                "표시할 뜻풀이가 없습니다."
            ),
            hint=(
                "다른 검색어로 다시 검색해주세요."
            ),
        )

    word_detected = bool(
        result_word
    )

    mismatch = (
        word_detected
        and
        normalize_for_compare(
            keyword
        )
        !=
        normalize_for_compare(
            result_word
        )
    )

    return {
        "status": "ok",

        "input_keyword": keyword,

        "title": (
            result_word
            if result_word
            else keyword
        ),

        "url": (
            "https://kli.korean.go.kr/term/"
        ),

        "meanings": meanings,

        "count": len(
            meanings
        ),

        "word_detected": word_detected,

        "mismatch": mismatch,

        "warnings": [],
    }


# ============================================================
# Jinja2 화면으로 전달할 최종 결과
# ============================================================

def get_crawl_results(
    keyword=None,
):

    if keyword is None:

        keyword = get_keyword_from_flask()

    keyword = str(
        keyword
    ).strip()

    if not keyword:
        return []

    try:

        print(
            "=========================================="
        )

        print(
            f"[Open API] 검색 시작: {keyword}"
        )

        data = request_dictionary_api(
            keyword
        )

        result = parse_dictionary_result(
            keyword,
            data,
        )

        print(
            f"[Open API] 입력 검색어: {keyword}"
        )

        print(
            f"[Open API] 실제 결과 단어: "
            f"{result['title']}"
        )

        print(
            f"[Open API] 검색 결과 개수: "
            f"{result['count']}"
        )

        print(
            "=========================================="
        )

        return [
            result
        ]

    except CrawlerError as e:

        print(
            "=========================================="
        )

        print(
            f"[Open API 오류 코드] {e.code}"
        )

        print(
            f"[Open API 오류] "
            f"{e.title}: {e.message}"
        )

        if e.technical_detail:

            print(
                f"[Open API 유지보수 로그] "
                f"{e.technical_detail}"
            )

        print(
            "=========================================="
        )

        return make_error_result(
            e
        )

    except Exception as e:

        print(
            "=========================================="
        )

        print(
            "[Open API 예상하지 못한 오류]",
            type(e).__name__,
            str(e),
        )

        print(
            "=========================================="
        )

        error = CrawlerError(
            code="UNEXPECTED_ERROR",
            title="예상하지 못한 오류",
            message=(
                "검색 처리 중 예상하지 못한 "
                "문제가 발생했습니다."
            ),
            hint=(
                "잠시 후 다시 검색해주세요."
            ),
            technical_detail=str(e),
        )

        return make_error_result(
            error
        )