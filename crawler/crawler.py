from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

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

MORE_BUTTON_XPATH = '//*[@id="searchPage_word_more"]'

MEAN_SELECTOR = 'p.mean[lang="ko"]'


# ============================================================
# Selenium Chrome Driver 생성
#
# Chrome 창은 사용자에게 표시되지 않음.
# Selenium 동적 크롤링은 그대로 수행함.
# ============================================================

def create_driver():

    try:

        options = webdriver.ChromeOptions()

        # ----------------------------------------------------
        # Chrome 창 숨기기
        # ----------------------------------------------------

        options.add_argument(
            "--headless=new"
        )

        # ----------------------------------------------------
        # 기본 옵션
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Driver 생성
        # ----------------------------------------------------

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
# 현재 페이지에 표시된 뜻 추출
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


            # 중복 뜻 제거
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
# 더보기 버튼 클릭
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

        # 버튼이 화면 가운데 오도록 이동
        driver.execute_script(
            """
            arguments[0].scrollIntoView({
                behavior: 'instant',
                block: 'center'
            });
            """,
            more_button
        )


        # JavaScript 클릭
        #
        # headless 환경에서는 일반 click보다
        # JavaScript click이 안정적인 경우가 많음
        driver.execute_script(
            "arguments[0].click();",
            more_button
        )


        return True


    except ElementClickInterceptedException:

        return False


    except Exception:

        return False


# ============================================================
# 네이버 국어사전 동적 검색
# ============================================================

def search_dictionary(
    keyword,
    driver
):

    # ========================================================
    # 검색어 검사
    # ========================================================

    keyword = keyword.strip()


    if not keyword:

        raise ValueError(
            "검색어를 입력하세요."
        )


    # ========================================================
    # 검색어 URL 인코딩
    #
    # 예:
    #
    # 금형
    #
    # →
    #
    # %EA%B8%88%ED%98%95
    #
    # ========================================================

    encoded_keyword = quote(
        keyword
    )


    # ========================================================
    # 네이버 국어사전 검색 주소
    #
    # 사용자가 입력한 검색어로 직접 접속
    # ========================================================

    search_url = (
        "https://ko.dict.naver.com/"
        f"#/search?query={encoded_keyword}"
    )


    print(
        f"[Crawler] 검색어: {keyword}"
    )

    print(
        f"[Crawler] 검색 URL: {search_url}"
    )


    # ========================================================
    # 검색 결과 페이지 접속
    # ========================================================

    try:

        driver.get(
            search_url
        )


    except WebDriverException as e:

        raise RuntimeError(
            "네이버 국어사전에 접속하지 못했습니다.\n\n"
            f"{e}"
        )


    # ========================================================
    # JavaScript가 검색 결과를 렌더링할 때까지 대기
    #
    # 뜻 또는 더보기 버튼이 나타날 때까지 기다림
    # ========================================================

    try:

        WebDriverWait(
            driver,
            15
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
    # 현재 뜻 목록
    # ========================================================

    initial_meanings = extract_meanings(
        driver
    )


    print(
        f"[Crawler] 최초 결과: {len(initial_meanings)}개"
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
    # 최종 뜻 추출
    # ========================================================

    meanings = extract_meanings(
        driver
    )


    if not meanings:

        raise LookupError(
            f"'{keyword}'에 대한 검색 결과가 없습니다."
        )


    print(
        f"[Crawler] 최종 결과: {len(meanings)}개"
    )


    # ========================================================
    # 실제 검색 결과 페이지 주소
    # ========================================================

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
# Flask / Jinja2 통합용 최종 함수
#
# Flask:
#
# results = get_crawl_results(keyword)
#
# 형태로 호출
# ============================================================

def get_crawl_results(
    keyword=""
):

    # ========================================================
    # 검색어 처리
    # ========================================================

    keyword = keyword.strip()


    if not keyword:

        return []


    driver = None


    try:

        print(
            "======================================"
        )

        print(
            f"[Crawler] '{keyword}' 크롤링 시작"
        )


        # ====================================================
        # Headless Selenium 실행
        # ====================================================

        driver = create_driver()


        # ====================================================
        # 실제 검색
        # ====================================================

        meanings, result_url = search_dictionary(
            keyword,
            driver
        )


        # ====================================================
        # Jinja2에서 사용할 데이터 생성
        #
        # [
        #     {
        #         "title": "...",
        #         "url": "...",
        #         "summary": "..."
        #     }
        # ]
        #
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
            f"[Crawler] 크롤링 완료: {len(results)}개"
        )

        print(
            "======================================"
        )


        return results


    except Exception as e:

        print(
            "======================================"
        )

        print(
            f"[Crawler 오류] {e}"
        )

        print(
            "======================================"
        )


        return []


    finally:

        close_driver(
            driver
        )