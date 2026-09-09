import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.caption("KOBIS 영화관입장권통합전산망 기준")


# --------------------------------------------------
# 한국 시간 기준으로 '어제' 날짜 계산
# --------------------------------------------------
# 서버가 해외에 있어도 한국 시간을 기준으로 계산합니다.

KOREA_TZ = ZoneInfo("Asia/Seoul")

now_korea = datetime.now(KOREA_TZ)
yesterday = now_korea.date() - timedelta(days=1)

# KOBIS API에서 사용하는 날짜 형식: YYYYMMDD
target_date = yesterday.strftime("%Y%m%d")

# 화면에 보여 줄 날짜 형식
display_date = yesterday.strftime("%Y년 %m월 %d일")


# --------------------------------------------------
# KOBIS API에서 데이터 가져오기
# --------------------------------------------------

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    """
    KOBIS 일별 박스오피스 데이터를 가져옵니다.

    ttl=3600:
    같은 날짜의 결과를 약 1시간 동안 기억해서
    API를 불필요하게 반복 호출하지 않습니다.
    """

    # Streamlit Secrets에서 인증키를 가져옵니다.
    # 실제 인증키를 코드에 직접 적지 않습니다.
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

    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류가 발생했는지 확인
        response.raise_for_status()

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
    # 인증키가 틀린 경우
    # --------------------------------------------------
    # KOBIS는 인증키가 잘못되어도 HTTP 상태코드가 200일 수 있습니다.
    # 따라서 faultInfo가 있는지도 반드시 확인합니다.

    if "faultInfo" in data:
        fault = data["faultInfo"]

        fault_code = fault.get("faultCode", "알 수 없음")
        fault_string = fault.get("message", "알 수 없는 오류")

        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 코드: {fault_code}\n"
                f"오류 내용: {fault_string}\n\n"
                "Streamlit Secrets의 KOBIS_KEY가 정확한지 "
                "확인해 주세요."
            )
        }

    # --------------------------------------------------
    # boxOfficeResult가 있는지 확인
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
    movie_list = boxoffice.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "message": (
                f"{target_dt} 날짜의 박스오피스 영화 목록이 없습니다.\n\n"
                "KOBIS에서 해당 날짜의 집계 데이터가 제공되는지 "
                "확인해 주세요."
            )
        }

    return {
        "success": True,
        "data": movie_list
    }


# --------------------------------------------------
# API 실행
# --------------------------------------------------

result = get_boxoffice(target_date)


# --------------------------------------------------
# API 오류가 발생한 경우
# --------------------------------------------------

if not result["success"]:
    st.error(result["message"])
    st.info(
        "확인할 항목: KOBIS_KEY → KOBIS API 상태 → "
        "조회 날짜의 집계 여부"
    )

    # 오류가 있으면 아래의 그래프와 표를 만들지 않습니다.
    st.stop()


# --------------------------------------------------
# 데이터프레임 만들기
# --------------------------------------------------

movies = result["data"]

df = pd.DataFrame(movies)


# --------------------------------------------------
# 숫자로 변환
# --------------------------------------------------
# KOBIS API의 숫자 값은 문자열로 전달되므로
# 정렬과 그래프를 위해 숫자형으로 변환합니다.

number_columns = [
    "rank",
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


# 순위 기준으로 정렬
df = df.sort_values("rank").reset_index(drop=True)


# --------------------------------------------------
# 조회 날짜 표시
# --------------------------------------------------

st.subheader(f"📅 {display_date} 박스오피스")


# --------------------------------------------------
# 1위 영화 정보
# --------------------------------------------------

if len(df) > 0:

    first_movie = df.iloc[0]

    st.markdown(
        f"## 🥇 1위: {first_movie['movieNm']}"
    )

    # 지표 카드 3개
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

# 영화명을 그래프의 인덱스로 사용합니다.
top5_chart = top5.set_index("movieNm")[["audiCnt"]]

st.bar_chart(top5_chart)


# --------------------------------------------------
# 전체 박스오피스 표
# --------------------------------------------------

st.subheader("🎞️ 전체 박스오피스")

# 사용자에게 보여 줄 열만 선택하고
# 이해하기 쉬운 한글 이름으로 변경합니다.

table_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()

table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# 숫자를 보기 좋게 천 단위 쉼표로 표시합니다.
table_df["관객수"] = table_df["관객수"].map(
    lambda x: f"{int(x):,}"
)

table_df["누적관객"] = table_df["누적관객"].map(
    lambda x: f"{int(x):,}"
)

table_df["스크린수"] = table_df["스크린수"].map(
    lambda x: f"{int(x):,}"
)


# 표 출력
st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)


# --------------------------------------------------
# 데이터 출처
# --------------------------------------------------

st.caption(
    "데이터 출처: KOBIS 영화관입장권통합전산망 "
    "일별 박스오피스 Open API"
)
