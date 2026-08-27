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

# 네이버 국어사전 검색창
SEARCH_XPATH = '//*[@id="ac_input"]'

# 단어 더보기 버튼
MORE_BUTTON_XPATH = '//*[@id="searchPage_word_more"]'

# 뜻
MEAN_SELECTOR = 'p.mean[lang="ko"]'

# ============================================================
# ★ 검색 결과의 실제 단어
#
# 사용자가 제공한 XPath
#
# 예:
# 사용자가 "사출" 검색
#
# 이 위치에 실제로 표시된 단어가
# "사출"이면 결과 사용
#
# "사출하다", "압출" 등 다른 단어면 결과 폐기
# ============================================================

RESULT_WORD_XPATH = (
    '//*[@id="contents"]'
    '/div[3]'
    '/div[1]'
    '/div[1]'
    '/div[1]'
    '/a'
    '/span'
    '/strong'
)

# ============================================================
# 첫 번째 검색 결과 전체 영역
#
# 뜻을 페이지 전체에서 긁으면
# 다른 관련 단어의 뜻까지 섞일 수 있으므로
# 첫 번째 검색 결과 영역 안에서만 뜻을 가져옴.
# ============================================================

FIRST_RESULT_XPATH = (
    '//*[@id="contents"]'
    '/div[3]'
    '/div[1]'
)


# ============================================================
# Chrome Driver 생성
#
# Chrome 창은 표시하지 않음.
# JavaScript는 실제 Chrome에서 실행되므로
# 동적 크롤링은 그대로 유지됨.
# ============================================================

def create_driver():
    try:
        options = webdriver.ChromeOptions()

        # Chrome 창 숨기기
        #   "--headless=new"
        #)

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
# 문자열 비교용 정리
# ============================================================

def normalize_word(text):
    """
    검색어와 크롤링된 단어를 비교하기 전에
    앞뒤 공백과 내부 불필요한 공백을 제거한다.

    예:
        " 사출 " -> "사출"
        "사 출"   -> "사출"
    """

    if text is None:
        return ""

    return "".join(
        str(text).split()
    )


# ============================================================
# 실제 검색 결과 단어 크롤링
#
# 중요:
# 입력받은 keyword를 title로 사용하는 것이 아님.
# 네이버 페이지에 실제 표시된 단어를 Selenium으로 가져옴.
# ============================================================

def extract_result_word(driver):
    try:
        result_word_element = WebDriverWait(
            driver,
            10
        ).until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    RESULT_WORD_XPATH
                )
            )
        )

        result_word = result_word_element.get_attribute(
            "innerText"
        )

        if result_word is None:
            return ""

        return result_word.strip()

    except TimeoutException:
        return ""

    except StaleElementReferenceException:
        return ""

    except Exception:
        return ""


# ============================================================
# 첫 번째 검색 결과의 뜻만 크롤링
#
# 페이지 전체의 p.mean을 가져오지 않음.
# 첫 번째 검색 결과 영역 내부의 뜻만 가져온다.
# ============================================================

def extract_meanings(driver):
    meanings = []

    try:
        first_result = driver.find_element(
            By.XPATH,
            FIRST_RESULT_XPATH
        )

    except Exception:
        return meanings

    try:
        mean_elements = first_result.find_elements(
            By.CSS_SELECTOR,
            MEAN_SELECTOR
        )

    except Exception:
        return meanings

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

            # 중복 결과 제거
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
# 단어 더보기 버튼 클릭
# ============================================================

def click_more_button(driver):
    try:
        more_buttons = driver.find_elements(
            By.XPATH,
            MORE_BUTTON_XPATH
        )

    except Exception:
        return False

    if len(more_buttons) == 0:
        return False

    more_button = more_buttons[0]

    try:
        driver.execute_script(
            """
            arguments[0].scrollIntoView({
                behavior: 'instant',
                block: 'center'
            });
            """,
            more_button
        )

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

        more_button.click()

        return True

    except ElementClickInterceptedException:
        try:
            driver.execute_script(
                "arguments[0].click();",
                more_button
            )

            return True

        except Exception:
            return False

    except Exception:
        try:
            driver.execute_script(
                "arguments[0].click();",
                more_button
            )

            return True

        except Exception:
            return False


# ============================================================
# 네이버 국어사전 검색
# ============================================================

def search_dictionary(
    keyword,
    driver
):
    """
    Selenium으로 네이버 국어사전을 실제 검색한다.

    반환값은 입력값을 그대로 사용하는 것이 아니라
    웹 페이지에서 크롤링한 실제 데이터를 사용한다.

    Returns
    -------
    dict | None

    성공:
        {
            "word": "실제 크롤링된 단어",
            "meanings": [...],
            "url": "실제 검색 결과 주소"
        }

    정확히 일치하는 검색 결과 없음:
        None
    """

    keyword = keyword.strip()

    if not keyword:
        return None

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
    # 검색창이 나타날 때까지 기다림
    # ========================================================

    try:
        search_box = WebDriverWait(
            driver,
            15
        ).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    SEARCH_XPATH
                )
            )
        )

    except TimeoutException:
        raise RuntimeError(
            "네이버 국어사전 검색창을 찾지 못했습니다.\n"
            "페이지 구조가 변경되었을 수 있습니다."
        )


    # ========================================================
    # 검색 실행
    # ========================================================

    search_box.clear()

    search_box.send_keys(
        keyword
    )

    search_box.send_keys(
        Keys.ENTER
    )


    # ========================================================
    # 실제 검색 결과 단어가 표시될 때까지 기다림
    # ========================================================

    try:
        WebDriverWait(
            driver,
            10
        ).until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    RESULT_WORD_XPATH
                )
            )
        )

    except TimeoutException:
        print(
            f"[Crawler] '{keyword}' 검색 결과 없음"
        )

        return None


    # ========================================================
    # ★ 실제 웹페이지에서 검색 결과 단어 크롤링
    # ========================================================

    crawled_word = extract_result_word(
        driver
    )


    print(
        f"[Crawler] 입력 검색어: {keyword}"
    )

    print(
        f"[Crawler] 실제 크롤링 단어: {crawled_word}"
    )


    # ========================================================
    # ★ 핵심 검사
    #
    # 사용자가 입력한 단어
    #
    #       VS
    #
    # 네이버 검색 결과에서 실제 크롤링한 단어
    #
    # 두 단어가 다르면 결과를 사용하지 않는다.
    # ========================================================

    normalized_keyword = normalize_word(
        keyword
    )

    normalized_crawled_word = normalize_word(
        crawled_word
    )


    if (
        not normalized_crawled_word
        or normalized_keyword
        != normalized_crawled_word
    ):

        print(
            "[Crawler] 검색어와 실제 결과 단어가 다름"
        )

        print(
            "[Crawler] 해당 결과 폐기"
        )

        return None


    # ========================================================
    # 정확히 같은 단어를 찾았을 때만 뜻 크롤링
    # ========================================================

    initial_meanings = extract_meanings(
        driver
    )


    # ========================================================
    # 더보기 버튼이 있으면 클릭
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
                    extract_meanings(d)
                ) > initial_count
            )

        except TimeoutException:
            pass


    # ========================================================
    # 최종 뜻 크롤링
    # ========================================================

    meanings = extract_meanings(
        driver
    )


    # 뜻이 하나도 없다면 결과 없음
    if not meanings:
        print(
            f"[Crawler] '{crawled_word}'의 뜻을 찾지 못함"
        )

        return None


    # ========================================================
    # 실제 검색 페이지 주소
    # ========================================================

    result_url = driver.current_url


    # ========================================================
    # 입력값이 아닌 실제 크롤링 결과 반환
    # ========================================================

    return {
        "word": crawled_word,
        "meanings": meanings,
        "url": result_url,
    }


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
# Flask URL에서 사용자가 검색한 단어 가져오기
#
# app.py는 수정하지 않는다.
#
# 기존 app.py:
#
#     results = get_crawl_results()
#
# 그대로 사용 가능.
# ============================================================

def get_keyword_from_flask():
    try:
        from flask import request

        keyword = request.args.get(
            "keyword",
            ""
        )

        if keyword is None:
            return ""

        return keyword.strip()

    except RuntimeError:
        return ""

    except Exception:
        return ""


# ============================================================
# Flask / Jinja2 통합용 최종 함수
#
# app.py에서는 기존 그대로:
#
#     results = get_crawl_results()
#
# 사용
# ============================================================

def get_crawl_results(
    keyword=None
):
    """
    검색 결과를 list[dict] 형태로 반환한다.

    중요한 점:
    title은 사용자가 입력한 keyword가 아니다.

    Selenium으로 웹페이지에서 실제 크롤링한
    단어를 title로 사용한다.

    정확히 일치하는 단어가 없으면:
        []

    반환 예:
        [
            {
                "title": "사출",
                "url": "...",
                "summary": "..."
            }
        ]
    """

    # ========================================================
    # keyword가 직접 전달되지 않았다면
    # 현재 Flask 주소에서 가져옴.
    # ========================================================

    if keyword is None:
        keyword = get_keyword_from_flask()


    keyword = str(
        keyword
    ).strip()


    # ========================================================
    # 검색 전 상태
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
        # Headless Selenium 실행
        # ====================================================

        driver = create_driver()


        # ====================================================
        # 실제 네이버 동적 크롤링
        # ====================================================

        crawled_result = search_dictionary(
            keyword,
            driver
        )


        # ====================================================
        # 검색 결과 없음
        #
        # 검색어와 실제 크롤링 단어가 다른 경우도
        # 여기에 포함됨.
        # ====================================================

        if crawled_result is None:
            print(
                "[Crawler] 정확히 일치하는 검색 결과 없음"
            )

            print(
                "=========================================="
            )

            return []


        # ====================================================
        # 실제 크롤링 데이터
        # ====================================================

        crawled_word = crawled_result[
            "word"
        ]

        meanings = crawled_result[
            "meanings"
        ]

        result_url = crawled_result[
            "url"
        ]


        # ====================================================
        # Flask / Jinja2 전달용 결과
        #
        # ★ title에 keyword 사용 안 함
        # ★ 웹페이지에서 긁어온 crawled_word 사용
        #
        # ★ summary 역시 크롤링한 뜻 사용
        # ====================================================

        results = []


        for index, meaning in enumerate(
            meanings,
            start=1
        ):
            results.append(
                {
                    "title": (
                        f"{crawled_word} 뜻 {index}"
                    ),
                    "url": result_url,
                    "summary": meaning,
                }
            )


        print(
            f"[Crawler] 최종 결과: {len(results)}개"
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