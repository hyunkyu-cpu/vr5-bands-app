"""
안정적인 가격 조회 유틸리티
yfinance의 불안정성을 해결하고 Timestamp 통일
"""

from __future__ import annotations
import pandas as pd
import datetime as dt
import yfinance as yf


def _to_ts(x) -> pd.Timestamp:
    """
    문자열/파이썬 datetime/pandas Timestamp 무엇이 오든 UTC naive Timestamp로 통일

    Args:
        x: 날짜/시간 객체

    Returns:
        pd.Timestamp (timezone-naive)
    """
    if isinstance(x, pd.Timestamp):
        return x.tz_convert(None) if x.tzinfo is not None else x

    try:
        # 파이썬 datetime
        if isinstance(x, (dt.datetime, dt.date)):
            x = pd.Timestamp(x)
        else:
            x = pd.to_datetime(x, errors="coerce")

        if x is pd.NaT:
            return pd.Timestamp.utcnow().tz_localize(None)

        return x.tz_convert(None) if x.tzinfo is not None else x

    except Exception:
        return pd.Timestamp.utcnow().tz_localize(None)


def fetch_last_price(ticker: str) -> tuple[float, pd.Timestamp]:
    """
    안정적으로 마지막 가격과 타임스탬프를 돌려준다.
    우선순위: 1분봉 5일 → 1일봉 10일 → fast_info → history()

    Args:
        ticker: 티커 심볼 (예: TQQQ)

    Returns:
        (price: float, ts: pd.Timestamp)

    Raises:
        RuntimeError: 모든 방법으로 가격 조회 실패 시
    """
    price = None
    ts = None

    # 방법 1) 1분봉 5일
    try:
        df = yf.download(ticker, period="5d", interval="1m", progress=False, threads=False)
        if df is not None and not df.empty:
            price = float(df["Close"].iloc[-1])
            ts = _to_ts(df.index[-1])
            return price, ts
    except Exception:
        pass

    # 방법 2) 일봉 10일
    if price is None:
        try:
            df = yf.download(ticker, period="10d", interval="1d", progress=False, threads=False)
            if df is not None and not df.empty:
                price = float(df["Close"].iloc[-1])
                ts = _to_ts(df.index[-1])
                return price, ts
        except Exception:
            pass

    # 방법 3) fast_info
    if price is None:
        try:
            tk = yf.Ticker(ticker)
            fi = tk.fast_info
            p = fi.get("last_price") or fi.get("lastPrice")
            if p:
                price = float(p)
                ts = _to_ts(pd.Timestamp.utcnow())
                return price, ts
        except Exception:
            pass

    # 방법 4) history() 백업
    if price is None:
        try:
            tk = yf.Ticker(ticker)
            df = tk.history(period="5d", interval="1d")
            if df is not None and not df.empty:
                price = float(df["Close"].iloc[-1])
                ts = _to_ts(df.index[-1])
                return price, ts
        except Exception:
            pass

    if price is None:
        raise RuntimeError(f"{ticker} 가격 조회 실패: 모든 방법 시도 실패")

    return price, ts


def future_dates(base_ts: pd.Timestamp, steps: int, step_days: int = 14) -> list[pd.Timestamp]:
    """
    미래 날짜 생성 (프로젝션용)

    Args:
        base_ts: 기준 시각
        steps: 생성할 날짜 수
        step_days: 간격 (일)

    Returns:
        pd.Timestamp 리스트
    """
    base_ts = pd.Timestamp(base_ts)
    base_ts = base_ts.tz_localize(None) if base_ts.tzinfo is not None else base_ts

    return [base_ts + pd.Timedelta(days=step_days * (i + 1)) for i in range(steps)]
