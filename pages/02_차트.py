"""
차트 페이지 - TQQQ 과거 가격 + 밴드 + 미래 프로젝션
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import traceback

from utils.vr import project_path
from utils.io import load_state


# 페이지 설정
st.set_page_config(
    page_title="TQQQ 차트 & 프로젝션",
    page_icon="📈",
    layout="wide"
)


def get_historical_data(ticker: str, period: str = "6mo") -> pd.DataFrame:
    """yfinance로 과거 데이터 조회"""
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period=period)

        if data.empty:
            raise Exception(f"{ticker} 데이터를 가져올 수 없습니다.")

        return data

    except Exception as e:
        raise Exception(f"과거 데이터 조회 실패: {str(e)}")


# 타이틀
st.title("📈 TQQQ 차트 & 프로젝션")
st.markdown("**과거 가격 + 현재 밴드 + 향후 n사이클 프로젝션**")
st.divider()


# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 차트 설정")

    ticker = st.text_input("티커", value="TQQQ")

    period_options = {"3개월": "3mo", "6개월": "6mo", "1년": "1y"}
    period_label = st.selectbox("히스토리 기간", list(period_options.keys()), index=1)
    period = period_options[period_label]

    projection_steps = st.slider("프로젝션 사이클 수", min_value=2, max_value=12, value=6, step=1)

    st.divider()
    st.info("💡 **프로젝션**\n\n향후 n사이클(2주 단위)의 목표 가치와 밴드를 점선으로 표시합니다.")


# 저장된 상태 불러오기
DEFAULTS = {
    'ticker': 'TQQQ',
    'd': 11.0,
    'band': 0.15,
    'contrib': 0.0,
    'last_calc_result': None
}

state = load_state(DEFAULTS)

# 차트 생성 버튼
if st.button("📊 차트 생성", type="primary"):
    try:
        with st.spinner(f"{ticker} 데이터 불러오는 중..."):
            # 1. 과거 데이터 조회
            hist_data = get_historical_data(ticker, period=period)

        st.success(f"✅ {ticker} 데이터를 성공적으로 불러왔습니다!")

        # 2. 종가 데이터 추출
        close_data = hist_data[['Close']].copy()
        close_data.index = close_data.index.tz_localize(None)  # 타임존 제거

        # 3. Plotly Figure 생성
        fig = go.Figure()

        # 과거 가격 라인
        fig.add_trace(go.Scatter(
            x=close_data.index,
            y=close_data['Close'],
            mode='lines',
            name=f'{ticker} 종가',
            line=dict(color='blue', width=2)
        ))

        # 4. 현재 밴드 및 V_next (저장된 계산 결과가 있을 경우)
        last_calc = state.get('last_calc_result')
        if last_calc and 'vals' in last_calc:
            vals = last_calc['vals']
            v_next = vals.get('v_next')
            low = vals.get('low')
            high = vals.get('high')

            if v_next and low and high:
                # 현재 시점
                now = datetime.now()

                # V_next 수평선
                fig.add_trace(go.Scatter(
                    x=[close_data.index[0], now],
                    y=[v_next, v_next],
                    mode='lines',
                    name='V_next (목표)',
                    line=dict(color='green', width=2, dash='solid')
                ))

                # 하단 밴드
                fig.add_trace(go.Scatter(
                    x=[close_data.index[0], now],
                    y=[low, low],
                    mode='lines',
                    name='하단 밴드',
                    line=dict(color='red', width=2, dash='solid')
                ))

                # 상단 밴드
                fig.add_trace(go.Scatter(
                    x=[close_data.index[0], now],
                    y=[high, high],
                    mode='lines',
                    name='상단 밴드',
                    line=dict(color='orange', width=2, dash='solid')
                ))

                # 5. 미래 프로젝션
                r = vals.get('r', 1.0)
                band_val = state.get('band', 0.15)
                contrib = state.get('contrib', 0.0)

                projection = project_path(v_next, r, contrib, band_val, projection_steps)

                # 미래 날짜 생성 (14일 = 2주 단위)
                future_dates = [now + timedelta(days=14 * i) for i in range(1, projection_steps + 1)]

                # V 경로 (점선)
                fig.add_trace(go.Scatter(
                    x=future_dates,
                    y=[p['V'] for p in projection],
                    mode='lines+markers',
                    name='V 프로젝션',
                    line=dict(color='green', width=2, dash='dash'),
                    marker=dict(size=6)
                ))

                # 하단 밴드 프로젝션 (점선)
                fig.add_trace(go.Scatter(
                    x=future_dates,
                    y=[p['low'] for p in projection],
                    mode='lines+markers',
                    name='하단 밴드 프로젝션',
                    line=dict(color='red', width=2, dash='dash'),
                    marker=dict(size=4)
                ))

                # 상단 밴드 프로젝션 (점선)
                fig.add_trace(go.Scatter(
                    x=future_dates,
                    y=[p['high'] for p in projection],
                    mode='lines+markers',
                    name='상단 밴드 프로젝션',
                    line=dict(color='orange', width=2, dash='dash'),
                    marker=dict(size=4)
                ))

        # 레이아웃 설정
        fig.update_layout(
            title=f"{ticker} 가격 및 VR 밴드 프로젝션",
            xaxis_title="날짜",
            yaxis_title="가격 / 목표 가치 ($)",
            hovermode='x unified',
            template='plotly_white',
            height=600
        )

        # 차트 표시
        st.plotly_chart(fig, use_container_width=True)

        # 통계 정보
        st.divider()
        st.subheader("📊 통계 정보")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("현재가", f"${close_data['Close'].iloc[-1]:,.2f}")

        with col2:
            st.metric(f"{period_label} 최고가", f"${close_data['Close'].max():,.2f}")

        with col3:
            st.metric(f"{period_label} 최저가", f"${close_data['Close'].min():,.2f}")

        with col4:
            pct_change = ((close_data['Close'].iloc[-1] - close_data['Close'].iloc[0]) / close_data['Close'].iloc[0]) * 100
            st.metric(f"{period_label} 변동률", f"{pct_change:+.2f}%")

        # 프로젝션 테이블
        if last_calc and 'vals' in last_calc:
            st.divider()
            st.subheader("📋 프로젝션 상세")

            proj_df = pd.DataFrame(projection)
            proj_df['date'] = future_dates
            proj_df = proj_df[['step', 'date', 'V', 'low', 'high']]
            proj_df['date'] = proj_df['date'].dt.strftime('%Y-%m-%d')
            proj_df['V'] = proj_df['V'].round(2)
            proj_df['low'] = proj_df['low'].round(2)
            proj_df['high'] = proj_df['high'].round(2)

            proj_df.columns = ['사이클', '날짜', 'V (목표)', '하단 밴드', '상단 밴드']

            st.dataframe(proj_df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"❌ 오류 발생: {str(e)}")
        st.error("**해결 방법:**\n- 네트워크 연결 확인\n- 티커 심볼이 정확한지 확인\n- 먼저 메인 페이지에서 계산을 수행하세요 (밴드 정보 필요)")

        with st.expander("🔍 상세 오류 정보"):
            st.code(traceback.format_exc())

else:
    st.info("👆 '차트 생성' 버튼을 눌러주세요")
    st.warning("⚠️ **주의**: 밴드와 프로젝션을 표시하려면 먼저 메인 페이지에서 계산을 수행해야 합니다.")


# 푸터
st.divider()
st.caption("🚀 VR 5.0 TQQQ 리밸런싱 도우미 | 차트 & 프로젝션 페이지")
