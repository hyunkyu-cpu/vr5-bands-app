"""
로그 관리 및 ICS 파일 생성 유틸리티
"""

import os
import csv
from datetime import datetime, timedelta
from typing import Dict
import pandas as pd
import pytz
from ics import Calendar, Event


def append_log(row: Dict[str, any], path: str = "data/vr_log.csv") -> None:
    """
    VR 리밸런싱 로그를 CSV 파일에 추가

    Args:
        row: 로그 행 데이터 딕셔너리
            - date: 날짜 (str)
            - price: 현재가 (float)
            - pv: 평가액 (float)
            - v_next: 다음 목표 가치 (float)
            - low: 하단 밴드 (float)
            - high: 상단 밴드 (float)
            - action: 액션 (str)
            - qty: 수량 (int)
            - amount: 금액 (float)
        path: CSV 파일 경로
    """
    # 파일이 없으면 헤더와 함께 생성
    file_exists = os.path.isfile(path)

    # 디렉토리가 없으면 생성
    os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(path, mode='a', newline='', encoding='utf-8') as f:
        fieldnames = ['date', 'price', 'pv', 'v_next', 'low', 'high', 'action', 'qty', 'amount']
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)


def read_log(path: str = "data/vr_log.csv") -> pd.DataFrame:
    """
    VR 리밸런싱 로그를 읽어 DataFrame으로 반환

    Args:
        path: CSV 파일 경로

    Returns:
        로그 데이터 DataFrame (파일이 없으면 빈 DataFrame)
    """
    if not os.path.isfile(path):
        # 파일이 없으면 빈 DataFrame 반환
        return pd.DataFrame(columns=['date', 'price', 'pv', 'v_next', 'low', 'high', 'action', 'qty', 'amount'])

    return pd.read_csv(path, encoding='utf-8')


def make_biweekly_ics(title: str = "VR 5.0 리밸런싱 점검", hours: int = 9) -> bytes:
    """
    2주 후 점검 일정을 ICS 파일로 생성

    Args:
        title: 일정 제목
        hours: 알림 시각 (KST 기준, 0-23)

    Returns:
        ICS 파일 바이트 데이터
    """
    # 현재 시각 (KST)
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)

    # 2주 후 날짜, 지정된 시각
    target_date = now + timedelta(days=14)
    target_datetime = target_date.replace(hour=hours, minute=0, second=0, microsecond=0)

    # 이벤트 생성
    calendar = Calendar()
    event = Event()
    event.name = title
    event.begin = target_datetime
    event.duration = timedelta(hours=1)  # 1시간 일정
    event.description = (
        "VR 5.0 TQQQ 리밸런싱 점검 시간입니다.\n"
        "현재가를 확인하고 매수/매도 여부를 결정하세요."
    )

    calendar.events.add(event)

    # ICS 파일 바이트로 반환
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
