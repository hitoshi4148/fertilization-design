"""
NASA POWER API から月別気温（T2M）を取得する。
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Tuple
import json
import urllib.error
import urllib.parse
import urllib.request

POWER_MONTHLY_URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"
DEFAULT_TIMEOUT_SEC = 30


class NasaPowerError(Exception):
    """NASA POWER API の取得・解析に失敗した場合。"""


def last_calendar_year() -> int:
    """昨年（暦年）を返す。例: 2026年実行 → 2025。"""
    return datetime.now().year - 1


def fetch_monthly_t2m_celsius(
    latitude: float,
    longitude: float,
    year: int | None = None,
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> Tuple[List[float], int]:
    """
    指定地点・年の月別平均気温（℃）12件を返す。

    Returns:
        (12ヶ月分の気温, 使用した年)
    """
    if year is None:
        year = last_calendar_year()

    params = urllib.parse.urlencode({
        "parameters": "T2M",
        "community": "AG",
        "longitude": f"{longitude:.4f}",
        "latitude": f"{latitude:.4f}",
        "start": str(year),
        "end": str(year),
        "format": "JSON",
    })
    url = f"{POWER_MONTHLY_URL}?{params}"

    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise NasaPowerError(f"NASA POWER API への接続に失敗しました: {exc}") from exc

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise NasaPowerError("NASA POWER API の応答が JSON として解釈できません。") from exc

    temps = _parse_monthly_t2m(data, year)
    if len(temps) != 12:
        raise NasaPowerError(
            f"月別気温データが12ヶ月分揃いません（取得: {len(temps)} 件）。"
        )
    return temps, year


def _parse_monthly_t2m(data: dict, year: int) -> List[float]:
    """POWER Monthly JSON から T2M の12ヶ月分を抽出。"""
    try:
        param = data["properties"]["parameter"]["T2M"]
    except (KeyError, TypeError) as exc:
        raise NasaPowerError("応答に T2M パラメータが含まれていません。") from exc

    if not isinstance(param, dict):
        raise NasaPowerError("T2M データの形式が不正です。")

    temps: List[float] = []
    for month in range(1, 13):
        key = f"{year}{month:02d}"
        if key not in param:
            # フォールバック: 数値キーや YYYYMM 以外の並び
            alt_keys = [k for k in param if str(k).startswith(str(year))]
            if len(alt_keys) >= 12:
                sorted_keys = sorted(alt_keys, key=lambda k: str(k))[:12]
                return [_to_float(param[k]) for k in sorted_keys]
            raise NasaPowerError(f"月別キー {key} が見つかりません。")
        value = _to_float(param[key])
        if value is None:
            raise NasaPowerError(f"{key} の気温値が無効です。")
        temps.append(value)

    return temps


def _to_float(value) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v < -900:
        return None
    return v
