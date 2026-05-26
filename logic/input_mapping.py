"""
Streamlit UI の入力文字列を内部モデル（Enum）へ変換する。
"""

from __future__ import annotations

from .constants import (
    FertilizerStance,
    GrassType,
    ManagementIntensity,
    UsageType,
)


def resolve_grass_type(turf_type: str, management_target: str) -> GrassType:
    """芝種 × 管理対象 → 年間施肥モデル用の芝種区分。"""
    if turf_type == "寒地型芝":
        if "ゴルフ" in management_target:
            return GrassType.COOL_GREEN
        return GrassType.COOL_COMPETITION
    if turf_type == "暖地型芝":
        if management_target == "フェアウェイ":
            return GrassType.WARM_FAIRWAY
        if "ゴルフ" in management_target:
            return GrassType.WARM_GREEN
        return GrassType.WARM_COMPETITION
    if turf_type == "日本芝":
        if management_target == "フェアウェイ":
            return GrassType.JAPANESE_FAIRWAY
        return GrassType.JAPANESE_ZOYSIA
    if turf_type == "ウィンターオーバーシード（WOS）":
        return GrassType.WOS
    return GrassType.COOL_COMPETITION


def resolve_usage_type(management_target: str) -> UsageType:
    if "ゴルフ" in management_target or management_target == "フェアウェイ":
        return UsageType.GOLF
    return UsageType.COMPETITION


def resolve_fertilizer_stance(soil_target_position: str) -> FertilizerStance:
    return {
        "下限寄り": FertilizerStance.LOWER,
        "中央": FertilizerStance.CENTER,
        "上限寄り": FertilizerStance.UPPER,
    }.get(soil_target_position, FertilizerStance.CENTER)


def resolve_management_intensity(value: str | None = None) -> ManagementIntensity:
    """UI に管理強度がない間は「中」を既定とする。"""
    if value == "低":
        return ManagementIntensity.LOW
    if value == "高":
        return ManagementIntensity.HIGH
    return ManagementIntensity.MEDIUM
