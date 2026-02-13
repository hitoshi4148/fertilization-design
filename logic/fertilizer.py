"""
施肥量計算モジュール（GP配分を含む）

MSLN/SLAN理論に基づく年間量は annual_nutrient_model から取得し、
GP × 季節補正に基づいて月別配分を行う。
"""

from typing import Dict, Tuple, List, Optional
from .constants import (
    GrassType,
    UsageType,
    ManagementIntensity,
    FertilizerStance,
)
from .annual_nutrient_model import calculate_annual_nutrient_requirements
from .gp_model import calculate_monthly_gp, normalize_gp_ratios
from .monthly_distribution import calculate_monthly_fertilizer_distribution


def calculate_fertilizer_requirements(
    grass_type: GrassType,
    usage_type: UsageType,
    management_intensity: ManagementIntensity,
    soil_values: Dict[str, float],  # {"P": float, "K": float, "Ca": float, "Mg": float}
    fertilizer_stance: FertilizerStance,
    latitude: float = 35.7,  # デフォルト：東京
    longitude: float = 139.8,
    distribution_stance: str = "春重点50",  # 配分スタンス
) -> Dict[str, Dict]:
    """
    年間施肥設計を計算（MSLN/SLAN理論 + GP × 季節補正配分）
    
    Args:
        grass_type: 芝種区分
        usage_type: 利用形態
        management_intensity: 管理強度
        soil_values: 土壌診断値
        fertilizer_stance: 施肥スタンス
        latitude: 緯度
        longitude: 経度
        distribution_stance: 配分スタンス（"春重点70", "春重点50", "春重点30", "GP準拠"）
    
    Returns:
        計算結果の辞書
        {
            "N": {
                "annual": float,
                "annual_value": float,  # MSLN/SLANモデルからの値
                "msln": float,
                "slan": float,
                "position": str,
                "monthly": List[float],
                "gp_values": List[float],  # 月別GP値
                "correction": str,
                "explanation": str,
            },
            ...
        }
    """
    # MSLN/SLAN理論に基づく年間量を取得
    annual_requirements = calculate_annual_nutrient_requirements(
        grass_type, usage_type, management_intensity, soil_values, fertilizer_stance
    )
    
    # 気温ベースのGPを計算
    monthly_gp = calculate_monthly_gp(latitude, longitude, grass_type.value)
    gp_ratios = normalize_gp_ratios(monthly_gp)
    
    # 各成分の月別配分を計算（GP × 季節補正 × 管理強度 × GP制御）
    results = {}
    for nutrient in ["N", "P", "K", "Ca", "Mg"]:
        annual_value = annual_requirements[nutrient]["annual_value"]
        
        # GP × 季節補正 × 管理強度 × GP制御に基づいて月別配分
        monthly = calculate_monthly_fertilizer_distribution(
            annual_value,
            gp_ratios,
            grass_type.value,
            usage_type.value,
            distribution_stance,
            management_intensity.value,  # 管理強度を渡す
            monthly_gp,  # GP値（GP制御用）
        )
        monthly = [round(x, 1) for x in monthly]
        
        # 既存のフォーマットに合わせて結果を構築
        results[nutrient] = {
            "annual": annual_value,  # 後方互換性のため
            "annual_value": annual_value,
            "msln": annual_requirements[nutrient]["msln"],
            "slan": annual_requirements[nutrient]["slan"],
            "position": annual_requirements[nutrient]["position"],
            "monthly": monthly,
            "gp_values": monthly_gp,  # GP値を保存
            "correction": annual_requirements[nutrient].get("correction", ""),
            "explanation": annual_requirements[nutrient]["reason"],
        }
    
    return results
