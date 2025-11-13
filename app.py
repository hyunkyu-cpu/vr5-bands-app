"""
VR 5.0 TQQQ 리밸런싱 도우미 (격주)
Streamlit 메인 애플리케이션 - 영구 저장 및 매수/매도 로그 기능
"""

import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import traceback

from utils.vr import compute_values, decide_action, format_action_badge, project_path
from utils.io import (
    save_state, load_state, append_log, read_log,
    append_trade, read_trades, make_biweekly_ics, get_csv_download_data
)


# 페이지 설정
st.set_page_config(
    page_title="VR 5.0 TQQQ 리밸런싱 도우미",
    page_icon="📊",
    layout="wide"
)


# 기본값 정의
DEFAULTS = {
    'ticker': 'TQQQ',
    'shares': 500,
    'pool': 10000.0,
    'v_prev': 25000.0,
    'd': 11.0,
    'band': 0.15,
    'contrib': 0.0,
    'current_price': None,
    'last_update': None,
    'last_calc_result': None
}


# 세션 상태 초기화 (영구 저장에서 불러오기)
if 'initialized' not in st.session_state:
    loaded = load_state(DEFAULTS)
    for key, value in loaded.items():
        st.session_state[key] = value
    st.session_state.initialized = True


def get_current_price(ticker: str) -> float:
    """yfinance로 현재 주가 조회"""
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period='1d')

        if data.empty:
            raise Exception(f"{ticker} 데이터를 가져올 수 없습니다.")

        return float(data['Close'].iloc[-1])

    except Exception as e:
        raise Exception(f"가격 조회 실패: {str(e)}")


# 타이틀
st.title("📊 VR 5.0 TQQQ 리밸런싱 도우미 (격주)")
st.markdown("**라오어 변동성 리밸런싱 전략 - 2주마다 점검 | 영구 저장 기능**")

# 실시간 가격 표시
ticker_for_price = st.session_state.get('ticker', 'TQQQ')

# 자동으로 가격 조회 (페이지 로드 시)
try:
    if st.session_state.current_price is None or st.session_state.last_update is None:
        with st.spinner(f"{ticker_for_price} 실시간 가격 조회 중..."):
            st.session_state.current_price = get_current_price(ticker_for_price)
            st.session_state.last_update = datetime.now()

    # 가격 표시
    col_price1, col_price2, col_price3 = st.columns([2, 2, 1])
    with col_price1:
        st.metric(
            label=f"{ticker_for_price} 실시간 가격",
            value=f"${st.session_state.current_price:,.2f}",
            delta=None
        )
    with col_price2:
        if st.session_state.last_update:
            time_str = st.session_state.last_update.strftime('%Y-%m-%d %H:%M:%S')
            st.caption(f"🕐 마지막 업데이트: {time_str}")
    with col_price3:
        if st.button("🔄 새로고침", type="secondary"):
            with st.spinner("가격 업데이트 중..."):
                st.session_state.current_price = get_current_price(ticker_for_price)
                st.session_state.last_update = datetime.now()
                st.rerun()

except Exception as e:
    st.warning(f"⚠️ 가격 조회 실패: {str(e)}")
    st.info("계산하기 버튼을 눌러 수동으로 가격을 조회할 수 있습니다.")

st.divider()


# 사이드바
with st.sidebar:
    st.header("⚙️ 설정")
    st.info("💡 **영구 저장**\n\n모든 입력값과 로그는 자동으로 저장되어 앱 재시작 후에도 유지됩니다.")
    st.divider()
    st.caption("📊 차트 페이지에서 과거 가격과 미래 프로젝션을 확인하세요!")


# 좌우 컬럼 레이아웃
col_left, col_right = st.columns([1, 1])

# 좌측 컬럼: 입력
with col_left:
    st.subheader("📝 입력 정보")

    # 기본 파라미터
    ticker = st.text_input(
        "티커",
        value=st.session_state.get('ticker', 'TQQQ'),
        help="기본값: TQQQ"
    )

    col1, col2 = st.columns(2)

    with col1:
        shares = st.number_input(
            "보유 수량 (주)",
            min_value=0,
            value=st.session_state.get('shares', 500),
            step=1,
            help="현재 보유한 주식 수"
        )

        v_prev = st.number_input(
            "직전 목표 Value ($)",
            min_value=0.0,
            value=st.session_state.get('v_prev', 25000.0),
            step=100.0,
            help="이전 리밸런싱 시점의 목표 가치"
        )

        band = st.number_input(
            "밴드폭 (±)",
            min_value=0.01,
            max_value=0.50,
            value=st.session_state.get('band', 0.15),
            step=0.01,
            format="%.2f",
            help="리밸런싱 밴드 비율 (기본값: 0.15 = ±15%)"
        )

    with col2:
        pool = st.number_input(
            "POOL 현금 ($)",
            min_value=0.0,
            value=st.session_state.get('pool', 10000.0),
            step=100.0,
            help="현재 보유 현금"
        )

        d = st.number_input(
            "분모 d (공격성)",
            min_value=1.0,
            value=st.session_state.get('d', 11.0),
            step=0.5,
            help="공격성 조절 파라미터 (기본값: 11)"
        )

        contrib = st.number_input(
            "2주 적립금 ($)",
            min_value=0.0,
            value=st.session_state.get('contrib', 0.0),
            step=100.0,
            help="2주간 추가 입금 예정 금액 (거치식은 0)"
        )

    st.divider()

    # 계산 버튼
    calculate_button = st.button("🧮 계산하기", type="primary", use_container_width=True)


# 우측 컬럼: 결과
with col_right:
    st.subheader("📈 계산 결과")

    if calculate_button:
        try:
            # 1. 현재가 조회
            with st.spinner(f"{ticker} 현재가 조회 중..."):
                current_price = get_current_price(ticker)

            st.success(f"✅ {ticker} 현재가: **${current_price:,.2f}**")

            # 2. 계산 수행
            vals = compute_values(
                price=current_price,
                shares=shares,
                pool=pool,
                v_prev=v_prev,
                d=d,
                band=band,
                contrib=contrib
            )

            action_info = decide_action(vals, current_price)
            action_badge = format_action_badge(action_info)

            # 3. 상태 저장 (영구 저장)
            state_to_save = {
                'ticker': ticker,
                'shares': shares,
                'pool': pool,
                'v_prev': v_prev,
                'd': d,
                'band': band,
                'contrib': contrib,
                'current_price': current_price,
                'last_update': datetime.now().isoformat(),
                'last_calc_result': {
                    'vals': vals,
                    'action_info': action_info
                }
            }
            save_state(state_to_save)
            st.session_state.update(state_to_save)

            # 4. 로그 저장
            log_row = {
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'ticker': ticker,
                'price': current_price,
                'PV': vals['pv'],
                'V_next': vals['v_next'],
                'band_low': vals['low'],
                'band_high': vals['high'],
                'action': action_info['action'],
                'qty': action_info['qty'],
                'amount': action_info['amount'],
                'r': vals['r'],
                'band': band,
                'contrib': contrib,
                'pool': pool,
                'shares': shares,
                'd': d
            }
            append_log(log_row)

            st.toast("✅ 자동 저장 완료!", icon="💾")

            # 5. 결과 표시 - 액션 배지
            st.divider()

            if action_info['action'] == 'BUY':
                st.success(f"### 🟢 {action_badge}")
            elif action_info['action'] == 'SELL':
                st.warning(f"### 🔴 {action_badge}")
            else:
                st.info(f"### ⚪ {action_badge}")

            # 6. 메트릭 카드
            st.divider()

            metric_col1, metric_col2, metric_col3 = st.columns(3)

            with metric_col1:
                st.metric("현재 평가액 (PV)", f"${vals['pv']:,.2f}")
                st.metric("하단 밴드", f"${vals['low']:,.2f}")

            with metric_col2:
                st.metric("다음 목표 (V_next)", f"${vals['v_next']:,.2f}")
                st.metric("상단 밴드", f"${vals['high']:,.2f}")

            with metric_col3:
                st.metric("상승률 (r)", f"{vals['r']:.4f}")
                if action_info['action'] != 'HOLD':
                    st.metric("거래 금액", f"${action_info['amount']:,.2f}")

            # 7. 상세 정보 테이블
            st.divider()
            st.markdown("#### 📋 상세 정보")

            result_df = pd.DataFrame({
                '항목': ['현재가', '보유 수량', '현재 평가액', '목표 가치', '하단 밴드', '상단 밴드', '액션', '수량', '금액'],
                '값': [
                    f"${current_price:,.2f}",
                    f"{shares} 주",
                    f"${vals['pv']:,.2f}",
                    f"${vals['v_next']:,.2f}",
                    f"${vals['low']:,.2f}",
                    f"${vals['high']:,.2f}",
                    action_info['action'],
                    f"{action_info['qty']} 주",
                    f"${action_info['amount']:,.2f}"
                ]
            })

            st.dataframe(result_df, use_container_width=True, hide_index=True)

            # 8. ICS 다운로드
            st.divider()

            try:
                ics_data = make_biweekly_ics()
                st.download_button(
                    label="📅 ICS 일정 다운로드 (2주 후 점검)",
                    data=ics_data,
                    file_name=f"vr_reminder_{datetime.now().strftime('%Y%m%d')}.ics",
                    mime="text/calendar",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"❌ ICS 생성 실패: {str(e)}")

        except Exception as e:
            st.error(f"❌ 오류 발생: {str(e)}")
            st.error("**해결 방법:**\n- 네트워크 연결 확인\n- 티커 심볼이 정확한지 확인\n- 잠시 후 다시 시도")

            with st.expander("🔍 상세 오류 정보"):
                st.code(traceback.format_exc())

    else:
        st.info("👈 좌측에 정보를 입력하고 '계산하기' 버튼을 눌러주세요")


# 하단: 체결 등록 폼
st.divider()
st.subheader("💼 체결 등록")

with st.expander("📝 실제 거래를 체결했을 때 기록하세요"):
    col_trade1, col_trade2, col_trade3, col_trade4 = st.columns(4)

    with col_trade1:
        trade_side = st.selectbox("거래 유형", ["BUY", "SELL"])

    with col_trade2:
        trade_qty = st.number_input("수량 (주)", min_value=1, value=1, step=1)

    with col_trade3:
        trade_price = st.number_input("체결 가격 ($)", min_value=0.01, value=100.0, step=0.01, format="%.2f")

    with col_trade4:
        trade_note = st.text_input("메모 (선택)", value="")

    if st.button("✅ 체결 기록 저장", type="primary"):
        try:
            append_trade(trade_side, trade_qty, trade_price, trade_note)
            st.success(f"✅ {trade_side} {trade_qty}주 @ ${trade_price:.2f} 체결 기록 저장 완료!")
            st.rerun()
        except Exception as e:
            st.error(f"❌ 체결 기록 저장 실패: {str(e)}")


# 하단: 권고표 (로그)
st.divider()
st.subheader("📜 리밸런싱 권고 로그")

try:
    log_df = read_log()

    if not log_df.empty:
        st.dataframe(log_df, use_container_width=True, hide_index=True)

        # CSV 다운로드
        csv_data = get_csv_download_data(log_df)

        st.download_button(
            label="📥 권고 로그 CSV 다운로드",
            data=csv_data,
            file_name=f"vr_log_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("아직 저장된 권고 로그가 없습니다. 계산 후 자동으로 저장됩니다.")

except Exception as e:
    st.warning(f"로그 불러오기 실패: {str(e)}")


# 하단: 체결표
st.divider()
st.subheader("📋 체결 기록")

try:
    trades_df = read_trades()

    if not trades_df.empty:
        st.dataframe(trades_df, use_container_width=True, hide_index=True)

        # CSV 다운로드
        trades_csv_data = get_csv_download_data(trades_df)

        st.download_button(
            label="📥 체결 기록 CSV 다운로드",
            data=trades_csv_data,
            file_name=f"vr_trades_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("아직 저장된 체결 기록이 없습니다. 실제 거래 후 '체결 등록'에서 기록하세요.")

except Exception as e:
    st.warning(f"체결 기록 불러오기 실패: {str(e)}")


# 푸터
st.divider()
st.caption("🚀 VR 5.0 TQQQ 리밸런싱 도우미 | 라오어 변동성 리밸런싱 전략 | 영구 저장 기능")
