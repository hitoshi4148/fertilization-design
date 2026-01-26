"""
Growth Potential (GP) 計算モジュール
"""

from typing import List, Dict, Optional
from datetime import datetime


def _get_cool_season_gp() -> List[float]:
    """寒地型のGPパターンを返す"""
    return [
        0.3,  # 1月
        0.4,  # 2月
        0.7,  # 3月
        0.9,  # 4月
        0.95, # 5月
        0.8,  # 6月
        0.6,  # 7月
        0.5,  # 8月
        0.7,  # 9月
        0.85, # 10月
        0.6,  # 11月
        0.4,  # 12月
    ]


def _get_warm_season_gp() -> List[float]:
    """暖地型のGPパターンを返す"""
    return [
        0.2,  # 1月
        0.3,  # 2月
        0.5,  # 3月
        0.7,  # 4月
        0.85, # 5月
        0.95, # 6月
        0.98, # 7月
        0.95, # 8月
        0.85, # 9月
        0.7,  # 10月
        0.5,  # 11月
        0.3,  # 12月
    ]


def calculate_growth_potential(
    grass_type: str,
    year: int = None
) -> List[float]:
    """
    年間Growth Potentialを計算
    
    Args:
        grass_type: 芝種区分
        year: 年（デフォルトは現在年）
    
    Returns:
        12ヶ月分のGP値（0.0〜1.0）のリスト
    """
    if year is None:
        year = datetime.now().year
    
    # 月ごとのGP計算（簡易版）
    # 実際のGP計算は気温データなどに基づくが、MVPでは季節パターンを使用
    
    if "寒地型" in grass_type:
        # 寒地型：春・秋にピーク、夏はやや低い
        gp_pattern = _get_cool_season_gp()
    elif "暖地型" in grass_type:
        # 暖地型：夏にピーク、冬は低い
        gp_pattern = _get_warm_season_gp()
    elif "日本芝" in grass_type:
        # 日本芝：夏にピーク、冬は休眠
        gp_pattern = [
            0.1,  # 1月
            0.15, # 2月
            0.3,  # 3月
            0.6,  # 4月
            0.85, # 5月
            0.95, # 6月
            0.98, # 7月
            0.95, # 8月
            0.85, # 9月
            0.6,  # 10月
            0.3,  # 11月
            0.15, # 12月
        ]
    elif grass_type == "WOS（季節で寒地型／暖地型が優勢）":
        # WOS：春・秋に寒地型、夏に暖地型が優勢（平均値を使用）
        cool_gp = _get_cool_season_gp()
        warm_gp = _get_warm_season_gp()
        gp_pattern = [(cool_gp[i] + warm_gp[i]) / 2 for i in range(12)]
    else:
        # デフォルト：年間平均
        gp_pattern = [0.7] * 12
    
    return gp_pattern


def calculate_growth_potentials(
    grass_type: str,
    year: int = None
) -> Dict[str, List[float]]:
    """
    年間Growth Potentialを計算（複数パターン対応）
    
    Args:
        grass_type: 芝種区分
        year: 年（デフォルトは現在年）
    
    Returns:
        GP値の辞書
        - "main": メインのGP値（施肥計算に使用）
        - "cool": 寒地型のGP値（WOSの場合のみ）
        - "warm": 暖地型のGP値（WOSの場合のみ）
    """
    if year is None:
        year = datetime.now().year
    
    if grass_type == "WOS（季節で寒地型／暖地型が優勢）":
        # WOSの場合は両方のGPを返す
        return {
            "main": calculate_growth_potential(grass_type, year),
            "cool": _get_cool_season_gp(),
            "warm": _get_warm_season_gp(),
        }
    elif "寒地型" in grass_type:
        # 寒地型
        gp = _get_cool_season_gp()
        return {
            "main": gp,
            "cool": gp,
        }
    elif "暖地型" in grass_type:
        # 暖地型
        gp = _get_warm_season_gp()
        return {
            "main": gp,
            "warm": gp,
        }
    else:
        # その他（日本芝など）
        gp = calculate_growth_potential(grass_type, year)
        return {
            "main": gp,
        }


def get_monthly_n_distribution(
    annual_n: float,
    gp_values: List[float]
) -> List[float]:
    """
    GPに基づいて年間Nを月別に配分
    
    Args:
        annual_n: 年間N要求量（kg/ha）
        gp_values: 12ヶ月分のGP値
    
    Returns:
        12ヶ月分のN配分量（kg/ha）のリスト
    """
    # GPの合計で正規化
    gp_sum = sum(gp_values)
    if gp_sum == 0:
        # 均等配分
        return [annual_n / 12] * 12
    
    # GP比率で配分
    monthly_n = [annual_n * (gp / gp_sum) for gp in gp_values]
    return monthly_n
