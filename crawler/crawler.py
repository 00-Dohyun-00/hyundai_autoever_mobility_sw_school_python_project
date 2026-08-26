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


# ============================================================
# 네이버 국어사전 설정
# ============================================================

NAVER_DICT_URL = "https://ko.dict.naver.com/#/main"

SEARCH_XPATH = '//*[@id="ac_input"]'
MORE_BUTTON_XPATH = '//*[@id="searchPage_word_more"]'
MEAN_SELECTOR = 'p.mean[lang="ko"]'


# ============================================================
# Selenium Chrome Driver 생성
#
# --headless=new
# → Chrome 창은 화면에 보이지 않음
# → Selenium 동적 크롤링은 그대로 동작함
# ============================================================

def create_driver():

    try:

        options = webdriver.ChromeOptions()

        # Chrome 창 숨기기
        options.add_argument(
            "--headless=new"
        )

        # 브라우저 설정
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

        raise RuntimeError(
            "Chrome 브라우저 실행에 실패했습니다.\n"
            "Chrome이 설치되어 있는지 확인해주세요.\n\n"
            f"상세 오류:\n{e}"
        )


# ============================================================
# 뜻 텍스트 추출
# ============================================================

def extract_meanings(driver):

    mean_elements = driver.find_elements(
        By.CSS_SELECTOR,
        MEAN_SELECTOR
    )

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

            # 같은 내용 중복 방지
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
# "단어 더보기" 버튼 처리
# ============================================================

def click_more_button(driver):

    more_buttons = driver.find_elements(
        By.XPATH,
        MORE_BUTTON_XPATH
    )

    # 더보기 버튼 없음
    if len(more_buttons) == 0:

        return False

    more_button = more_buttons[0]

    try:

        # 버튼 위치로 이동
        driver.execute_script(
            """
            arguments[0].scrollIntoView({
                behavior: 'instant',
                block: 'center'
            });
            """,
            more_button
        )

        # 클릭 가능할 때까지 기다림
        WebDriverWait(
            driver,
            5
        ).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    MORE_BUTTON_XPATH
                )
            )
        )

        # 일반 클릭
        more_button.click()

        return True

    except ElementClickInterceptedException:

        # 일반 클릭 실패 시 JavaScript 클릭
        try:

            driver.execute_script(
                "arguments[0].click();",
                more_button
            )

            return True

        except Exception:

            return False

    except Exception:

        # 기타 클릭 오류도 JavaScript로 재시도
        try:

            driver.execute_script(
                "arguments[0].click();",
                more_button
            )

            return True

        except Exception:

            return False


# ============================================================
# 네이버 국어사전 동적 검색
# ============================================================

def search_dictionary(
    keyword,
    driver
):

    # 검색어 정리
    keyword = keyword.strip()

    if not keyword:

        raise ValueError(
            "검색어를 입력하세요."
        )


    # ========================================================
    # 네이버 국어사전 접속
    # ========================================================

    try:

        driver.get(
            NAVER_DICT_URL
        )

    except WebDriverException as e:

        raise RuntimeError(
            "네이버 국어사전에 접속하지 못했습니다.\n\n"
            f"{e}"
        )


    # ========================================================
    # 검색창 로딩 기다리기
    # ========================================================

    wait = WebDriverWait(
        driver,
        15
    )

    try:

        search_box = wait.until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    SEARCH_XPATH
                )
            )
        )

    except TimeoutException:

        raise RuntimeError(
            "검색창을 찾지 못했습니다.\n"
            "네이버 국어사전 페이지 구조가 "
            "변경되었을 수 있습니다."
        )


    # ========================================================
    # 사용자가 입력한 검색어 검색
    # ========================================================

    search_box.clear()

    search_box.send_keys(
        keyword
    )

    search_box.send_keys(
        Keys.ENTER
    )


    # ========================================================
    # 검색 결과 로딩 기다리기
    # ========================================================

    try:

        WebDriverWait(
            driver,
            10
        ).until(

            lambda d:

            len(
                d.find_elements(
                    By.CSS_SELECTOR,
                    MEAN_SELECTOR
                )
            ) > 0

            or

            len(
                d.find_elements(
                    By.XPATH,
                    MORE_BUTTON_XPATH
                )
            ) > 0

        )

    except TimeoutException:

        meanings = extract_meanings(
            driver
        )

        if not meanings:

            raise LookupError(
                f"'{keyword}'에 대한 검색 결과가 없습니다."
            )


    # ========================================================
    # 처음 표시된 뜻
    # ========================================================

    initial_meanings = extract_meanings(
        driver
    )


    # ========================================================
    # 더보기 버튼
    # ========================================================

    more_clicked = click_more_button(
        driver
    )

    if more_clicked:

        initial_count = len(
            initial_meanings
        )

        try:

            WebDriverWait(
                driver,
                5
            ).until(

                lambda d:

                len(
                    d.find_elements(
                        By.CSS_SELECTOR,
                        MEAN_SELECTOR
                    )
                ) > initial_count

            )

        except TimeoutException:

            pass


    # ========================================================
    # 최종 결과
    # ========================================================

    meanings = extract_meanings(
        driver
    )

    if not meanings:

        raise LookupError(
            f"'{keyword}'에 대한 검색 결과가 없습니다."
        )


    # 실제 검색 후 현재 주소
    result_url = driver.current_url


    return (
        meanings,
        result_url
    )


# ============================================================
# Selenium Driver 종료
# ============================================================

def close_driver(driver):

    if driver is None:

        return

    try:

        driver.quit()

    except Exception:

        pass


# ============================================================
# Flask에서 현재 검색어 가져오기
#
# ★ app.py를 수정하지 않기 위해
# crawler 자체가 request.args에서 keyword를 가져옴
# ============================================================

def get_keyword_from_flask():

    try:

        # Flask를 여기에서만 import
        # crawler 자체 구조를 최대한 독립적으로 유지
        from flask import request

        keyword = request.args.get(
            "keyword",
            ""
        )

        if keyword is None:

            return ""

        return keyword.strip()

    except RuntimeError:

        # Flask request context 밖에서 실행된 경우
        return ""

    except Exception:

        return ""


# ============================================================
# Flask / Jinja2 통합용 최종 함수
#
# app.py에서는 기존 그대로:
#
# results = get_crawl_results()
#
# 호출하면 됨.
#
# URL:
# /crawl-result?keyword=사출
#
# 이면 crawler.py가 자동으로 "사출"을 읽음.
# ============================================================

def get_crawl_results(
    keyword=None
):

    # ========================================================
    # keyword를 직접 전달하지 않았다면
    # Flask URL에서 자동으로 가져옴
    # ========================================================

    if keyword is None:

        keyword = get_keyword_from_flask()


    # ========================================================
    # 문자열 정리
    # ========================================================

    keyword = str(
        keyword
    ).strip()


    # ========================================================
    # 검색어가 없는 경우
    #
    # 처음 /crawl-result 접속했을 때
    # Selenium을 실행하지 않음.
    # ========================================================

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


        # ====================================================
        # Headless Chrome 실행
        # ====================================================

        driver = create_driver()


        # ====================================================
        # 네이버 동적 크롤링
        # ====================================================

        meanings, result_url = search_dictionary(
            keyword,
            driver
        )


        # ====================================================
        # Jinja2에서 사용할 형식으로 변환
        # ====================================================

        results = []


        for index, meaning in enumerate(
            meanings,
            start=1
        ):

            results.append(
                {
                    "title": (
                        f"{keyword} 뜻 {index}"
                    ),

                    "url": result_url,

                    "summary": meaning,
                }
            )


        print(
            f"[Crawler] 검색 완료: {len(results)}개"
        )

        print(
            "=========================================="
        )


        return results


    except Exception as e:

        print(
            "=========================================="
        )

        print(
            f"[Crawler 오류] {e}"
        )

        print(
            "=========================================="
        )


        return []


    finally:

        close_driver(
            driver
        )