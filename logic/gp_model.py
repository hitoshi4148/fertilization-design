"""
気温ベースのGrowth Potential (GP) 計算モジュール
"""

import math
from typing import List, Optional


def calculate_gp_from_temperature(
    temperature: float,
    t_opt: float = 20.0,
    sigma: float = 7.0
) -> float:
    """
    気温からGPを計算（ガウス分布型）
    
    Args:
        temperature: 月平均気温（℃）
        t_opt: 最適気温（デフォルト20℃）
        sigma: 標準偏差（デフォルト7℃）
    
    Returns:
        GP値（0〜1の範囲）
    """
    if sigma == 0:
        return 1.0 if temperature == t_opt else 0.0
    
    gp = math.exp(-((temperature - t_opt) ** 2) / (2 * sigma ** 2))
    return max(0.0, min(1.0, gp))  # 0〜1の範囲に制限


def get_optimal_temperature(grass_type: str) -> float:
    """
    芝種に応じた最適気温を返す
    
    Args:
        grass_type: 芝種区分
    
    Returns:
        最適気温（℃）
    """
    if "寒地型" in grass_type:
        return 18.0  # 寒地型はやや低め
    elif "暖地型" in grass_type:
        return 25.0  # 暖地型はやや高め
    elif "日本芝" in grass_type:
        return 28.0  # 日本芝は高温
    else:  # WOS
        return 22.0  # 中間


def get_monthly_temperatures(
    latitude: float,
    longitude: float,
    grass_type: str
) -> List[float]:
    """
    緯度経度から月別平均気温を取得（仮データ版）
    
    実際の実装では、気象APIやデータベースから取得する
    
    Args:
        latitude: 緯度
        longitude: 経度
        grass_type: 芝種区分
    
    Returns:
        12ヶ月分の月平均気温（℃）のリスト
    """
    # 仮データ：日本の主要地域の月別平均気温パターン
    # 緯度に応じて調整（簡易版）
    
    # 基準気温パターン（東京付近）
    base_temps = [
        5.2,   # 1月
        5.7,   # 2月
        8.7,   # 3月
        13.9,  # 4月
        18.2,  # 5月
        21.4,  # 6月
        25.0,  # 7月
        26.4,  # 8月
        22.8,  # 9月
        17.5,  # 10月
        12.1,  # 11月
        7.6,   # 12月
    ]
    
    # 緯度による補正（簡易版：1度の緯度差で約0.6℃の差）
    lat_base = 35.7  # 東京の緯度
    lat_diff = latitude - lat_base
    temp_adjustment = lat_diff * 0.6
    
    # 各月の気温を調整
    adjusted_temps = [t + temp_adjustment for t in base_temps]
    
    return adjusted_temps


def calculate_monthly_gp(
    latitude: float,
    longitude: float,
    grass_type: str
) -> List[float]:
    """
    緯度経度と芝種から月別GPを計算
    
    Args:
        latitude: 緯度
        longitude: 経度
        grass_type: 芝種区分
    
    Returns:
        12ヶ月分のGP値（0〜1）のリスト
    """
    # 月別平均気温を取得
    monthly_temps = get_monthly_temperatures(latitude, longitude, grass_type)
    
    # 最適気温を取得
    t_opt = get_optimal_temperature(grass_type)
    
    # 各月のGPを計算
    monthly_gp = [
        calculate_gp_from_temperature(temp, t_opt=t_opt)
        for temp in monthly_temps
    ]
    
    return monthly_gp


def normalize_gp_ratios(gp_values: List[float]) -> List[float]:
    """
    GP値を比率に正規化（合計が1になるように）
    
    Args:
        gp_values: 12ヶ月分のGP値
    
    Returns:
        正規化されたGP比率（合計=1.0）
    """
    gp_sum = sum(gp_values)
    if gp_sum == 0:
        # 均等配分
        return [1.0 / 12] * 12
    
    return [gp / gp_sum for gp in gp_values]
