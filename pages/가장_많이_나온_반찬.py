import streamlit as st
import requests
import re
from collections import Counter
import plotly.express as px
import pandas as pd
from datetime import datetime, date

st.set_page_config(page_title="송탄고 가장 많이 나온 반찬 TOP 5", layout="wide")

st.title("🍱 송탄고등학교 - 가장 많이 나온 반찬 TOP 5")

# Streamlit Secrets에서 NEIS API 키 불러오기
api_key = st.secrets.get("NEIS_API_KEY")

if not api_key:
    st.error("Streamlit Secrets에 'NEIS_API_KEY'가 설정되어 있지 않습니다.")
    st.stop()

# 사이드바에서 날짜 범위 입력받기
st.sidebar.header("📅 조회 기간 설정")
default_start = date(2025, 9, 1)
default_end = date(2026, 9, 30)

date_range = st.sidebar.date_input(
    "조회할 기간을 선택하세요",
    value=(default_start, default_end),
    min_value=date(2020, 1, 1),
    max_value=date(2030, 12, 31)
)

# 날짜가 범위로 올바르게 선택되었는지 확인
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date_obj, end_date_obj = date_range
else:
    st.info("사이드바에서 시작일과 종료일을 모두 선택해 주세요.")
    st.stop()

start_ymd = start_date_obj.strftime("%Y%m%d")
end_ymd = end_date_obj.strftime("%Y%m%d")

st.caption(f"조회 기간: **{start_date_obj.strftime('%Y년 %m월 %d일')} ~ {end_date_obj.strftime('%Y년 %m월 %d일')}** (중식 기준)")

# 송탄고등학교 기본 정보 (경기도교육청: J10, 행정표준코드: 7530188)
ATPT_OFCDC_SC_CODE = "J10"
SD_SCHUL_CODE = "7530188"

@st.cache_data(ttl=3600)
def fetch_all_meal_data(api_key, start_date, end_date):
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    pIndex = 1
    pSize = 100
    all_rows = []

    while True:
        params = {
            "KEY": api_key,
            "Type": "json",
            "pIndex": pIndex,
            "pSize": pSize,
            "ATPT_OFCDC_SC_CODE": ATPT_OFCDC_SC_CODE,
            "SD_SCHUL_CODE": SD_SCHUL_CODE,
            "MMEAL_SC_CODE": "2",  # 중식
            "MLSV_FROM_YMD": start_date,
            "MLSV_TO_YMD": end_date,
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if "mealServiceDietInfo" in data:
                rows = data["mealServiceDietInfo"][1]["row"]
                all_rows.extend(rows)

                # 전체 건수 확인 후 끝까지 수집했으면 반복 종료
                head = data["mealServiceDietInfo"][0]["head"]
                total_count = int(head[0]["list_total_count"])

                if len(all_rows) >= total_count:
                    break
                pIndex += 1
            else:
                break
        except Exception as e:
            st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
            break

    return all_rows

with st.spinner("NEIS API에서 급식 데이터를 불러오는 중입니다..."):
    meal_data = fetch_all_meal_data(api_key, start_ymd, end_ymd)

if not meal_data:
    st.warning("선택하신 기간에 조회된 급식 데이터가 없습니다. 사이드바에서 다른 기간을 선택해 보세요.")
else:
    # 날짜별 메뉴 중복 제거 처리 (같은 날 동일 메뉴 중복 카운트 방지)
    menu_dates = {}
    total_days = len({row["MLSV_YMD"] for row in meal_data})

    for row in meal_data:
        date_str = row["MLSV_YMD"]
        dish_string = row.get("DDISH_NM", "")

        # <br/> 기준 분리 및 알레르기 정보/특수문자 제거
        dishes = dish_string.split("<br/>")
        for dish in dishes:
            # 괄호 속 알레르기 번호 및 기타 표시 제거
            cleaned_dish = re.sub(r"\([^)]*\)", "", dish).strip()
            cleaned_dish = re.sub(r"[^\w\s가-힣]", "", cleaned_dish).strip()

            if cleaned_dish:
                if cleaned_dish not in menu_dates:
                    menu_dates[cleaned_dish] = set()
                menu_dates[cleaned_dish].add(date_str)

    # 메뉴별 등장 일수 계산
    menu_counts = Counter({dish: len(dates) for dish, dates in menu_dates.items()})

    # 상위 5개 메뉴 추출
    top5 = menu_counts.most_common(5)

    if top5:
        df_top5 = pd.DataFrame(top5, columns=["메뉴", "출석일수"])
        df_top5["비율(%)"] = ((df_top5["출석일수"] / total_days) * 100).round(1)

        # 파이 차트 시각화 (Plotly)
        fig = px.pie(
            df_top5,
            names="메뉴",
            values="출석일수",
            title=f"가장 많이 나온 반찬 TOP 5 (총 급식일수: {total_days}일)",
            color="출석일수",
            color_continuous_scale="Blues",
            hover_data=["비율(%)"],
        )

        fig.update_traces(
            textinfo="label+value",
            hovertemplate="<b>%{label}</b><br>제공 일수: %{value}일<br>제공 비율: %{customdata[0]}%",
            sort=False,  # 내림차순 순서 유지
            direction="clockwise"  # 시계 방향 배치
        )

        fig.update_layout(
            coloraxis_showscale=False,
            legend_title_text="메뉴",
            margin=dict(t=60, b=30, l=30, r=30)
        )

        # 주요 지표 및 차트 표시
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("📊 TOP 5 메뉴 요약")
            st.dataframe(
                df_top5,
                column_config={
                    "메뉴": "메뉴명",
                    "출석일수": st.column_config.NumberColumn("제공 일수", format="%d 일"),
                    "비율(%)": st.column_config.NumberColumn("비율", format="%.1f %%"),
                },
                hide_index=True,
                use_container_width=True
            )

        with col2:
            st.plotly_chart(fig, use_container_width=True)
