"""
VR 5.0 TQQQ 리밸런싱 도우미 (격주)
Streamlit 메인 애플리케이션 - 영구 저장 및 매수/매도 로그 기능
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import traceback

from utils.vr import compute_values, decide_action, format_action_badge, project_path, generate_price_table
from utils.io import (
    save_state, load_state, append_log, read_log,
    append_trade, read_trades, make_biweekly_ics, get_csv_download_data
)
from utils.price import fetch_last_price


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


# 가격 조회 함수는 utils.price.fetch_last_price 사용


# 타이틀
st.title("📊 VR 5.0 TQQQ 리밸런싱 도우미 (격주)")
st.markdown("**라오어 변동성 리밸런싱 전략 - 2주마다 점검 | 영구 저장 기능**")

# 실시간 가격 표시
ticker_for_price = st.session_state.get('ticker', 'TQQQ')

# 자동으로 가격 조회 (페이지 로드 시)
try:
    if st.session_state.current_price is None or st.session_state.last_update is None:
        with st.spinner(f"{ticker_for_price} 실시간 가격 조회 중..."):
            price, price_ts = fetch_last_price(ticker_for_price)
            st.session_state.current_price = price
            st.session_state.last_update = str(price_ts)

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
            st.caption(f"🕐 기준시각: {st.session_state.last_update}")
    with col_price3:
        if st.button("🔄 새로고침", type="secondary"):
            with st.spinner("가격 업데이트 중..."):
                price, price_ts = fetch_last_price(ticker_for_price)
                st.session_state.current_price = price
                st.session_state.last_update = str(price_ts)
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
    calculate_button = st.button("🧮 계산하기", type="primary", width="stretch")


# 우측 컬럼: 결과
with col_right:
    st.subheader("📈 계산 결과")

    if calculate_button:
        try:
            # 1. 현재가 조회
            with st.spinner(f"{ticker} 현재가 조회 중..."):
                current_price, price_ts = fetch_last_price(ticker)

            st.success(f"✅ {ticker} 현재가: **${current_price:,.2f}** (기준: {price_ts})")

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

            st.dataframe(result_df, width="stretch", hide_index=True)

            # 8. ICS 다운로드
            st.divider()

            try:
                ics_data = make_biweekly_ics()
                st.download_button(
                    label="📅 ICS 일정 다운로드 (2주 후 점검)",
                    data=ics_data,
                    file_name=f"vr_reminder_{datetime.now().strftime('%Y%m%d')}.ics",
                    mime="text/calendar",
                    width="stretch"
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


# 하단: 예약 매매표
st.divider()
st.subheader("📋 예약 매매표 (가격대별 매수/매도 가이드)")

# 계산 결과가 있을 때만 표시
last_calc = st.session_state.get('last_calc_result')
if last_calc and 'vals' in last_calc:
    vals = last_calc['vals']
    current_price = st.session_state.get('current_price')
    shares = st.session_state.get('shares', 0)

    if current_price and shares > 0:
        # 사이드바 설정
        with st.expander("⚙️ 예약 매매표 설정"):
            col_set1, col_set2 = st.columns(2)

            with col_set1:
                price_step = st.number_input(
                    "가격 간격 ($)",
                    min_value=0.1,
                    max_value=10.0,
                    value=1.0,
                    step=0.1,
                    format="%.1f",
                    help="각 행의 가격 간격"
                )

            with col_set2:
                num_levels = st.number_input(
                    "위아래 단계 수",
                    min_value=5,
                    max_value=30,
                    value=10,
                    step=1,
                    help="현재 가격 기준 위아래 몇 단계씩 표시할지"
                )

        # 예약 매매표 생성
        price_table = generate_price_table(
            current_price=current_price,
            shares=shares,
            v_next=vals['v_next'],
            low=vals['low'],
            high=vals['high'],
            price_step=price_step,
            num_levels=num_levels
        )

        # DataFrame 변환
        price_df = pd.DataFrame(price_table)

        # 가격 내림차순 정렬 (높은 가격부터)
        price_df = price_df.sort_values('price', ascending=False).reset_index(drop=True)

        # 포맷팅
        price_df['가격'] = price_df['price'].apply(lambda x: f"${x:,.2f}")
        price_df['액션'] = price_df['action']
        price_df['수량'] = price_df['qty'].apply(lambda x: f"{x:,}" if x > 0 else "-")
        price_df['보유주식'] = price_df['total_shares'].apply(lambda x: f"{x:,}")
        price_df['평가액'] = price_df['pv'].apply(lambda x: f"${x:,.2f}")

        # 현재 가격 행 강조 표시를 위한 스타일링
        display_df = price_df[['가격', '액션', '수량', '보유주식', '평가액']].copy()

        # 현재 가격에 가장 가까운 행 찾기
        price_df['price_diff'] = abs(price_df['price'] - current_price)
        current_idx = price_df['price_diff'].idxmin()

        st.info(f"💡 **현재가: ${current_price:,.2f}** | 목표: ${vals['v_next']:,.2f} | 하단: ${vals['low']:,.2f} | 상단: ${vals['high']:,.2f}")

        # 테이블 표시
        st.dataframe(
            display_df,
            width="stretch",
            hide_index=True,
            height=600
        )

        # CSV 다운로드
        price_csv = display_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 예약 매매표 CSV 다운로드",
            data=price_csv,
            file_name=f"vr_price_table_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.warning("⚠️ 현재가와 보유 주식 정보가 필요합니다. 먼저 계산을 수행하세요.")
else:
    st.info("👆 먼저 계산하기 버튼을 눌러 VR 계산을 수행하세요.")


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
        st.dataframe(log_df, width="stretch", hide_index=True)

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
        st.dataframe(trades_df, width="stretch", hide_index=True)

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
