import html
import json
import os
import re
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


load_dotenv()


# ============================================================
# 검색 방식
# ============================================================

SOURCE_NAVER = "naver"
SOURCE_KLI = "kli"
DEFAULT_SOURCE = SOURCE_KLI


# ============================================================
# 네이버 국어사전 Selenium 설정
# ============================================================

NAVER_DICT_URL = "https://ko.dict.naver.com/#/main"
SEARCH_XPATH = '//*[@id="ac_input"]'
MORE_BUTTON_XPATH = '//*[@id="searchPage_word_more"]'
MEAN_SELECTOR = 'p.mean[lang="ko"]'


# ============================================================
# 국립국어원 언어정보나눔터 · 온용어 Open API 설정
# ============================================================

KLI_API_URL = "https://kli.korean.go.kr/term/api/search.do"
KLI_HOME_URL = "https://kli.korean.go.kr/term/"
KLI_API_KEY_ENV = "KLI_API_KEY"
KLI_API_TIMEOUT = 10


# ============================================================
# 공통 오류 클래스
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
# 공통 유틸리티
# ============================================================

def make_warning(code, message):
    return {
        "code": code,
        "message": message,
    }


def make_error_result(error, source_mode=None):
    return [
        {
            "status": "error",
            "source_mode": source_mode or DEFAULT_SOURCE,
            "error": {
                "code": error.code,
                "title": error.title,
                "message": error.message,
                "hint": error.hint,
            },
        }
    ]


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

    # 온용어 표제어의 단어 경계 표시(^)는 비교에서 제외
    text = text.replace("^", "")

    return text.casefold()


def clean_text(text):
    if text is None:
        return ""

    text = str(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)

    return text.strip()


def clean_kli_word(word):
    return clean_text(word).replace("^", " ").strip()


def as_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


# ============================================================
# Flask request 값 읽기
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


def normalize_source(source):
    source = str(source or "").strip().lower()

    if source == SOURCE_NAVER:
        return SOURCE_NAVER

    if source == SOURCE_KLI:
        return SOURCE_KLI

    return DEFAULT_SOURCE


def get_source_from_flask():
    """
    /crawl-result 에 source가 없으면 검색 방식을 아직
    선택하지 않은 상태로 처리합니다.

    source=naver -> Selenium
    source=kli   -> Open API
    """
    try:
        from flask import request

        source = str(
            request.args.get(
                "source",
                "",
            )
            or ""
        ).strip().lower()

        if source in (
            SOURCE_NAVER,
            SOURCE_KLI,
        ):
            return source

        return ""

    except RuntimeError:
        return ""

    except Exception:
        return ""


# ============================================================
# 네이버 Selenium - Chrome Driver 생성
# ============================================================

def create_driver():
    try:
        options = webdriver.ChromeOptions()

        options.add_argument("--headless=new")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        driver = webdriver.Chrome(
            options=options
        )

        return driver

    except WebDriverException as e:
        raise CrawlerError(
            code="DRIVER_START_FAILED",
            title="Chrome 실행 실패",
            message=(
                "네이버 국어사전 동적 크롤링에 사용할 "
                "Chrome 브라우저를 실행하지 못했습니다."
            ),
            hint=(
                "Chrome 설치 상태와 Selenium 실행 환경을 "
                "확인해주세요. 배포 환경에서는 이 방식이 "
                "지원되지 않을 수 있습니다."
            ),
            technical_detail=str(e),
        ) from e


def close_driver(driver):
    if driver is None:
        return

    try:
        driver.quit()
    except Exception:
        pass


def safe_page_source(driver):
    try:
        return driver.page_source or ""
    except Exception:
        return ""


def is_access_blocked(driver):
    source = safe_page_source(driver).lower()

    blocked_signals = [
        "captcha",
        "비정상적인 접근",
        "접근이 제한",
        "자동입력 방지",
        "자동 입력 방지",
        "로봇이 아닙니다",
        "too many requests",
    ]

    return any(
        signal.lower() in source
        for signal in blocked_signals
    )


def has_no_result_message(driver):
    source = safe_page_source(driver)

    no_result_signals = [
        "검색 결과가 없습니다",
        "검색결과가 없습니다",
        "검색 결과 없음",
        "일치하는 검색 결과가 없습니다",
    ]

    return any(
        signal in source
        for signal in no_result_signals
    )


def extract_naver_meanings(driver):
    try:
        mean_elements = driver.find_elements(
            By.CSS_SELECTOR,
            MEAN_SELECTOR,
        )

    except WebDriverException as e:
        raise CrawlerError(
            code="DOM_READ_FAILED",
            title="검색 결과 읽기 실패",
            message=(
                "검색 결과 화면은 열렸지만 "
                "뜻 영역을 읽는 과정에서 문제가 발생했습니다."
            ),
            hint=(
                "브라우저 연결 상태를 확인한 뒤 "
                "다시 검색해주세요."
            ),
            technical_detail=str(e),
        ) from e

    meanings = []

    for element in mean_elements:
        try:
            text = element.get_attribute("innerText")

            if text is None:
                continue

            text = text.strip()

            if not text:
                continue

            if text not in meanings:
                meanings.append(text)

        except StaleElementReferenceException:
            continue

        except Exception:
            continue

    return meanings


def extract_naver_result_word(driver):
    try:
        mean_elements = driver.find_elements(
            By.CSS_SELECTOR,
            MEAN_SELECTOR,
        )

        if not mean_elements:
            return (
                "",
                make_warning(
                    "RESULT_WORD_NOT_FOUND",
                    (
                        "뜻은 확인했지만 실제 검색 결과 단어를 "
                        "별도로 확인하지 못했습니다."
                    ),
                ),
            )

        first_mean = mean_elements[0]

        result_container = first_mean.find_element(
            By.XPATH,
            "./ancestor::*[.//a//strong][1]",
        )

        word_elements = result_container.find_elements(
            By.XPATH,
            ".//a//strong",
        )

        for word_element in word_elements:
            try:
                result_word = word_element.get_attribute(
                    "innerText"
                )

                if result_word is None:
                    continue

                result_word = result_word.strip()

                if result_word:
                    return (
                        result_word,
                        None,
                    )

            except StaleElementReferenceException:
                continue

            except Exception:
                continue

        return (
            "",
            make_warning(
                "RESULT_WORD_NOT_FOUND",
                (
                    "뜻은 확인했지만 실제 검색 결과 단어를 "
                    "확인하지 못했습니다."
                ),
            ),
        )

    except Exception as e:
        print(
            "[Naver Selenium 경고] 결과 단어 추출 실패:",
            type(e).__name__,
            str(e),
        )

        return (
            "",
            make_warning(
                "RESULT_WORD_READ_FAILED",
                (
                    "실제 결과 단어 판독에 실패하여 "
                    "입력 검색어를 대신 사용했습니다."
                ),
            ),
        )


def click_naver_more_button(driver):
    try:
        more_buttons = driver.find_elements(
            By.XPATH,
            MORE_BUTTON_XPATH,
        )

    except WebDriverException:
        return (
            False,
            make_warning(
                "MORE_BUTTON_CHECK_FAILED",
                (
                    "추가 검색 결과가 있는지 "
                    "확인하는 과정에서 문제가 발생했습니다."
                ),
            ),
        )

    if len(more_buttons) == 0:
        return (
            False,
            None,
        )

    more_button = more_buttons[0]

    try:
        driver.execute_script(
            """
            arguments[0].scrollIntoView({
                behavior: 'instant',
                block: 'center'
            });
            """,
            more_button,
        )

        WebDriverWait(
            driver,
            5,
        ).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    MORE_BUTTON_XPATH,
                )
            )
        )

        more_button.click()

        return (
            True,
            None,
        )

    except ElementClickInterceptedException:
        try:
            driver.execute_script(
                "arguments[0].click();",
                more_button,
            )

            return (
                True,
                None,
            )

        except Exception:
            return (
                False,
                make_warning(
                    "MORE_BUTTON_CLICK_FAILED",
                    (
                        "'단어 더보기' 버튼을 누르지 못해 "
                        "일부 뜻만 표시될 수 있습니다."
                    ),
                ),
            )

    except Exception:
        try:
            driver.execute_script(
                "arguments[0].click();",
                more_button,
            )

            return (
                True,
                None,
            )

        except Exception:
            return (
                False,
                make_warning(
                    "MORE_BUTTON_CLICK_FAILED",
                    (
                        "'단어 더보기' 버튼을 누르지 못해 "
                        "일부 뜻만 표시될 수 있습니다."
                    ),
                ),
            )


def search_naver_dictionary(keyword, driver):
    keyword = keyword.strip()

    if not keyword:
        raise CrawlerError(
            code="EMPTY_KEYWORD",
            title="검색어 없음",
            message="검색어가 입력되지 않았습니다.",
            hint=(
                "검색할 단어를 입력한 뒤 "
                "다시 시도해주세요."
            ),
        )

    try:
        driver.get(NAVER_DICT_URL)

    except WebDriverException as e:
        raise CrawlerError(
            code="SITE_CONNECTION_FAILED",
            title="네이버 국어사전 접속 실패",
            message=(
                "네이버 국어사전 페이지에 "
                "접속하지 못했습니다."
            ),
            hint=(
                "인터넷 연결 상태를 확인한 뒤 "
                "다시 시도해주세요."
            ),
            technical_detail=str(e),
        ) from e

    try:
        search_box = WebDriverWait(
            driver,
            15,
        ).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    SEARCH_XPATH,
                )
            )
        )

    except TimeoutException as e:
        if is_access_blocked(driver):
            raise CrawlerError(
                code="ACCESS_BLOCKED",
                title="자동 접근 제한 감지",
                message=(
                    "자동화된 접근을 제한하는 화면이 "
                    "표시된 것으로 보입니다."
                ),
                hint=(
                    "잠시 후 다시 시도하거나 "
                    "로컬 Selenium 실행 상태를 확인해주세요."
                ),
                technical_detail=str(e),
            ) from e

        raise CrawlerError(
            code="SEARCH_BOX_NOT_FOUND",
            title="검색창을 찾지 못함",
            message=(
                "페이지는 열렸지만 검색 입력창을 "
                "찾지 못했습니다."
            ),
            hint=(
                "페이지 로딩이 지연되었거나 "
                "네이버 국어사전의 화면 구조가 "
                "변경되었을 수 있습니다."
            ),
            technical_detail=str(e),
        ) from e

    try:
        search_box.clear()
        search_box.send_keys(keyword)
        search_box.send_keys(Keys.ENTER)

    except WebDriverException as e:
        raise CrawlerError(
            code="SEARCH_INPUT_FAILED",
            title="검색 실행 실패",
            message=(
                "검색창은 찾았지만 검색어를 입력하거나 "
                "검색을 실행하지 못했습니다."
            ),
            hint=(
                "페이지가 다시 로딩되었거나 "
                "브라우저 연결에 문제가 생겼을 수 있습니다."
            ),
            technical_detail=str(e),
        ) from e

    try:
        WebDriverWait(
            driver,
            10,
        ).until(
            lambda d:
            len(
                d.find_elements(
                    By.CSS_SELECTOR,
                    MEAN_SELECTOR,
                )
            ) > 0
            or
            len(
                d.find_elements(
                    By.XPATH,
                    MORE_BUTTON_XPATH,
                )
            ) > 0
        )

    except TimeoutException as e:
        if is_access_blocked(driver):
            raise CrawlerError(
                code="ACCESS_BLOCKED",
                title="자동 접근 제한 감지",
                message=(
                    "검색 과정에서 자동화 접근 제한 화면이 "
                    "나타난 것으로 보입니다."
                ),
                hint="잠시 후 다시 시도해주세요.",
                technical_detail=str(e),
            ) from e

        if has_no_result_message(driver):
            raise CrawlerError(
                code="NO_RESULTS",
                title="검색 결과 없음",
                message=(
                    f"'{keyword}'에 대한 검색 결과를 "
                    "찾지 못했습니다."
                ),
                hint=(
                    "검색어의 철자와 띄어쓰기를 "
                    "확인해주세요."
                ),
                technical_detail=str(e),
            ) from e

        meanings = extract_naver_meanings(driver)

        if not meanings:
            raise CrawlerError(
                code="RESULT_LOAD_TIMEOUT",
                title="검색 결과 로딩 지연",
                message=(
                    "검색은 실행됐지만 제한 시간 안에 "
                    "검색 결과가 나타나지 않았습니다."
                ),
                hint=(
                    "네트워크 또는 페이지 로딩이 "
                    "지연되었을 수 있습니다. "
                    "잠시 후 다시 시도해주세요."
                ),
                technical_detail=str(e),
            ) from e

    warnings = []

    initial_meanings = extract_naver_meanings(driver)

    more_clicked, more_warning = click_naver_more_button(
        driver
    )

    if more_warning:
        warnings.append(more_warning)

    if more_clicked:
        initial_count = len(initial_meanings)

        try:
            WebDriverWait(
                driver,
                5,
            ).until(
                lambda d:
                len(
                    d.find_elements(
                        By.CSS_SELECTOR,
                        MEAN_SELECTOR,
                    )
                ) > initial_count
            )

        except TimeoutException:
            warnings.append(
                make_warning(
                    "MORE_RESULT_LOAD_TIMEOUT",
                    (
                        "'단어 더보기'를 눌렀지만 "
                        "추가 뜻이 제한 시간 안에 "
                        "나타나지 않았습니다."
                    ),
                )
            )

    meanings = extract_naver_meanings(driver)

    if not meanings:
        if is_access_blocked(driver):
            raise CrawlerError(
                code="ACCESS_BLOCKED",
                title="자동 접근 제한 감지",
                message=(
                    "검색 결과를 읽는 과정에서 "
                    "접근 제한이 발생한 것으로 보입니다."
                ),
                hint="잠시 후 다시 시도해주세요.",
            )

        if has_no_result_message(driver):
            raise CrawlerError(
                code="NO_RESULTS",
                title="검색 결과 없음",
                message=(
                    f"'{keyword}'에 대한 검색 결과를 "
                    "찾지 못했습니다."
                ),
                hint=(
                    "정확한 검색어를 입력하여 "
                    "다시 검색해주세요."
                ),
            )

        raise CrawlerError(
            code="MEANING_NOT_FOUND",
            title="뜻 영역을 찾지 못함",
            message=(
                "검색 결과 페이지는 열렸지만 "
                "뜻 텍스트를 찾지 못했습니다."
            ),
            hint=(
                "네이버 국어사전의 페이지 구조가 "
                "변경되었을 가능성이 있습니다."
            ),
        )

    result_word, word_warning = extract_naver_result_word(
        driver
    )

    word_detected = bool(result_word)

    if word_warning:
        warnings.append(word_warning)

    if not result_word:
        result_word = keyword

    result_url = driver.current_url

    return (
        result_word,
        word_detected,
        meanings,
        result_url,
        warnings,
    )


def get_naver_results(keyword):
    driver = None

    try:
        print("==========================================")
        print(f"[Naver Selenium] 검색 시작: {keyword}")

        driver = create_driver()

        (
            result_word,
            word_detected,
            meanings,
            result_url,
            warnings,
        ) = search_naver_dictionary(
            keyword,
            driver,
        )

        mismatch = (
            word_detected
            and
            normalize_for_compare(keyword)
            !=
            normalize_for_compare(result_word)
        )

        meaning_meta = [
            {
                "source": "네이버 국어사전",
                "glossary": "",
                "label": "네이버 국어사전 (Selenium)",
            }
            for _ in meanings
        ]

        result = {
            "status": "ok",
            "source_mode": SOURCE_NAVER,
            "source_name": "네이버 국어사전",
            "source_method": "Selenium 동적 크롤링",
            "input_keyword": keyword,
            "title": result_word,
            "url": result_url,
            "meanings": meanings,
            "meaning_meta": meaning_meta,
            "count": len(meanings),
            "word_detected": word_detected,
            "mismatch": mismatch,
            "warnings": warnings,
        }

        print(f"[Naver Selenium] 입력 검색어: {keyword}")
        print(f"[Naver Selenium] 실제 결과 단어: {result_word}")
        print(f"[Naver Selenium] 검색 결과 개수: {len(meanings)}")
        print("==========================================")

        return [result]

    except CrawlerError as e:
        print("==========================================")
        print(f"[Naver Selenium 오류 코드] {e.code}")
        print(f"[Naver Selenium 오류] {e.title}: {e.message}")

        if e.technical_detail:
            print(
                "[Naver Selenium 유지보수 로그] "
                f"{e.technical_detail}"
            )

        print("==========================================")

        return make_error_result(
            e,
            SOURCE_NAVER,
        )

    except WebDriverException as e:
        error = CrawlerError(
            code="BROWSER_COMMUNICATION_FAILED",
            title="브라우저 통신 오류",
            message=(
                "크롤링 도중 Chrome과의 연결이 "
                "끊겼습니다."
            ),
            hint=(
                "Chrome이 종료되지 않았는지 확인한 뒤 "
                "다시 시도해주세요."
            ),
            technical_detail=str(e),
        )

        print(
            "[Naver Selenium 유지보수 로그] "
            f"{type(e).__name__}: {e}"
        )

        return make_error_result(
            error,
            SOURCE_NAVER,
        )

    except Exception as e:
        error = CrawlerError(
            code="UNEXPECTED_ERROR",
            title="예상하지 못한 오류",
            message=(
                "네이버 국어사전 검색 처리 중 "
                "예상하지 못한 문제가 발생했습니다."
            ),
            hint=(
                "다시 시도한 뒤 같은 문제가 반복되면 "
                "서버 로그를 확인해주세요."
            ),
            technical_detail=f"{type(e).__name__}: {e}",
        )

        print("==========================================")
        print(
            "[Naver Selenium 유지보수 로그] "
            f"{error.technical_detail}"
        )
        print("==========================================")

        return make_error_result(
            error,
            SOURCE_NAVER,
        )

    finally:
        close_driver(driver)


# ============================================================
# 온용어 Open API
# ============================================================

def get_kli_api_key():
    api_key = os.getenv(
        KLI_API_KEY_ENV,
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


def request_kli_api(keyword):
    api_key = get_kli_api_key()

    params = {
        "key": api_key,
        "apiSearchWord": keyword,
        "start": "1",
        "num": "100",
        "sort": "wt",
    }

    request_url = (
        KLI_API_URL
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
            timeout=KLI_API_TIMEOUT,
        ) as response:
            raw_data = response.read()
            text = raw_data.decode("utf-8")

    except HTTPError as e:
        raise CrawlerError(
            code="API_HTTP_ERROR",
            title="API 요청 실패",
            message=(
                "언어정보나눔터 API 요청 중 "
                "HTTP 오류가 발생했습니다."
            ),
            hint="잠시 후 다시 검색해주세요.",
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
            hint="잠시 후 다시 시도해주세요.",
            technical_detail=str(e),
        ) from e

    try:
        return json.loads(text)

    except json.JSONDecodeError as e:
        raise CrawlerError(
            code="API_INVALID_RESPONSE",
            title="API 응답 오류",
            message=(
                "API에서 받은 데이터를 "
                "읽지 못했습니다."
            ),
            hint="잠시 후 다시 검색해주세요.",
            technical_detail=str(e),
        ) from e


def get_kli_channel(data):
    if not isinstance(data, dict):
        raise CrawlerError(
            code="API_INVALID_RESPONSE",
            title="API 응답 오류",
            message="API에서 올바르지 않은 응답을 받았습니다.",
            hint="잠시 후 다시 검색해주세요.",
        )

    channel = data.get("channel")

    if not isinstance(channel, dict):
        raise CrawlerError(
            code="API_INVALID_RESPONSE",
            title="API 응답 오류",
            message="API 검색 결과 구조를 읽지 못했습니다.",
            hint="잠시 후 다시 검색해주세요.",
        )

    return channel


def get_kli_return_objects(channel):
    return_objects = as_list(
        channel.get("return_object")
    )

    return [
        obj
        for obj in return_objects
        if isinstance(obj, dict)
    ]


def check_kli_api_error(channel):
    return_objects = get_kli_return_objects(channel)

    error_messages = {
        "000": "API 서버에서 시스템 오류가 발생했습니다.",
        "020": "등록되지 않은 API 인증키입니다.",
        "021": "현재 사용할 수 없는 API 인증키입니다.",
        "022": "Open API의 일일 사용 한도를 초과했습니다.",
        "100": "API 요청 형식이 올바르지 않습니다.",
    }

    for return_object in return_objects:
        return_code = str(
            return_object.get(
                "returnCode",
                "1",
            )
        ).strip()

        if return_code in ("", "1"):
            continue

        raise CrawlerError(
            code=f"API_ERROR_{return_code}",
            title="Open API 오류",
            message=error_messages.get(
                return_code,
                "Open API 요청 중 오류가 발생했습니다.",
            ),
            hint=(
                "인증키 상태와 API 사용 가능 여부를 "
                "확인해주세요."
            ),
        )


def parse_kli_total(channel):
    try:
        return int(
            channel.get(
                "total",
                0,
            )
            or 0
        )

    except (TypeError, ValueError):
        return 0


def flatten_kli_items(channel):
    items = []

    for return_object in get_kli_return_objects(channel):
        result_list = return_object.get("resultlist")

        for item in as_list(result_list):
            if isinstance(item, dict):
                items.append(item)

    return items


def select_kli_word_group(keyword, items):
    if not items:
        return []

    keyword_normalized = normalize_for_compare(keyword)

    exact_items = [
        item
        for item in items
        if normalize_for_compare(
            clean_kli_word(
                item.get("word", "")
            )
        ) == keyword_normalized
    ]

    if exact_items:
        return exact_items

    first_word = clean_kli_word(
        items[0].get(
            "word",
            keyword,
        )
    )

    first_word_normalized = normalize_for_compare(
        first_word
    )

    grouped_items = [
        item
        for item in items
        if normalize_for_compare(
            clean_kli_word(
                item.get("word", "")
            )
        ) == first_word_normalized
    ]

    return grouped_items or [items[0]]


def parse_kli_result(keyword, data):
    channel = get_kli_channel(data)

    # 인증키/요청 오류가 있다면 NO_RESULTS보다 먼저 처리
    check_kli_api_error(channel)

    total = parse_kli_total(channel)
    items = flatten_kli_items(channel)

    if total <= 0 or not items:
        raise CrawlerError(
            code="NO_RESULTS",
            title="검색 결과 없음",
            message=(
                f"'{keyword}'에 대한 검색 결과를 "
                "찾지 못했습니다."
            ),
            hint=(
                "검색어의 철자와 띄어쓰기를 확인하거나 "
                "다른 단어로 검색해주세요."
            ),
        )

    selected_items = select_kli_word_group(
        keyword,
        items,
    )

    first_item = selected_items[0]

    result_word = clean_kli_word(
        first_item.get(
            "word",
            keyword,
        )
    ) or keyword

    meanings = []
    meaning_meta = []
    seen_meanings = set()

    for item in selected_items:
        definition = clean_text(
            item.get(
                "definition",
                "",
            )
        )

        if not definition:
            continue

        if definition in seen_meanings:
            continue

        seen_meanings.add(definition)
        meanings.append(definition)

        source = clean_text(
            item.get(
                "source",
                "",
            )
        ) or "출처 정보 없음"

        glossary = clean_text(
            item.get(
                "glossary",
                "",
            )
        )

        label_parts = [source]

        if glossary:
            label_parts.append(glossary)

        meaning_meta.append(
            {
                "source": source,
                "glossary": glossary,
                "label": " · ".join(label_parts),
            }
        )

    if not meanings:
        raise CrawlerError(
            code="NO_RESULTS",
            title="검색 결과 없음",
            message=(
                f"'{keyword}'에 대해 표시할 수 있는 "
                "뜻풀이를 찾지 못했습니다."
            ),
            hint=(
                "검색어를 확인하거나 "
                "다른 단어로 검색해주세요."
            ),
        )

    word_detected = bool(result_word)

    mismatch = (
        word_detected
        and
        normalize_for_compare(keyword)
        !=
        normalize_for_compare(result_word)
    )

    return {
        "status": "ok",
        "source_mode": SOURCE_KLI,
        "source_name": "국립국어원 언어정보나눔터 · 온용어",
        "source_method": "Open API",
        "input_keyword": keyword,
        "title": result_word,
        "url": KLI_HOME_URL,
        "meanings": meanings,
        "meaning_meta": meaning_meta,
        "count": len(meanings),
        "word_detected": word_detected,
        "mismatch": mismatch,
        "warnings": [],
    }


def get_kli_results(keyword):
    try:
        print("==========================================")
        print(f"[KLI Open API] 검색 시작: {keyword}")

        data = request_kli_api(keyword)
        result = parse_kli_result(
            keyword,
            data,
        )

        print(f"[KLI Open API] 입력 검색어: {keyword}")
        print(
            "[KLI Open API] 실제 결과 단어: "
            f"{result['title']}"
        )
        print(
            "[KLI Open API] 검색 결과 개수: "
            f"{result['count']}"
        )
        print("==========================================")

        return [result]

    except CrawlerError as e:
        print("==========================================")
        print(f"[KLI Open API 오류 코드] {e.code}")
        print(f"[KLI Open API 오류] {e.title}: {e.message}")

        if e.technical_detail:
            print(
                "[KLI Open API 유지보수 로그] "
                f"{e.technical_detail}"
            )

        print("==========================================")

        return make_error_result(
            e,
            SOURCE_KLI,
        )

    except Exception as e:
        error = CrawlerError(
            code="UNEXPECTED_ERROR",
            title="예상하지 못한 오류",
            message=(
                "언어정보나눔터 API 검색 처리 중 "
                "예상하지 못한 문제가 발생했습니다."
            ),
            hint=(
                "잠시 후 다시 검색해주세요. "
                "같은 문제가 반복되면 서버 로그를 확인해주세요."
            ),
            technical_detail=f"{type(e).__name__}: {e}",
        )

        print("==========================================")
        print(
            "[KLI Open API 예상하지 못한 오류] "
            f"{error.technical_detail}"
        )
        print("==========================================")

        return make_error_result(
            error,
            SOURCE_KLI,
        )


# ============================================================
# 최종 진입점
#
# 기존 app.py가 get_crawl_results()만 호출해도
# query string의 source 값에 따라 자동으로 분기됩니다.
#
# /crawl-result?source=naver&keyword=사출
# /crawl-result?source=kli&keyword=사출
# ============================================================

def get_crawl_results(
    keyword=None,
    source=None,
):
    """
    기존 app.py는 그대로 두고 이 함수만 호출하면 됩니다.

    /crawl-result
        -> 검색 방식 선택 화면
        -> 실제 검색 실행 안 함

    /crawl-result?source=naver&keyword=자동차
        -> Selenium + 네이버 국어사전

    /crawl-result?source=kli&keyword=자동차
        -> 국립국어원 언어정보나눔터 · 온용어 Open API
    """
    if keyword is None:
        keyword = get_keyword_from_flask()

    keyword = str(
        keyword or ""
    ).strip()

    if not keyword:
        return []

    if source is None:
        source = get_source_from_flask()

        # 검색 방식을 고르지 않은 상태에서는
        # Selenium/API 어느 쪽도 실행하지 않습니다.
        if source not in (
            SOURCE_NAVER,
            SOURCE_KLI,
        ):
            return []

    else:
        source = normalize_source(source)

    if source == SOURCE_NAVER:
        return get_naver_results(
            keyword
        )

    return get_kli_results(
        keyword
    )
