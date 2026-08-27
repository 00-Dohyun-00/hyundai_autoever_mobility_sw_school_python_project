import os
import unicodedata
import os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium import webdriver

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium.webdriver.chrome.service import Service

from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
)


# ============================================================
# 네이버 국어사전 설정
# ============================================================

NAVER_DICT_URL = "https://ko.dict.naver.com/#/main"

SEARCH_XPATH = '//*[@id="ac_input"]'

MORE_BUTTON_XPATH = '//*[@id="searchPage_word_more"]'

MEAN_SELECTOR = 'p.mean[lang="ko"]'


# ============================================================
# 크롤링 오류 클래스
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
# 경고 정보 생성
# ============================================================

def make_warning(
    code,
    message,
):

    return {
        "code": code,
        "message": message,
    }


# ============================================================
# 오류 결과 생성
# ============================================================

def make_error_result(
    error,
):

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
# Chrome Driver 생성
# ============================================================
def create_driver():

    try:

        options = webdriver.ChromeOptions()

        chromium_path = "/usr/bin/chromium"
        chromedriver_path = "/usr/bin/chromedriver"

        if os.path.exists(chromium_path):
            options.binary_location = chromium_path

        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        if os.path.exists(chromedriver_path):

            service = Service(chromedriver_path)

            driver = webdriver.Chrome(
                service=service,
                options=options,
            )

        else:

            driver = webdriver.Chrome(
                options=options
            )

        return driver

    except WebDriverException as e:

        raise CrawlerError(
            code="DRIVER_START_FAILED",
            title="Chrome 실행 실패",
            message=(
                "크롤링에 사용할 Chrome 브라우저를 "
                "실행하지 못했습니다."
            ),
            hint=(
                "Chrome 설치 상태와 Selenium 실행 환경을 "
                "확인해주세요."
            ),
            technical_detail=str(e),
        ) from e


# ============================================================
# Driver 종료
# ============================================================

def close_driver(
    driver,
):

    if driver is None:

        return


    try:

        driver.quit()

    except Exception:

        pass


# ============================================================
# 페이지 소스 안전하게 읽기
# ============================================================

def safe_page_source(
    driver,
):

    try:

        return driver.page_source or ""

    except Exception:

        return ""


# ============================================================
# 자동화 접근 제한 확인
# ============================================================

def is_access_blocked(
    driver,
):

    source = safe_page_source(
        driver
    ).lower()


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


# ============================================================
# 검색 결과 없음 메시지 확인
# ============================================================

def has_no_result_message(
    driver,
):

    source = safe_page_source(
        driver
    )


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


# ============================================================
# 검색어 비교용 정규화
# ============================================================

def normalize_for_compare(
    text,
):

    if text is None:

        return ""


    text = unicodedata.normalize(
        "NFKC",
        str(text),
    )


    text = "".join(
        text.split()
    )


    return text.casefold()


# ============================================================
# 뜻 추출
# ============================================================

def extract_meanings(
    driver,
):

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

            text = element.get_attribute(
                "innerText"
            )


            if text is None:

                continue


            text = text.strip()


            if not text:

                continue


            if text not in meanings:

                meanings.append(
                    text
                )


        except StaleElementReferenceException:

            continue


        except Exception:

            continue


    return meanings


# ============================================================
# 실제 검색 결과 단어 추출
#
# 결과 단어를 찾지 못해도
# 뜻 검색 결과 자체는 유지합니다.
# ============================================================

def extract_result_word(
    driver,
):

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
            "[Crawler 경고] 결과 단어 추출 실패:",
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


# ============================================================
# '단어 더보기' 버튼 클릭
# ============================================================

def click_more_button(
    driver,
):

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


# ============================================================
# 네이버 국어사전 검색
# ============================================================

def search_dictionary(
    keyword,
    driver,
):

    keyword = keyword.strip()


    if not keyword:

        raise CrawlerError(

            code="EMPTY_KEYWORD",

            title="검색어 없음",

            message=(
                "검색어가 입력되지 않았습니다."
            ),

            hint=(
                "검색할 단어를 입력한 뒤 "
                "다시 시도해주세요."
            ),

        )


    # ========================================================
    # 네이버 국어사전 접속
    # ========================================================

    try:

        driver.get(
            NAVER_DICT_URL
        )


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


    # ========================================================
    # 검색창 확인
    # ========================================================

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

        if is_access_blocked(
            driver
        ):

            raise CrawlerError(

                code="ACCESS_BLOCKED",

                title="자동 접근 제한 감지",

                message=(
                    "자동화된 접근을 제한하는 화면이 "
                    "표시된 것으로 보입니다."
                ),

                hint=(
                    "잠시 후 다시 시도하거나 "
                    "Headless 모드를 해제하여 "
                    "Chrome 화면을 확인해주세요."
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


    # ========================================================
    # 검색어 입력
    # ========================================================

    try:

        search_box.clear()


        search_box.send_keys(
            keyword
        )


        search_box.send_keys(
            Keys.ENTER
        )


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


    # ========================================================
    # 검색 결과 대기
    # ========================================================

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

        if is_access_blocked(
            driver
        ):

            raise CrawlerError(

                code="ACCESS_BLOCKED",

                title="자동 접근 제한 감지",

                message=(
                    "검색 과정에서 자동화 접근 제한 화면이 "
                    "나타난 것으로 보입니다."
                ),

                hint=(
                    "잠시 후 다시 시도해주세요."
                ),

                technical_detail=str(e),

            ) from e


        if has_no_result_message(
            driver
        ):

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


        meanings = extract_meanings(
            driver
        )


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


    # ========================================================
    # 처음 보이는 뜻 확인
    # ========================================================

    initial_meanings = extract_meanings(
        driver
    )


    # ========================================================
    # 단어 더보기
    # ========================================================

    more_clicked, more_warning = click_more_button(
        driver
    )


    if more_warning:

        warnings.append(
            more_warning
        )


    if more_clicked:

        initial_count = len(
            initial_meanings
        )


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


    # ========================================================
    # 최종 뜻 추출
    # ========================================================

    meanings = extract_meanings(
        driver
    )


    if not meanings:

        if is_access_blocked(
            driver
        ):

            raise CrawlerError(

                code="ACCESS_BLOCKED",

                title="자동 접근 제한 감지",

                message=(
                    "검색 결과를 읽는 과정에서 "
                    "접근 제한이 발생한 것으로 보입니다."
                ),

                hint=(
                    "잠시 후 다시 시도해주세요."
                ),

            )


        if has_no_result_message(
            driver
        ):

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


    # ========================================================
    # 실제 결과 단어
    # ========================================================

    result_word, word_warning = extract_result_word(
        driver
    )


    word_detected = bool(
        result_word
    )


    if word_warning:

        warnings.append(
            word_warning
        )


    # 실제 결과 단어를 읽지 못했다면
    # 사용자가 입력한 검색어를 대신 사용
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


# ============================================================
# Flask request에서 검색어 읽기
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


    driver = None


    try:

        print(
            "=========================================="
        )

        print(
            f"[Crawler] 검색 시작: {keyword}"
        )


        driver = create_driver()


        (
            result_word,
            word_detected,
            meanings,
            result_url,
            warnings,
        ) = search_dictionary(

            keyword,

            driver,

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


        result = {

            "status": "ok",

            "input_keyword": keyword,

            "title": result_word,

            "url": result_url,

            "meanings": meanings,

            "count": len(
                meanings
            ),

            "word_detected": word_detected,

            "mismatch": mismatch,

            "warnings": warnings,

        }


        print(
            f"[Crawler] 입력 검색어: {keyword}"
        )

        print(
            f"[Crawler] 실제 결과 단어: {result_word}"
        )

        print(
            f"[Crawler] 검색 결과 개수: {len(meanings)}"
        )

        print(
            "=========================================="
        )


        return [
            result
        ]


    # ========================================================
    # 분류된 오류
    # ========================================================

    except CrawlerError as e:

        print(
            "=========================================="
        )

        print(
            f"[Crawler 오류 코드] {e.code}"
        )

        print(
            f"[Crawler 오류] {e.title}: {e.message}"
        )


        if e.technical_detail:

            print(
                f"[Crawler 유지보수 로그] "
                f"{e.technical_detail}"
            )


        print(
            "=========================================="
        )


        return make_error_result(
            e
        )


    # ========================================================
    # Chrome / Selenium 통신 오류
    # ========================================================

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
            "[Crawler 유지보수 로그] "
            f"{type(e).__name__}: {e}"
        )


        return make_error_result(
            error
        )


    # ========================================================
    # 현재 분류되지 않은 오류
    # ========================================================

    except Exception as e:

        error = CrawlerError(

            code="UNEXPECTED_ERROR",

            title="예상하지 못한 오류",

            message=(
                "현재 오류 분류에 포함되지 않은 "
                "문제가 발생했습니다."
            ),

            hint=(
                "다시 시도한 뒤 같은 문제가 반복되면 "
                "서버 로그를 확인해주세요."
            ),

            technical_detail=(
                f"{type(e).__name__}: {e}"
            ),

        )


        print(
            "=========================================="
        )

        print(
            "[Crawler 유지보수 로그] "
            f"{error.technical_detail}"
        )

        print(
            "=========================================="
        )


        return make_error_result(
            error
        )


    finally:

        close_driver(
            driver
        )