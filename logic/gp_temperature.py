"""
月別気温から GP を算出し、グラフ用の平滑曲線データを生成する。
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from .gp_daily import (
    GP_TURF_LABELS,
    MONTHS_LABEL,
    gp_cool,
    gp_warm,
    weight_cool,
)


def gp_from_temperature(temp: float, turf_type: str) -> float:
    """1時点の気温と芝種から GP（0〜1）を算出。"""
    if turf_type == "寒地型芝":
        return gp_cool(temp)
    if turf_type in ("暖地型芝", "日本芝"):
        return gp_warm(temp)
    if turf_type == "ウィンターオーバーシード（WOS）":
        w = weight_cool(temp)
        return w * gp_cool(temp) + (1.0 - w) * gp_warm(temp)
    return 0.0


def monthly_gp_from_temperatures(
    monthly_temps: List[float],
    turf_type: str,
) -> Dict[str, float]:
    """12ヶ月の平均気温から月別 GP を算出（キー \"1\"〜\"12\"）。"""
    if len(monthly_temps) != 12:
        raise ValueError("monthly_temps は12要素である必要があります。")
    return {
        str(m + 1): round(gp_from_temperature(monthly_temps[m], turf_type), 4)
        for m in range(12)
    }


def build_gp_chart_series_from_temps(
    monthly_temps: List[float],
    turf_type: str,
) -> Dict[str, List[float]]:
    """NASA 月別気温ベースの GP 系列（グラフ・表用の12点）。"""
    if turf_type == "ウィンターオーバーシード（WOS）":
        cool = [gp_from_temperature(t, "寒地型芝") for t in monthly_temps]
        warm = [gp_from_temperature(t, "暖地型芝") for t in monthly_temps]
        wos = [gp_from_temperature(t, turf_type) for t in monthly_temps]
        return {
            "寒地型GP": cool,
            "暖地型GP": warm,
            "WOS（合成GP）": wos,
        }

    label = GP_TURF_LABELS.get(turf_type, turf_type)
    return {label: [gp_from_temperature(t, turf_type) for t in monthly_temps]}


def smooth_line_for_chart(
    monthly_values: List[float],
    points_per_segment: int = 8,
) -> Tuple[List[float], List[float]]:
    """
    12ヶ月の値を折れ線上で滑らかに補間（グラフ表示専用）。

    Returns:
        (x座標 0〜11 の細分化, 対応する y 値)
    """
    x_month = np.arange(12, dtype=float)
    y_month = np.array(monthly_values, dtype=float)
    x_fine = np.linspace(0.0, 11.0, 12 * points_per_segment)
    y_fine = np.interp(x_fine, x_month, y_month)
    return x_fine.tolist(), y_fine.tolist()


def chart_df_smooth_series(
    gp_chart_series: Dict[str, List[float]],
) -> "pd.DataFrame":
    """Altair 用: 系列名・月インデックス（小数）・GP の long 形式。"""
    import pandas as pd

    rows = []
    for series_name, values in gp_chart_series.items():
        x_fine, y_fine = smooth_line_for_chart(values)
        for x, y in zip(x_fine, y_fine):
            month_idx = int(round(x)) % 12
            rows.append({
                "月": MONTHS_LABEL[month_idx],
                "月_idx": x,
                "GP": y,
                "系列": series_name,
            })
    return pd.DataFrame(rows)
