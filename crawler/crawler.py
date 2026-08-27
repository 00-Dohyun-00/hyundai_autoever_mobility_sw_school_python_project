from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
)

import unicodedata


# ============================================================
# 네이버 국어사전 설정
# ============================================================

NAVER_DICT_URL = "https://ko.dict.naver.com/#/main"

SEARCH_XPATH = '//*[@id="ac_input"]'
MORE_BUTTON_XPATH = '//*[@id="searchPage_word_more"]'
MEAN_SELECTOR = 'p.mean[lang="ko"]'


# ============================================================
# 사용자에게 보여줄 크롤링 오류
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
# 경고 데이터 생성
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
#
# app.py의 구조를 바꾸지 않기 위해
# 여전히 list 형태로 반환한다.
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
# Chrome Driver 생성
# ============================================================

def create_driver():

    try:

        options = webdriver.ChromeOptions()


        # ====================================================
        # Chrome 창 숨기기
        #
        # 디버깅할 때 Chrome 화면을 보고 싶다면
        # 아래 한 줄을 주석 처리한다.
        # ====================================================

        options.add_argument(
            "--headless=new"
        )


        options.add_argument(
            "--disable-notifications"
        )

        options.add_argument(
            "--disable-popup-blocking"
        )

        options.add_argument(
            "--disable-gpu"
        )

        options.add_argument(
            "--window-size=1920,1080"
        )


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
                "시작하지 못했습니다."
            ),

            hint=(
                "Chrome 설치 여부, Chrome/ChromeDriver 버전, "
                "서버 실행 권한을 확인해주세요."
            ),

            technical_detail=str(e),

        ) from e


# ============================================================
# 현재 페이지 HTML 안전하게 읽기
# ============================================================

def safe_page_source(driver):

    try:

        return driver.page_source or ""

    except Exception:

        return ""


# ============================================================
# 자동화 차단 / CAPTCHA 추정
# ============================================================

def is_access_blocked(driver):

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

        "robot",

        "too many requests",

    ]


    return any(

        signal.lower() in source

        for signal in blocked_signals

    )


# ============================================================
# 실제 "검색 결과 없음" 문구 확인
# ============================================================

def has_no_result_message(driver):

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
# 검색어 비교용 문자열 정리
#
# 공백 차이 등은 무시한다.
# ============================================================

def normalize_for_compare(text):

    if text is None:

        return ""


    text = unicodedata.normalize(
        "NFKC",
        str(text),
    )


    return "".join(
        text.split()
    ).casefold()


# ============================================================
# 뜻 추출
# ============================================================

def extract_meanings(driver):

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
                "Chrome이 중간에 종료되지 않았는지 확인하고 "
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


        except WebDriverException:

            continue


        except Exception:

            continue


    return meanings


# ============================================================
# 실제 검색 결과 단어 추출
#
# 중요:
#
# 실패해도 전체 크롤링을 실패시키지 않는다.
# 뜻이 정상적으로 있으면 뜻은 그대로 사용한다.
# ============================================================

def extract_result_word(driver):

    try:

        mean_elements = driver.find_elements(
            By.CSS_SELECTOR,
            MEAN_SELECTOR,
        )


        if not mean_elements:

            return "", make_warning(

                "RESULT_WORD_NOT_FOUND",

                (
                    "실제 결과 단어를 읽지 못해 "
                    "입력 검색어를 제목으로 표시했습니다."
                ),

            )


        # 첫 번째 뜻
        first_mean = mean_elements[0]


        # 첫 번째 뜻을 포함하고 있으면서
        # 단어 <strong>이 있는 가장 가까운 부모 영역
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


        return "", make_warning(

            "RESULT_WORD_NOT_FOUND",

            (
                "뜻은 가져왔지만 실제 결과 단어를 "
                "읽지 못해 입력 검색어를 제목으로 표시했습니다."
            ),

        )


    except Exception as e:

        print(
            "[Crawler 경고] 결과 단어 추출 실패:",
            type(e).__name__,
            str(e),
        )


        return "", make_warning(

            "RESULT_WORD_READ_FAILED",

            (
                "뜻은 정상적으로 가져왔지만 "
                "결과 단어 판독에 실패해 입력 검색어를 "
                "제목으로 표시했습니다."
            ),

        )


# ============================================================
# 단어 더보기 버튼
#
# 실패해도 전체 크롤링 실패로 처리하지 않는다.
# ============================================================

def click_more_button(driver):

    try:

        more_buttons = driver.find_elements(

            By.XPATH,

            MORE_BUTTON_XPATH,

        )


    except WebDriverException:

        return False, make_warning(

            "MORE_BUTTON_CHECK_FAILED",

            (
                "추가 뜻이 있는지 확인하는 과정에서 "
                "오류가 발생했습니다. "
                "현재 화면의 뜻만 표시될 수 있습니다."
            ),

        )


    # 더보기 버튼 자체가 없는 경우 정상
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

            return False, make_warning(

                "MORE_BUTTON_CLICK_FAILED",

                (
                    "'단어 더보기' 버튼을 누르지 못했습니다. "
                    "일부 뜻만 표시될 수 있습니다."
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

            return False, make_warning(

                "MORE_BUTTON_CLICK_FAILED",

                (
                    "'단어 더보기' 버튼을 누르지 못했습니다. "
                    "일부 뜻만 표시될 수 있습니다."
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


    # ========================================================
    # 검색어 없음
    # ========================================================

    if not keyword:

        raise CrawlerError(

            code="EMPTY_KEYWORD",

            title="검색어 없음",

            message="검색어가 비어 있습니다.",

            hint=(
                "검색어를 입력한 뒤 다시 시도해주세요."
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
                "크롤링 대상 페이지에 접속하지 못했습니다."
            ),

            hint=(
                "인터넷 연결, 방화벽, DNS 또는 "
                "네이버 서비스 상태를 확인해주세요."
            ),

            technical_detail=str(e),

        ) from e


    # ========================================================
    # 검색창 기다리기
    # ========================================================

    wait = WebDriverWait(
        driver,
        15,
    )


    try:

        search_box = wait.until(

            EC.element_to_be_clickable(

                (
                    By.XPATH,
                    SEARCH_XPATH,
                )

            )

        )


    except TimeoutException as e:

        # 접근 제한 여부 먼저 확인
        if is_access_blocked(
            driver
        ):

            raise CrawlerError(

                code="ACCESS_BLOCKED",

                title="자동 접근 제한 감지",

                message=(
                    "네이버가 자동화된 접근으로 판단했거나 "
                    "추가 확인 화면을 표시한 것으로 보입니다."
                ),

                hint=(
                    "잠시 후 다시 시도하거나 "
                    "headless 모드를 끄고 Chrome 화면에서 "
                    "CAPTCHA 또는 접근 제한 화면이 있는지 확인해주세요."
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
                "페이지 로딩이 느리거나 네이버 페이지 구조가 "
                "변경되었을 가능성이 있습니다."
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
                "검색창은 찾았지만 검색어 입력 또는 "
                "검색 실행에 실패했습니다."
            ),

            hint=(
                "브라우저가 중간에 종료되었거나 "
                "페이지가 다시 로딩되었을 수 있습니다."
            ),

            technical_detail=str(e),

        ) from e


    # ========================================================
    # 검색 결과 로딩 기다리기
    #
    # 기존 정상 작동 방식 유지
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


        # ====================================================
        # CAPTCHA / 접근 제한
        # ====================================================

        if is_access_blocked(
            driver
        ):

            raise CrawlerError(

                code="ACCESS_BLOCKED",

                title="자동 접근 제한 감지",

                message=(
                    "검색 요청 이후 접근 제한 또는 "
                    "자동화 확인 화면이 표시된 것으로 보입니다."
                ),

                hint=(
                    "잠시 후 다시 시도하거나 "
                    "headless 모드를 해제하여 "
                    "실제 Chrome 화면을 확인해주세요."
                ),

                technical_detail=str(e),

            ) from e


        # ====================================================
        # 실제 검색 결과 없음
        # ====================================================

        if has_no_result_message(
            driver
        ):

            raise CrawlerError(

                code="NO_RESULTS",

                title="검색 결과 없음",

                message=(
                    f"'{keyword}'에 대한 사전 검색 결과를 "
                    "찾지 못했습니다."
                ),

                hint=(
                    "철자나 띄어쓰기를 확인하거나 "
                    "다른 검색어로 시도해주세요."
                ),

                technical_detail=str(e),

            ) from e


        # 혹시 로딩은 늦었지만 뜻은 생겼는지 재확인
        meanings = extract_meanings(
            driver
        )


        if not meanings:

            raise CrawlerError(

                code="RESULT_LOAD_TIMEOUT",

                title="검색 결과 로딩 지연",

                message=(
                    "검색은 실행됐지만 제한 시간 안에 "
                    "뜻 영역이 나타나지 않았습니다."
                ),

                hint=(
                    "네트워크가 느리거나 네이버 페이지 렌더링이 "
                    "지연됐을 수 있습니다. 다시 시도해주세요."
                ),

                technical_detail=str(e),

            ) from e


    # ========================================================
    # 처음 표시된 뜻
    # ========================================================

    initial_meanings = extract_meanings(
        driver
    )


    warnings = []


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

            # 전체 실패가 아니라 부분 경고
            warnings.append(

                make_warning(

                    "MORE_RESULT_LOAD_TIMEOUT",

                    (
                        "'단어 더보기'를 눌렀지만 "
                        "추가 뜻이 제한 시간 안에 불러와지지 않았습니다. "
                        "현재 확인된 뜻만 표시합니다."
                    ),

                )

            )


    # ========================================================
    # 최종 뜻 가져오기
    # ========================================================

    meanings = extract_meanings(
        driver
    )


    # ========================================================
    # 뜻 자체가 없음
    # ========================================================

    if not meanings:


        if is_access_blocked(
            driver
        ):

            raise CrawlerError(

                code="ACCESS_BLOCKED",

                title="자동 접근 제한 감지",

                message=(
                    "검색 결과를 읽는 도중 "
                    "접근 제한 화면이 표시된 것으로 보입니다."
                ),

                hint=(
                    "잠시 후 다시 시도하거나 "
                    "headless 모드를 해제해 실제 Chrome 화면을 "
                    "확인해주세요."
                ),

            )


        if has_no_result_message(
            driver
        ):

            raise CrawlerError(

                code="NO_RESULTS",

                title="검색 결과 없음",

                message=(
                    f"'{keyword}'에 대한 사전 검색 결과를 "
                    "찾지 못했습니다."
                ),

                hint=(
                    "철자, 띄어쓰기 또는 다른 형태의 "
                    "단어로 검색해보세요."
                ),

            )


        raise CrawlerError(

            code="MEANING_NOT_FOUND",

            title="뜻 영역을 찾지 못함",

            message=(
                "검색 결과 페이지는 열렸지만 "
                "뜻 텍스트를 읽지 못했습니다."
            ),

            hint=(
                "네이버 HTML 구조가 변경되었거나 "
                "일시적으로 결과 영역이 다른 형태로 "
                "렌더링되었을 수 있습니다."
            ),

        )


    # ========================================================
    # 실제 결과 단어 읽기
    # ========================================================

    result_word, word_warning = extract_result_word(
        driver
    )


    # 실제 단어를 성공적으로 읽었는지
    word_detected = bool(
        result_word
    )


    if word_warning:

        warnings.append(
            word_warning
        )


    # 실제 단어 추출 실패 시
    # 뜻은 살리고 제목만 입력 검색어 사용
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
# Chrome 종료
# ============================================================

def close_driver(driver):

    if driver is None:

        return


    try:

        driver.quit()


    except Exception:

        pass


# ============================================================
# Flask URL에서 keyword 가져오기
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
# Flask / Jinja2용 최종 함수
#
# app.py:
#
# results = get_crawl_results()
#
# 기존 호출 방식 그대로 사용 가능
# ============================================================

def get_crawl_results(
    keyword=None,
):

    if keyword is None:

        keyword = get_keyword_from_flask()


    keyword = str(
        keyword
    ).strip()


    # 처음 페이지를 연 상태
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


        # Chrome 실행
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


        # ====================================================
        # 검색어와 실제 결과 단어 비교
        #
        # 실제 단어 판독에 성공한 경우에만 비교
        # ====================================================

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


        # ====================================================
        # 정상 결과
        #
        # 하나의 검색 결과 안에 meanings를 배열로 담는다.
        # ====================================================

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
            f"[Crawler] 검색어/결과 불일치: {mismatch}"
        )

        print(
            f"[Crawler] 검색 완료: {len(meanings)}개"
        )

        print(
            "=========================================="
        )


        return [
            result
        ]


    # ========================================================
    # 예상해서 분류한 오류
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
                f"[Crawler 상세] {e.technical_detail}"
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
                "크롤링 도중 Chrome과의 연결이 끊겼습니다."
            ),

            hint=(
                "Chrome이 강제 종료되었거나 "
                "ChromeDriver 세션이 깨졌을 수 있습니다. "
                "다시 시도해주세요."
            ),

            technical_detail=str(e),

        )


        print(
            f"[Crawler 오류] {error.code}: {e}"
        )


        return make_error_result(
            error
        )


    # ========================================================
    # 아직 분류하지 못한 모든 오류
    #
    # 중요한 점:
    #
    # 그냥 []로 버리지 않고
    # UNEXPECTED_ERROR로 분류한다.
    #
    # 터미널에는 실제 Python 오류를 남긴다.
    # ========================================================

    except Exception as e:

        error = CrawlerError(

            code="UNEXPECTED_ERROR",

            title="예상하지 못한 오류",

            message=(
                "현재 오류 분류표에 등록되지 않은 "
                "예외가 발생했습니다."
            ),

            hint=(
                "터미널의 '[Crawler 오류]' 로그를 확인해주세요. "
                "새로운 오류 유형이면 해당 로그를 기준으로 "
                "새 분류를 추가할 수 있습니다."
            ),

            technical_detail=(
                f"{type(e).__name__}: {e}"
            ),

        )


        print(
            "=========================================="
        )

        print(
            f"[Crawler 오류] {error.technical_detail}"
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