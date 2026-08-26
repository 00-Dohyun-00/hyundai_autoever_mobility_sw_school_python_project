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
# 설정
# ============================================================

NAVER_DICT_URL = "https://ko.dict.naver.com/#/main"

SEARCH_XPATH = '//*[@id="ac_input"]'
MORE_BUTTON_XPATH = '//*[@id="searchPage_word_more"]'
MEAN_SELECTOR = 'p.mean[lang="ko"]'


# ============================================================
# Selenium Chrome Driver 생성
# Chrome 창은 보이지 않지만 동적 크롤링은 그대로 수행
# ============================================================

def create_driver():
    try:
        options = webdriver.ChromeOptions()

        # Chrome 창 숨기기
        options.add_argument("--headless=new")

        # 브라우저 설정
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

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
# 현재 페이지의 뜻 텍스트 추출
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

            # 중복 방지
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

    except ElementClickInterceptedException:
        try:
            driver.execute_script(
                "arguments[0].click();",
                more_button
            )

        except Exception:
            return False

    except Exception:
        try:
            driver.execute_script(
                "arguments[0].click();",
                more_button
            )

        except Exception:
            return False

    return True


# ============================================================
# 네이버 국어사전 동적 검색
# ============================================================

def search_dictionary(keyword, driver):
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

    wait = WebDriverWait(
        driver,
        15
    )

    # ========================================================
    # 검색창 찾기
    # ========================================================

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
    # 검색 결과 로딩 대기
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
    # 현재 뜻 가져오기
    # ========================================================

    initial_meanings = extract_meanings(
        driver
    )

    # ========================================================
    # 더보기 버튼 처리
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
    # 최종 결과 추출
    # ========================================================

    meanings = extract_meanings(
        driver
    )

    if not meanings:
        raise LookupError(
            f"'{keyword}'에 대한 검색 결과가 없습니다."
        )

    # 검색 결과 페이지 주소
    result_url = driver.current_url

    return meanings, result_url


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
# Flask / Jinja2에서 사용하는 최종 함수
#
# 사용 예:
#
# get_crawl_results("사출")
# get_crawl_results("자동차")
# get_crawl_results("금형")
#
# 검색어 없이 호출해도 Flask가 터지지 않음
# ============================================================

def get_crawl_results(keyword=""):
    keyword = keyword.strip()

    # 검색어가 전달되지 않은 경우
    # TypeError 대신 빈 리스트 반환
    if not keyword:
        return []

    driver = None

    try:
        # ====================================================
        # Headless Chrome 실행
        # ====================================================

        driver = create_driver()

        # ====================================================
        # 사용자가 입력한 검색어로 동적 크롤링
        # ====================================================

        meanings, result_url = search_dictionary(
            keyword,
            driver
        )

        # ====================================================
        # Flask / Jinja2 전달용 데이터 생성
        # ====================================================

        results = []

        for index, meaning in enumerate(
            meanings,
            start=1
        ):
            results.append(
                {
                    "title": f"{keyword} 뜻 {index}",
                    "url": result_url,
                    "summary": meaning
                }
            )

        return results

    except Exception as e:
        print(
            f"[Crawler 오류] {e}"
        )

        return []

    finally:
        close_driver(
            driver
        )