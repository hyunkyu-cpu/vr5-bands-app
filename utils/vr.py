"""
VR 5.0 리밸런싱 계산 로직
라오어 변동성 리밸런싱 알고리즘 구현
"""

from __future__ import annotations
import math
from typing import Dict, List
from dataclasses import dataclass


def compute_values(
    price: float,
    shares: int,
    pool: float,
    v_prev: float,
    d: float,
    band: float,
    contrib: float
) -> Dict[str, float]:
    """
    VR 5.0 핵심 계산 수행

    Args:
        price: 현재 주가
        shares: 보유 주식 수
        pool: 현금 풀
        v_prev: 직전 목표 가치
        d: 분모 (공격성 조절 파라미터)
        band: 밴드폭 (±비율)
        contrib: 2주 적립금

    Returns:
        계산 결과 딕셔너리
        - pv: 현재 평가액
        - r: 상승률
        - v_next: 다음 목표 가치
        - low: 하단 밴드
        - high: 상단 밴드
    """
    # 현재 평가액
    pv = price * shares

    # 상승률 계산: r = 1 + (pool / V_prev) / d
    r = 1.0 + (pool / v_prev) / d

    # 다음 목표 가치: V_next = V_prev * r + contrib
    v_next = v_prev * r + contrib

    # 밴드 계산
    low = v_next * (1.0 - band)
    high = v_next * (1.0 + band)

    return {
        "pv": pv,
        "r": r,
        "v_next": v_next,
        "low": low,
        "high": high
    }


def decide_action(vals: Dict[str, float], price: float) -> Dict[str, any]:
    """
    매수/매도/홀드 판단

    Args:
        vals: compute_values()의 결과
        price: 현재 주가

    Returns:
        액션 정보 딕셔너리
        - action: "BUY" | "SELL" | "HOLD"
        - qty: 매수/매도 주수 (정수)
        - amount: 매수/매도 금액 (달러)
    """
    pv = vals["pv"]
    v_next = vals["v_next"]
    low = vals["low"]
    high = vals["high"]

    # 매수 조건: PV < low
    if pv < low:
        buy_amount = v_next - pv
        buy_qty = math.ceil(buy_amount / price)
        return {
            "action": "BUY",
            "qty": buy_qty,
            "amount": buy_amount
        }

    # 매도 조건: PV > high
    elif pv > high:
        sell_amount = pv - v_next
        sell_qty = math.floor(sell_amount / price)
        return {
            "action": "SELL",
            "qty": sell_qty,
            "amount": sell_amount
        }

    # 밴드 내: HOLD
    else:
        return {
            "action": "HOLD",
            "qty": 0,
            "amount": 0.0
        }


def format_action_badge(action_info: Dict[str, any]) -> str:
    """
    액션 정보를 한국어 배지 문자열로 변환

    Args:
        action_info: decide_action()의 결과

    Returns:
        "BUY N 주" | "SELL N 주" | "HOLD" 형식의 문자열
    """
    action = action_info["action"]
    qty = action_info["qty"]

    if action == "BUY":
        return f"BUY {qty} 주"
    elif action == "SELL":
        return f"SELL {qty} 주"
    else:
        return "HOLD"


@dataclass
class Inputs:
    """VR 계산 입력값"""
    price: float
    shares: int
    pool: float
    V_prev: float
    d: float
    band: float
    contrib: float


def project_path(V_start: float, r: float, contrib: float, band: float, steps: int) -> List[dict]:
    """
    향후 n사이클의 V 경로와 밴드를 프로젝션

    Args:
        V_start: 시작 목표 가치 (V_next)
        r: 상승률
        contrib: 2주 적립금
        band: 밴드폭
        steps: 프로젝션할 사이클 수

    Returns:
        프로젝션 결과 리스트
        - step: 사이클 번호 (1부터 시작)
        - V: 목표 가치
        - low: 하단 밴드
        - high: 상단 밴드
    """
    out = []
    V = V_start

    for i in range(steps):
        V = V * r + contrib
        out.append({
            "step": i + 1,
            "V": V,
            "low": V * (1 - band),
            "high": V * (1 + band)
        })

    return out
