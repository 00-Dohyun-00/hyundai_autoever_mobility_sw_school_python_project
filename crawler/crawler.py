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
#
# headless=True
# → 크롬 창을 화면에 띄우지 않고 실행
#
# 동적 크롤링은 그대로 유지됨
# ============================================================

def create_driver(headless=True):
    try:
        options = webdriver.ChromeOptions()

        # ----------------------------------------------------
        # Chrome 창 숨기기
        # ----------------------------------------------------
        if headless:
            options.add_argument("--headless=new")

        # ----------------------------------------------------
        # Chrome 설정
        # ----------------------------------------------------
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")

        # headless에서는 화면 크기를 직접 지정
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

            # 같은 뜻이 중복으로 들어가는 것 방지
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
# 더보기 버튼 처리
# ============================================================

def click_more_button(driver):
    more_buttons = driver.find_elements(
        By.XPATH,
        MORE_BUTTON_XPATH
    )

    # 더보기 버튼이 없으면 종료
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

        more_button.click()

    except ElementClickInterceptedException:
        # 일반 클릭 실패 시 JavaScript 클릭
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
#
# keyword에 원하는 검색어를 넣으면 됨
# ============================================================

def search_dictionary(keyword, driver):
    """
    네이버 국어사전에서 원하는 단어를 검색하고
    검색된 뜻을 list 형태로 반환한다.

    Parameters
    ----------
    keyword : str
        사용자가 입력한 검색어

    driver : webdriver.Chrome
        Selenium Chrome Driver

    Returns
    -------
    list[str]
        검색된 뜻 목록
    """

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
    # 검색 결과 기다리기
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
    # 현재 화면 뜻 가져오기
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

    # 실제 검색 결과 페이지 주소
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
# ★ Flask / Jinja2에서 호출하는 최종 함수
#
# 이제 keyword를 외부에서 받는다.
#
# 예:
#
# get_crawl_results("사출")
# get_crawl_results("자동차")
# get_crawl_results("금형")
# ============================================================

def get_crawl_results(keyword):
    """
    사용자가 입력한 검색어를 네이버 국어사전에서
    동적으로 크롤링한다.

    Flask / Jinja2에서 바로 사용할 수 있도록
    list[dict] 형태로 반환한다.

    Parameters
    ----------
    keyword : str
        사용자가 입력한 검색어

    Returns
    -------
    list[dict]

        [
            {
                "title": "...",
                "url": "...",
                "summary": "..."
            }
        ]
    """

    # 검색어 앞뒤 공백 제거
    keyword = keyword.strip()

    # 검색어가 없으면 빈 결과
    if not keyword:
        return []

    driver = None

    try:
        # ====================================================
        # Chrome을 화면에 띄우지 않고 실행
        # ====================================================

        driver = create_driver(
            headless=True
        )

        # ====================================================
        # 사용자가 입력한 검색어로 크롤링
        # ====================================================

        meanings, result_url = search_dictionary(
            keyword,
            driver
        )

        # ====================================================
        # Flask / Jinja2 전달용 결과 생성
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
        # Selenium 종료
        close_driver(
            driver
        )