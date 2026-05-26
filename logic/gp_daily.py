"""
緯度ベースの日次 GP モデル（正弦波気温 + 芝種別応答関数）。

UI（app.py）で使用中の算出式を logic 層に集約する。
"""

from __future__ import annotations

import math
from typing import Dict, List

MONTHS_LABEL = [
    "1月", "2月", "3月", "4月", "5月", "6月",
    "7月", "8月", "9月", "10月", "11月", "12月",
]

_MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

GP_TURF_LABELS = {
    "寒地型芝": "寒地型GP",
    "暖地型芝": "暖地型GP",
    "日本芝": "日本芝GP",
}


def estimate_temperature(day: int, latitude: float) -> float:
    """緯度から仮想的な年間気温カーブを生成する。"""
    t_mean = 36.0 - 0.6 * latitude
    amplitude = 0.35 * latitude - 2.5
    phase = 121
    return t_mean + amplitude * math.sin(2 * math.pi * (day - phase) / 365)


def gp_cool(temp: float) -> float:
    """寒地型芝の GP（気温応答関数）"""
    if temp <= 0:
        return 0.0
    if temp <= 20:
        return temp / 20.0
    if temp < 35:
        return (35.0 - temp) / 15.0
    return 0.0


def gp_warm(temp: float) -> float:
    """暖地型芝の GP（気温応答関数）"""
    if temp <= 10:
        return 0.0
    if temp <= 30:
        return (temp - 10.0) / 20.0
    if temp < 45:
        return (45.0 - temp) / 15.0
    return 0.0


def weight_cool(temp: float) -> float:
    """WOS 時の寒地型寄与率 w(T)"""
    if temp <= 12:
        return 1.0
    if temp < 22:
        return (22.0 - temp) / 10.0
    return 0.0


def calculate_daily_gp(latitude: float, turf_type: str) -> List[float]:
    """365 日分の GP を算出する。"""
    daily_gp: List[float] = []
    for day in range(1, 366):
        temp = estimate_temperature(day, latitude)
        if turf_type == "寒地型芝":
            gp = gp_cool(temp)
        elif turf_type in ("暖地型芝", "日本芝"):
            gp = gp_warm(temp)
        elif turf_type == "ウィンターオーバーシード（WOS）":
            w = weight_cool(temp)
            gp = w * gp_cool(temp) + (1 - w) * gp_warm(temp)
        else:
            gp = 0.0
        daily_gp.append(gp)
    return daily_gp


def monthly_gp_averages(daily_gp: List[float]) -> Dict[str, float]:
    """365 日分の GP を月別平均に集約する（キー \"1\"〜\"12\"）。"""
    monthly: Dict[str, float] = {}
    start = 0
    for m, days in enumerate(_MONTH_DAYS, 1):
        end = start + days
        monthly[str(m)] = sum(daily_gp[start:end]) / days
        start = end
    return monthly


def gp_values_and_ratios(monthly_gp: Dict[str, float]) -> tuple[List[float], List[float]]:
    """月別 GP リストと正規化配分比率を返す。"""
    gp_values = [monthly_gp[str(m)] for m in range(1, 13)]
    gp_sum = sum(gp_values)
    ratios = [v / gp_sum for v in gp_values] if gp_sum > 0 else [1.0 / 12] * 12
    return gp_values, ratios


def build_gp_chart_series(latitude: float, turf_type: str) -> Dict[str, List[float]]:
    """GP グラフ用の系列名 → 12ヶ月分の値。"""
    daily = calculate_daily_gp(latitude, turf_type)
    monthly = monthly_gp_averages(daily)

    if turf_type == "ウィンターオーバーシード（WOS）":
        monthly_cool = monthly_gp_averages(calculate_daily_gp(latitude, "寒地型芝"))
        monthly_warm = monthly_gp_averages(calculate_daily_gp(latitude, "暖地型芝"))
        return {
            "寒地型GP": [monthly_cool[str(m)] for m in range(1, 13)],
            "暖地型GP": [monthly_warm[str(m)] for m in range(1, 13)],
            "WOS（合成GP）": [monthly[str(m)] for m in range(1, 13)],
        }

    label = GP_TURF_LABELS.get(turf_type, turf_type)
    return {label: [monthly[str(m)] for m in range(1, 13)]}
