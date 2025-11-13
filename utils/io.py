"""
로그 관리, 영구 저장 및 ICS 파일 생성 유틸리티
파일 기반 영구 저장으로 앱 재시작 후에도 데이터 유지
"""

from __future__ import annotations
import json
import os
import tempfile
import csv
import datetime as dt
from typing import Dict
import pandas as pd
import pytz
from ics import Calendar, Event
from datetime import datetime, timedelta


# 데이터 경로
DATA_DIR = "data"
STATE_PATH = os.path.join(DATA_DIR, "vr_state.json")
LOG_PATH = os.path.join(DATA_DIR, "vr_log.csv")
TRADES_PATH = os.path.join(DATA_DIR, "vr_trades.csv")


def ensure_data_dir():
    """데이터 디렉토리 생성"""
    os.makedirs(DATA_DIR, exist_ok=True)


def atomic_write_text(path: str, text: str):
    """
    원자적 파일 쓰기 (temp 파일 후 os.replace)

    Args:
        path: 대상 파일 경로
        text: 쓸 텍스트 내용
    """
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d if d else ".", prefix=".tmp_", text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def save_state(state: dict):
    """
    현재 상태를 JSON 파일로 저장

    Args:
        state: 저장할 상태 딕셔너리
    """
    ensure_data_dir()
    atomic_write_text(STATE_PATH, json.dumps(state, ensure_ascii=False, indent=2))


def load_state(defaults: dict) -> dict:
    """
    저장된 상태를 불러오거나 기본값 반환

    Args:
        defaults: 기본값 딕셔너리

    Returns:
        저장된 상태 또는 기본값
    """
    ensure_data_dir()
    if not os.path.exists(STATE_PATH):
        return defaults.copy()
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {**defaults, **data}
    except:
        return defaults.copy()


def append_log(row: dict):
    """
    VR 리밸런싱 권고 로그를 CSV 파일에 추가

    Args:
        row: 로그 행 데이터 딕셔너리
    """
    ensure_data_dir()
    header = [
        "date", "ticker", "price", "PV", "V_next", "band_low", "band_high",
        "action", "qty", "amount", "r", "band", "contrib", "pool", "shares", "d"
    ]

    # 헤더에 맞춰 데이터 정렬
    new = pd.DataFrame([row])[header]

    if os.path.exists(LOG_PATH):
        new.to_csv(LOG_PATH, mode="a", header=False, index=False, encoding="utf-8")
    else:
        new.to_csv(LOG_PATH, mode="w", header=True, index=False, encoding="utf-8")


def read_log() -> pd.DataFrame:
    """
    VR 리밸런싱 권고 로그를 읽어 DataFrame으로 반환

    Returns:
        로그 데이터 DataFrame (최신순 정렬)
    """
    ensure_data_dir()
    if not os.path.exists(LOG_PATH):
        return pd.DataFrame(columns=[
            "date", "ticker", "price", "PV", "V_next", "band_low", "band_high",
            "action", "qty", "amount", "r", "band", "contrib", "pool", "shares", "d"
        ])

    df = pd.read_csv(LOG_PATH, encoding="utf-8")
    if "date" in df.columns and len(df) > 0:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date", ascending=False)
    return df


def append_trade(side: str, qty: int, fill_price: float, note: str = ""):
    """
    체결 기록을 CSV 파일에 추가

    Args:
        side: 매수(BUY) 또는 매도(SELL)
        qty: 수량
        fill_price: 체결 가격
        note: 메모
    """
    ensure_data_dir()
    now = dt.datetime.now().isoformat(timespec="seconds")
    notional = float(qty) * float(fill_price)

    row = {
        "date": now,
        "side": side,
        "qty": int(qty),
        "fill_price": float(fill_price),
        "notional": notional,
        "note": note
    }

    header = ["date", "side", "qty", "fill_price", "notional", "note"]
    write_header = not os.path.exists(TRADES_PATH)

    with open(TRADES_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if write_header:
            w.writeheader()
        w.writerow(row)


def read_trades() -> pd.DataFrame:
    """
    체결 기록을 읽어 DataFrame으로 반환

    Returns:
        체결 기록 DataFrame (최신순 정렬)
    """
    ensure_data_dir()
    if not os.path.exists(TRADES_PATH):
        return pd.DataFrame(columns=["date", "side", "qty", "fill_price", "notional", "note"])

    df = pd.read_csv(TRADES_PATH, encoding="utf-8")
    if "date" in df.columns and len(df) > 0:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date", ascending=False)
    return df


def make_biweekly_ics(title: str = "VR 5.0 리밸런싱 점검", hours: int = 9) -> bytes:
    """
    2주 후 점검 일정을 ICS 파일로 생성

    Args:
        title: 일정 제목
        hours: 알림 시각 (KST 기준, 0-23)

    Returns:
        ICS 파일 바이트 데이터
    """
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)

    target_date = now + timedelta(days=14)
    target_datetime = target_date.replace(hour=hours, minute=0, second=0, microsecond=0)

    calendar = Calendar()
    event = Event()
    event.name = title
    event.begin = target_datetime
    event.duration = timedelta(hours=1)
    event.description = (
        "VR 5.0 TQQQ 리밸런싱 점검 시간입니다.\n"
        "현재가를 확인하고 매수/매도 여부를 결정하세요."
    )

    calendar.events.add(event)
    return calendar.serialize().encode('utf-8')


def get_csv_download_data(df: pd.DataFrame) -> bytes:
    """
    DataFrame을 CSV 바이트 데이터로 변환

    Args:
        df: DataFrame

    Returns:
        CSV 파일 바이트 데이터
    """
    return df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
