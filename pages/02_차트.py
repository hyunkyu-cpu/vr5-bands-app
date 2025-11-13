"""
차트 페이지 - TQQQ 6개월 종가 차트
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import traceback


# 페이지 설정
st.set_page_config(
    page_title="TQQQ 차트",
    page_icon="📈",
    layout="wide"
)


def get_historical_data(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """
    yfinance로 과거 데이터 조회

    Args:
        ticker: 티커 심볼
        period: 조회 기간 (기본값: 6개월)

    Returns:
        과거 데이터 DataFrame

    Raises:
        Exception: 데이터 조회 실패 시
    """
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period=period)

        if data.empty:
            raise Exception(f"{ticker} 데이터를 가져올 수 없습니다.")

        return data

    except Exception as e:
        raise Exception(f"과거 데이터 조회 실패: {str(e)}")


# 타이틀
st.title("📈 TQQQ 차트")
st.markdown("**최근 6개월 종가 추이**")
st.divider()


# 티커 입력
ticker = st.text_input(
    "티커 입력",
    value="TQQQ",
    help="차트를 볼 티커를 입력하세요"
)

# 차트 표시
if st.button("📊 차트 불러오기", type="primary"):
    try:
        with st.spinner(f"{ticker} 데이터 불러오는 중..."):
            # 과거 데이터 조회
            hist_data = get_historical_data(ticker, period="6mo")

        st.success(f"✅ {ticker} 데이터를 성공적으로 불러왔습니다!")

        # 종가 데이터 추출
        close_data = hist_data[['Close']].copy()
        close_data.index = close_data.index.tz_localize(None)  # 타임존 제거 (차트 표시용)

        # 라인 차트 출력
        st.subheader(f"{ticker} 종가 (최근 6개월)")
        st.line_chart(close_data['Close'])

        # 통계 정보
        st.divider()
        st.subheader("📊 통계 정보")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("현재가", f"${close_data['Close'].iloc[-1]:,.2f}")

        with col2:
            st.metric("6개월 최고가", f"${close_data['Close'].max():,.2f}")

        with col3:
            st.metric("6개월 최저가", f"${close_data['Close'].min():,.2f}")

        with col4:
            pct_change = ((close_data['Close'].iloc[-1] - close_data['Close'].iloc[0]) / close_data['Close'].iloc[0]) * 100
            st.metric("6개월 변동률", f"{pct_change:+.2f}%")

        # 상세 데이터 테이블
        st.divider()
        st.subheader("📋 최근 30일 종가 데이터")

        recent_data = close_data.tail(30).copy()
        recent_data.index.name = '날짜'
        recent_data = recent_data.rename(columns={'Close': '종가 ($)'})
        recent_data['종가 ($)'] = recent_data['종가 ($)'].round(2)

        st.dataframe(
            recent_data.sort_index(ascending=False),
            use_container_width=True
        )

    except Exception as e:
        st.error(f"❌ 오류 발생: {str(e)}")
        st.error("**해결 방법:**\n- 네트워크 연결 확인\n- 티커 심볼이 정확한지 확인\n- 잠시 후 다시 시도")

        with st.expander("🔍 상세 오류 정보"):
            st.code(traceback.format_exc())

else:
    st.info("👆 티커를 입력하고 '차트 불러오기' 버튼을 눌러주세요")


# 푸터
st.divider()
st.caption("🚀 VR 5.0 TQQQ 리밸런싱 도우미 | 차트 페이지")
