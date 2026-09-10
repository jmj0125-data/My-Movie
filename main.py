import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일별 박스오피스")
st.caption("KOBIS 영화관입장권통합전산망 기준")


# --------------------------------------------------
# 한국 시간 기준으로 오늘과 어제 날짜 계산
# --------------------------------------------------
# 배포 서버의 시간이 한국 시간이 아닐 수도 있으므로
# 한국 시간(Asia/Seoul)을 기준으로 날짜를 계산합니다.

KOREA_TZ = ZoneInfo("Asia/Seoul")

today_korea = datetime.now(KOREA_TZ).date()
yesterday = today_korea - timedelta(days=1)


# --------------------------------------------------
# 날짜 선택
# --------------------------------------------------
# 가장 최근에 선택할 수 있는 날짜는 어제입니다.
# 시작 날짜는 넉넉하게 2000년으로 설정했습니다.

selected_date = st.date_input(
    "📅 조회할 날짜를 선택하세요",
    value=yesterday,
    min_value=datetime(2000, 1, 1).date(),
    max_value=yesterday
)

# KOBIS API가 사용하는 YYYYMMDD 형식으로 변환합니다.
target_date = selected_date.strftime("%Y%m%d")

# 화면에 보여 줄 날짜
display_date = selected_date.strftime("%Y년 %m월 %d일")


# --------------------------------------------------
# KOBIS API에서 데이터 가져오기
# --------------------------------------------------

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    """
    선택한 날짜의 KOBIS 일별 박스오피스 데이터를 가져옵니다.

    같은 날짜를 다시 조회하면 약 1시간 동안
    저장된 데이터를 사용하여 API를 다시 호출하지 않습니다.
    """

    # Streamlit Secrets에서 KOBIS 인증키를 가져옵니다.
    # 인증키를 코드에 직접 적지 않습니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]

    except Exception:
        return {
            "success": False,
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 Secrets에 "
                "`KOBIS_KEY`가 등록되어 있는지 확인해 주세요."
            )
        }

    # KOBIS 공식 일별 박스오피스 API 주소
    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    # API에 전달할 값
    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        # KOBIS API 호출
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류 확인
        response.raise_for_status()

        # JSON 데이터로 변환
        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API에 접속하지 못했습니다.\n\n"
                f"오류 내용: {e}\n\n"
                "인터넷 연결이나 KOBIS API 상태를 확인해 주세요."
            )
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API에서 올바른 JSON 데이터를 받지 못했습니다.\n\n"
                "잠시 후 다시 실행해 주세요."
            )
        }

    # --------------------------------------------------
    # faultInfo 확인
    # --------------------------------------------------
    # 인증키가 잘못되어도 HTTP 상태코드는 200일 수 있습니다.
    # 따라서 faultInfo가 있는지 확인해야 합니다.

    if "faultInfo" in data:

        fault = data["faultInfo"]

        fault_code = fault.get(
            "faultCode",
            "알 수 없음"
        )

        fault_message = fault.get(
            "message",
            "알 수 없는 오류"
        )

        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 코드: {fault_code}\n"
                f"오류 내용: {fault_message}\n\n"
                "Streamlit Secrets의 KOBIS_KEY가 "
                "정확한지 확인해 주세요."
            )
        }

    # --------------------------------------------------
    # boxOfficeResult 확인
    # --------------------------------------------------

    if "boxOfficeResult" not in data:
        return {
            "success": False,
            "message": (
                "KOBIS API 응답에 boxOfficeResult가 없습니다.\n\n"
                "API 응답 형식이나 KOBIS 서버 상태를 확인해 주세요."
            )
        }

    boxoffice = data["boxOfficeResult"]

    # 영화 목록 가져오기
    movie_list = boxoffice.get(
        "dailyBoxOfficeList",
        []
    )

    # --------------------------------------------------
    # 영화 목록이 비어 있는 경우
    # --------------------------------------------------

    if not movie_list:
        return {
            "success": False,
            "empty": True,
            "message": "그날은 아직 집계 전입니다."
        }

    return {
        "success": True,
        "empty": False,
        "data": movie_list
    }


# --------------------------------------------------
# API 실행
# --------------------------------------------------

result = get_boxoffice(target_date)


# --------------------------------------------------
# 오류 또는 빈 목록 처리
# --------------------------------------------------

if not result["success"]:

    if result.get("empty", False):

        st.warning("📊 그날은 아직 집계 전입니다.")

        st.info(
            "선택한 날짜에 KOBIS에서 제공하는 "
            "박스오피스 데이터가 아직 없습니다. "
            "다른 날짜를 선택해 보세요."
        )

    else:

        st.error(result["message"])

        st.info(
            "확인할 항목: KOBIS_KEY → "
            "KOBIS API 상태 → 조회 날짜의 집계 여부"
        )

    # 오류가 있으면 아래 내용을 실행하지 않습니다.
    st.stop()


# --------------------------------------------------
# 데이터프레임 만들기
# --------------------------------------------------

movies = result["data"]

df = pd.DataFrame(movies)


# --------------------------------------------------
# 숫자 데이터 숫자형으로 변환
# --------------------------------------------------
# KOBIS API에서는 숫자도 문자열로 보내므로
# 정렬과 그래프를 위해 숫자로 변환합니다.

number_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt"
]

for column in number_columns:

    if column in df.columns:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        ).fillna(0)


# 순위순으로 정렬
df = df.sort_values(
    "rank"
).reset_index(drop=True)


# --------------------------------------------------
# 조회 날짜 표시
# --------------------------------------------------

st.subheader(
    f"📅 {display_date} 박스오피스"
)


# --------------------------------------------------
# 1위 영화
# --------------------------------------------------

if len(df) > 0:

    first_movie = df.iloc[0]

    # 누적관객이 100만 명 이상이면 트로피 표시
    trophy = ""

    if first_movie["audiAcc"] > 1_000_000:
        trophy = " 🏆"

    st.markdown(
        f"## 🥇 1위: {first_movie['movieNm']}{trophy}"
    )

    # 지표 카드 세 장
    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "당일 관객수",
            f"{int(first_movie['audiCnt']):,}명"
        )

    with col2:

        st.metric(
            "누적 관객수",
            f"{int(first_movie['audiAcc']):,}명"
        )

    with col3:

        st.metric(
            "스크린수",
            f"{int(first_movie['scrnCnt']):,}개"
        )


# --------------------------------------------------
# 관객수 상위 5편 그래프
# --------------------------------------------------

st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)

# 영화명을 그래프의 이름으로 사용합니다.
top5_chart = top5.set_index(
    "movieNm"
)[["audiCnt"]]

st.bar_chart(top5_chart)


# --------------------------------------------------
# 전체 박스오피스 표
# --------------------------------------------------

st.subheader("🎞️ 전체 박스오피스")


# 표에 사용할 데이터만 복사합니다.
table_df = df[
    [
        "rank",
        "rankInten",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# --------------------------------------------------
# 순위 증감 표시
# --------------------------------------------------
# rankInten이 양수면 순위가 오른 것입니다.
# rankInten이 음수면 순위가 내린 것입니다.
#
# 예:
# 3 → 1위가 되었다면 rankInten = 2
# 1 → 3위가 되었다면 rankInten = -2

def make_rank_change(value):

    value = int(value)

    if value > 0:
        return f"🔺 {value}"

    elif value < 0:
        return f"🔻 {abs(value)}"

    else:
        return "-"


table_df["순위변동"] = table_df[
    "rankInten"
].apply(make_rank_change)


# --------------------------------------------------
# 영화명에 트로피 표시
# --------------------------------------------------
# 누적관객이 100만 명을 넘은 영화는
# 영화명 옆에 🏆를 붙입니다.

def make_movie_name(row):

    movie_name = row["movieNm"]

    if row["audiAcc"] > 1_000_000:
        return f"{movie_name} 🏆"

    return movie_name


table_df["영화명"] = table_df.apply(
    make_movie_name,
    axis=1
)


# --------------------------------------------------
# 표의 열 이름을 한글로 변경
# --------------------------------------------------

table_df = table_df[
    [
        "rank",
        "순위변동",
        "영화명",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


table_df.columns = [
    "순위",
    "순위변동",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# --------------------------------------------------
# 숫자를 보기 좋게 천 단위 쉼표로 표시
# --------------------------------------------------

table_df["관객수"] = table_df[
    "관객수"
].map(
    lambda x: f"{int(x):,}"
)


table_df["누적관객"] = table_df[
    "누적관객"
].map(
    lambda x: f"{int(x):,}"
)


table_df["스크린수"] = table_df[
    "스크린수"
].map(
    lambda x: f"{int(x):,}"
)


# --------------------------------------------------
# 표 출력
# --------------------------------------------------

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# 순위변동 안내
# --------------------------------------------------

st.caption(
    "🔺 숫자: 전날보다 순위 상승 · "
    "🔻 숫자: 전날보다 순위 하락 · "
    "🏆 누적관객 100만 명 초과"
)


# --------------------------------------------------
# 데이터 출처
# --------------------------------------------------

st.caption(
    "데이터 출처: KOBIS 영화관입장권통합전산망 "
    "일별 박스오피스 Open API"
)
