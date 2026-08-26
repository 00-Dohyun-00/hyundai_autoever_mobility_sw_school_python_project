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
# ============================================================

def create_driver():
    try:
        options = webdriver.ChromeOptions()

        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")

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

            meanings.append(
                text
            )

        except StaleElementReferenceException:
            continue

        except Exception:
            continue

    return meanings


# ============================================================
# 더보기 버튼 처리
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
                behavior: 'smooth',
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
# 네이버 국어사전 검색
# ============================================================

def search_dictionary(keyword, driver):
    """
    네이버 국어사전에서 단어를 검색하고
    검색된 뜻을 list 형태로 반환한다.
    """

    keyword = keyword.strip()

    if not keyword:
        raise ValueError(
            "검색어를 입력하세요."
        )

    # 네이버 국어사전 접속
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

    # 검색창 찾기
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

    # 검색 실행
    search_box.clear()

    search_box.send_keys(
        keyword
    )

    search_box.send_keys(
        Keys.ENTER
    )

    # 검색 결과 기다리기
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

    # 현재 화면 뜻
    initial_meanings = extract_meanings(
        driver
    )

    # 더보기
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

    # 최종 뜻 추출
    meanings = extract_meanings(
        driver
    )

    if not meanings:
        raise LookupError(
            f"'{keyword}'에 대한 검색 결과가 없습니다."
        )

    return meanings


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
# ★ Flask / Jinja2 통합용 최종 함수
# ============================================================

def get_crawl_results():
    """
    사출 관련 크롤링 결과 목록을 반환한다.

    Flask / Jinja2에서 바로 사용할 수 있도록
    list[dict] 형태로 반환한다.

    Returns:
        [
            {
                "title": "...",
                "url": "...",
                "summary": "..."
            },
            ...
        ]
    """

    driver = None

    try:
        # Chrome 실행
        driver = create_driver()

        # 검색 키워드
        keyword = "사출"

        # 네이버 국어사전 검색
        meanings = search_dictionary(
            keyword,
            driver
        )

        # Flask / Jinja2 전달용 결과
        results = []

        for index, meaning in enumerate(
            meanings,
            start=1
        ):
            results.append(
                {
                    "title": f"{keyword} 뜻 {index}",
                    "url": NAVER_DICT_URL,
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