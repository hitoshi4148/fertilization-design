"""
MSLN/SLAN理論に基づく年間施肥量決定モジュール

GPには一切依存せず、年間施肥量のみを決定する。
"""

from typing import Dict, Tuple
from .constants import (
    GrassType,
    UsageType,
    ManagementIntensity,
    FertilizerStance,
    SOIL_REFERENCE_RANGES,
)


# MSLN/SLANレンジ定義（kg/ha/年）
# 芝種区分 × 利用形態 × 管理強度 → (MSLN, SLAN)
ANNUAL_N_RANGE: Dict[Tuple[GrassType, UsageType, ManagementIntensity], Dict[str, float]] = {
    # 寒地型
    (GrassType.COOL_COMPETITION, UsageType.COMPETITION, ManagementIntensity.LOW): {"msln": 15.0, "slan": 25.0},
    (GrassType.COOL_COMPETITION, UsageType.COMPETITION, ManagementIntensity.MEDIUM): {"msln": 18.0, "slan": 30.0},
    (GrassType.COOL_COMPETITION, UsageType.COMPETITION, ManagementIntensity.HIGH): {"msln": 22.0, "slan": 35.0},
    (GrassType.COOL_GREEN, UsageType.GOLF, ManagementIntensity.LOW): {"msln": 18.0, "slan": 28.0},
    (GrassType.COOL_GREEN, UsageType.GOLF, ManagementIntensity.MEDIUM): {"msln": 20.0, "slan": 32.0},
    (GrassType.COOL_GREEN, UsageType.GOLF, ManagementIntensity.HIGH): {"msln": 24.0, "slan": 38.0},
    
    # 暖地型
    (GrassType.WARM_COMPETITION, UsageType.COMPETITION, ManagementIntensity.LOW): {"msln": 12.0, "slan": 22.0},
    (GrassType.WARM_COMPETITION, UsageType.COMPETITION, ManagementIntensity.MEDIUM): {"msln": 16.0, "slan": 28.0},
    (GrassType.WARM_COMPETITION, UsageType.COMPETITION, ManagementIntensity.HIGH): {"msln": 20.0, "slan": 32.0},
    (GrassType.WARM_GREEN, UsageType.GOLF, ManagementIntensity.LOW): {"msln": 14.0, "slan": 24.0},
    (GrassType.WARM_GREEN, UsageType.GOLF, ManagementIntensity.MEDIUM): {"msln": 18.0, "slan": 30.0},
    (GrassType.WARM_GREEN, UsageType.GOLF, ManagementIntensity.HIGH): {"msln": 22.0, "slan": 34.0},
    (GrassType.WARM_FAIRWAY, UsageType.GOLF, ManagementIntensity.LOW): {"msln": 10.0, "slan": 18.0},
    (GrassType.WARM_FAIRWAY, UsageType.GOLF, ManagementIntensity.MEDIUM): {"msln": 13.0, "slan": 22.0},
    (GrassType.WARM_FAIRWAY, UsageType.GOLF, ManagementIntensity.HIGH): {"msln": 16.0, "slan": 26.0},
    
    # 日本芝
    (GrassType.JAPANESE_FAIRWAY, UsageType.GOLF, ManagementIntensity.LOW): {"msln": 8.0, "slan": 15.0},
    (GrassType.JAPANESE_FAIRWAY, UsageType.GOLF, ManagementIntensity.MEDIUM): {"msln": 11.0, "slan": 18.0},
    (GrassType.JAPANESE_FAIRWAY, UsageType.GOLF, ManagementIntensity.HIGH): {"msln": 14.0, "slan": 22.0},
    (GrassType.JAPANESE_ZOYSIA, UsageType.GOLF, ManagementIntensity.LOW): {"msln": 10.0, "slan": 18.0},
    (GrassType.JAPANESE_ZOYSIA, UsageType.GOLF, ManagementIntensity.MEDIUM): {"msln": 13.0, "slan": 21.0},
    (GrassType.JAPANESE_ZOYSIA, UsageType.GOLF, ManagementIntensity.HIGH): {"msln": 16.0, "slan": 24.0},
    
    # WOS
    (GrassType.WOS, UsageType.COMPETITION, ManagementIntensity.LOW): {"msln": 13.5, "slan": 23.0},
    (GrassType.WOS, UsageType.COMPETITION, ManagementIntensity.MEDIUM): {"msln": 18.0, "slan": 30.0},
    (GrassType.WOS, UsageType.COMPETITION, ManagementIntensity.HIGH): {"msln": 22.5, "slan": 36.0},
    (GrassType.WOS, UsageType.GOLF, ManagementIntensity.LOW): {"msln": 16.0, "slan": 26.0},
    (GrassType.WOS, UsageType.GOLF, ManagementIntensity.MEDIUM): {"msln": 20.0, "slan": 32.0},
    (GrassType.WOS, UsageType.GOLF, ManagementIntensity.HIGH): {"msln": 25.0, "slan": 40.0},
}

# 施肥スタンスによる位置（MSLN〜SLAN内の位置）
STANCE_POSITION: Dict[FertilizerStance, float] = {
    FertilizerStance.LOWER: 0.25,  # 下限寄り（MSLN寄り）
    FertilizerStance.CENTER: 0.5,   # 中央
    FertilizerStance.UPPER: 0.75,  # 上限寄り（SLAN寄り）
}

# Nに対する他の成分の比率（MSLN/SLANベース）
NUTRIENT_RATIO_TO_N = {
    "P": 0.3,   # Nの30%
    "K": 0.5,   # Nの50%
    "Ca": 0.4,  # Nの40%
    "Mg": 0.15, # Nの15%
}

# 他の成分のMSLN/SLANレンジ（Nに対する比率で計算）
def get_nutrient_range(n_annual: float, nutrient: str) -> Dict[str, float]:
    """
    Nの年間量から他の成分のMSLN/SLANレンジを計算
    
    Args:
        n_annual: Nの年間量（kg/ha）
        nutrient: 成分名（"P", "K", "Ca", "Mg"）
    
    Returns:
        {"msln": float, "slan": float}
    """
    ratio = NUTRIENT_RATIO_TO_N.get(nutrient, 0.3)
    # MSLN/SLANはNの比率に基づいて計算（±20%の幅を想定）
    base = n_annual * ratio
    msln = base * 0.8
    slan = base * 1.2
    return {"msln": msln, "slan": slan}


def calculate_annual_nitrogen(
    grass_type: GrassType,
    usage_type: UsageType,
    management_intensity: ManagementIntensity,
    fertilizer_stance: FertilizerStance,
) -> Dict:
    """
    MSLN/SLAN理論に基づいて年間N量を決定
    
    Args:
        grass_type: 芝種区分
        usage_type: 利用形態
        management_intensity: 管理強度
        fertilizer_stance: 施肥スタンス
    
    Returns:
        {
            "annual_value": float,
            "msln": float,
            "slan": float,
            "position": str,
            "reason": str,
        }
    """
    # MSLN/SLANレンジを取得
    key = (grass_type, usage_type, management_intensity)
    range_data = ANNUAL_N_RANGE.get(key, {"msln": 15.0, "slan": 25.0})
    msln = range_data["msln"]
    slan = range_data["slan"]
    
    # MSLN〜SLAN内の位置を決定
    position_ratio = STANCE_POSITION[fertilizer_stance]
    annual_n = msln + (slan - msln) * position_ratio
    
    # MSLN/SLANの範囲内に収める
    annual_n = max(msln, min(slan, annual_n))
    
    # 説明文を生成（g/m²に変換：1 kg/ha = 0.1 g/m²）
    position_text = fertilizer_stance.value
    reason = (
        f"このN量は、{grass_type.value}・{usage_type.value}・{management_intensity.value}管理強度を前提に、"
        f"MSLN（{msln/10:.1f}g/m²）〜SLAN（{slan/10:.1f}g/m²）の範囲内で{position_text}の位置（{position_ratio*100:.0f}%位置）を選択した"
        f"年間窒素設計量です。"
    )
    
    return {
        "annual_value": round(annual_n, 1),
        "msln": round(msln, 1),
        "slan": round(slan, 1),
        "position": position_text,
        "reason": reason,
    }


def calculate_annual_phosphorus(
    n_annual: float,
    n_msln: float,
    n_slan: float,
    soil_p: float,
) -> Dict:
    """
    MSLN/SLAN理論に基づいて年間P量を決定
    
    Args:
        n_annual: Nの年間量（kg/ha）
        n_msln: NのMSLN値
        n_slan: NのSLAN値
        soil_p: 土壌診断値（mg/100g）
    
    Returns:
        {
            "annual_value": float,
            "msln": float,
            "slan": float,
            "position": str,
            "reason": str,
        }
    """
    # PのMSLN/SLANレンジを計算
    p_range = get_nutrient_range(n_annual, "P")
    p_msln = p_range["msln"]
    p_slan = p_range["slan"]
    
    # 土壌診断値による補正
    p_ref_min, p_ref_max = SOIL_REFERENCE_RANGES["P"]
    
    if soil_p < p_ref_min:
        # 不足時：MSLN寄りに設定（補正を強めに）
        deficiency_ratio = (p_ref_min - soil_p) / p_ref_min
        position_ratio = 0.2 + deficiency_ratio * 0.3  # 0.2〜0.5の範囲
        annual_p = p_msln + (p_slan - p_msln) * position_ratio
        position_text = "MSLN寄り（土壌不足補正）"
        reason = (
            f"リン酸は、N量（{n_annual/10:.1f}g/m²）を基準にMSLN（{p_msln/10:.1f}g/m²）〜SLAN（{p_slan/10:.1f}g/m²）の範囲を設定し、"
            f"土壌診断値（{soil_p:.1f}mg/100g）が基準下限（{p_ref_min:.1f}mg/100g）を下回るため、"
            f"不足分を補う設計としてMSLN寄りの値を採用しました。"
        )
    elif soil_p > p_ref_max:
        # 過剰時：MSLN寄りに設定（上限を超えない）
        annual_p = p_msln * 1.1  # MSLNの少し上、ただしSLANを超えない
        annual_p = min(annual_p, p_slan)
        position_text = "MSLN寄り（土壌過剰抑制）"
        reason = (
            f"リン酸は、N量（{n_annual/10:.1f}g/m²）を基準にMSLN（{p_msln/10:.1f}g/m²）〜SLAN（{p_slan/10:.1f}g/m²）の範囲を設定し、"
            f"土壌診断値（{soil_p:.1f}mg/100g）が基準上限（{p_ref_max:.1f}mg/100g）を上回るため、"
            f"過剰施肥を避ける設計としてMSLN寄りの値を採用しました。"
        )
    else:
        # 適正範囲内：中央付近
        position_ratio = 0.5
        annual_p = p_msln + (p_slan - p_msln) * position_ratio
        position_text = "中央"
        reason = (
            f"リン酸は、N量（{n_annual/10:.1f}g/m²）を基準にMSLN（{p_msln/10:.1f}g/m²）〜SLAN（{p_slan/10:.1f}g/m²）の範囲を設定し、"
            f"土壌診断値（{soil_p:.1f}mg/100g）が適正範囲内のため、中央の値を採用しました。"
        )
    
    # 範囲内に収める
    annual_p = max(p_msln, min(p_slan, annual_p))
    
    return {
        "annual_value": round(annual_p, 1),
        "msln": round(p_msln, 1),
        "slan": round(p_slan, 1),
        "position": position_text,
        "reason": reason,
    }


def calculate_annual_potassium(
    n_annual: float,
    n_msln: float,
    n_slan: float,
    soil_k: float,
) -> Dict:
    """
    MSLN/SLAN理論に基づいて年間K量を決定（Pと同様だが補正幅は小さく）
    
    Args:
        n_annual: Nの年間量（kg/ha）
        n_msln: NのMSLN値
        n_slan: NのSLAN値
        soil_k: 土壌診断値（mg/100g）
    
    Returns:
        {
            "annual_value": float,
            "msln": float,
            "slan": float,
            "position": str,
            "reason": str,
        }
    """
    # KのMSLN/SLANレンジを計算
    k_range = get_nutrient_range(n_annual, "K")
    k_msln = k_range["msln"]
    k_slan = k_range["slan"]
    
    # 土壌診断値による補正（Pより軽微）
    k_ref_min, k_ref_max = SOIL_REFERENCE_RANGES["K"]
    
    if soil_k < k_ref_min:
        # 不足時：軽微にMSLN寄りに
        deficiency_ratio = (k_ref_min - soil_k) / k_ref_min
        position_ratio = 0.3 + deficiency_ratio * 0.2  # 0.3〜0.5の範囲（Pより控えめ）
        annual_k = k_msln + (k_slan - k_msln) * position_ratio
        position_text = "MSLN寄り（軽微補正）"
        reason = (
            f"カリウムは、N量（{n_annual/10:.1f}g/m²）を基準にMSLN（{k_msln/10:.1f}g/m²）〜SLAN（{k_slan/10:.1f}g/m²）の範囲を設定し、"
            f"土壌診断値（{soil_k:.1f}mg/100g）が基準下限（{k_ref_min:.1f}mg/100g）を下回るため、"
            f"軽微な補正を適用してMSLN寄りの値を採用しました。"
        )
    elif soil_k > k_ref_max:
        # 過剰時：中央寄りに設定
        position_ratio = 0.4
        annual_k = k_msln + (k_slan - k_msln) * position_ratio
        annual_k = min(annual_k, k_slan)
        position_text = "中央寄り（過剰抑制）"
        reason = (
            f"カリウムは、N量（{n_annual/10:.1f}g/m²）を基準にMSLN（{k_msln/10:.1f}g/m²）〜SLAN（{k_slan/10:.1f}g/m²）の範囲を設定し、"
            f"土壌診断値（{soil_k:.1f}mg/100g）が基準上限（{k_ref_max:.1f}mg/100g）を上回るため、"
            f"過剰施肥を避ける設計として中央寄りの値を採用しました。"
        )
    else:
        # 適正範囲内：中央
        position_ratio = 0.5
        annual_k = k_msln + (k_slan - k_msln) * position_ratio
        position_text = "中央"
        reason = (
            f"カリウムは、N量（{n_annual/10:.1f}g/m²）を基準にMSLN（{k_msln/10:.1f}g/m²）〜SLAN（{k_slan/10:.1f}g/m²）の範囲を設定し、"
            f"土壌診断値（{soil_k:.1f}mg/100g）が適正範囲内のため、中央の値を採用しました。"
        )
    
    # 範囲内に収める
    annual_k = max(k_msln, min(k_slan, annual_k))
    
    return {
        "annual_value": round(annual_k, 1),
        "msln": round(k_msln, 1),
        "slan": round(k_slan, 1),
        "position": position_text,
        "reason": reason,
    }


def calculate_annual_calcium(
    n_annual: float,
    n_msln: float,
    n_slan: float,
    soil_ca: float,
) -> Dict:
    """
    MSLN/SLAN理論に基づいて年間Ca量を決定（不足時のみ補正）
    
    Args:
        n_annual: Nの年間量（kg/ha）
        n_msln: NのMSLN値
        n_slan: NのSLAN値
        soil_ca: 土壌診断値（mg/100g）
    
    Returns:
        {
            "annual_value": float,
            "msln": float,
            "slan": float,
            "position": str,
            "reason": str,
        }
    """
    # CaのMSLN/SLANレンジを計算
    ca_range = get_nutrient_range(n_annual, "Ca")
    ca_msln = ca_range["msln"]
    ca_slan = ca_range["slan"]
    
    # 土壌診断値による補正（不足時のみ）
    ca_ref_min, ca_ref_max = SOIL_REFERENCE_RANGES["Ca"]
    
    if soil_ca < ca_ref_min:
        # 不足時のみ補正：MSLNを少し上回る程度
        deficiency_ratio = (ca_ref_min - soil_ca) / ca_ref_min
        # MSLNの1.0〜1.3倍の範囲で補正
        annual_ca = ca_msln * (1.0 + deficiency_ratio * 0.3)
        annual_ca = min(annual_ca, ca_slan)  # SLANを超えない
        position_text = "MSLN超（不足補正）"
        reason = (
            f"カルシウムは、N量（{n_annual/10:.1f}g/m²）を基準にMSLN（{ca_msln/10:.1f}g/m²）〜SLAN（{ca_slan/10:.1f}g/m²）の範囲を設定し、"
            f"土壌診断値（{soil_ca:.1f}mg/100g）が基準下限（{ca_ref_min:.1f}mg/100g）を下回るため、"
            f"不足分を補う設計としてMSLNを上回る値を採用しました。"
        )
    else:
        # 適正範囲以上：MSLN程度（上限追求しない）
        annual_ca = ca_msln * 0.9  # MSLNよりやや控えめ
        position_text = "MSLN未満（控えめ設計）"
        reason = (
            f"カルシウムは、N量（{n_annual/10:.1f}g/m²）を基準にMSLN（{ca_msln/10:.1f}g/m²）〜SLAN（{ca_slan/10:.1f}g/m²）の範囲を設定し、"
            f"土壌診断値（{soil_ca:.1f}mg/100g）が基準範囲内以上（{ca_ref_min:.1f}mg/100g以上）のため、"
            f"過剰施肥を避ける設計としてMSLN未満の控えめな値を採用しました。"
        )
    
    # MSLN未満にはしない（最低でもMSLNの0.8倍）
    annual_ca = max(ca_msln * 0.8, annual_ca)
    
    return {
        "annual_value": round(annual_ca, 1),
        "msln": round(ca_msln, 1),
        "slan": round(ca_slan, 1),
        "position": position_text,
        "reason": reason,
    }


def calculate_annual_magnesium(
    n_annual: float,
    n_msln: float,
    n_slan: float,
    soil_mg: float,
) -> Dict:
    """
    MSLN/SLAN理論に基づいて年間Mg量を決定（不足時のみ補正）
    
    Args:
        n_annual: Nの年間量（kg/ha）
        n_msln: NのMSLN値
        n_slan: NのSLAN値
        soil_mg: 土壌診断値（mg/100g）
    
    Returns:
        {
            "annual_value": float,
            "msln": float,
            "slan": float,
            "position": str,
            "reason": str,
        }
    """
    # MgのMSLN/SLANレンジを計算
    mg_range = get_nutrient_range(n_annual, "Mg")
    mg_msln = mg_range["msln"]
    mg_slan = mg_range["slan"]
    
    # 土壌診断値による補正（不足時のみ）
    mg_ref_min, mg_ref_max = SOIL_REFERENCE_RANGES["Mg"]
    
    if soil_mg < mg_ref_min:
        # 不足時のみ補正：MSLNを少し上回る程度
        deficiency_ratio = (mg_ref_min - soil_mg) / mg_ref_min
        # MSLNの1.0〜1.3倍の範囲で補正
        annual_mg = mg_msln * (1.0 + deficiency_ratio * 0.3)
        annual_mg = min(annual_mg, mg_slan)  # SLANを超えない
        position_text = "MSLN超（不足補正）"
        reason = (
            f"マグネシウムは、N量（{n_annual/10:.1f}g/m²）を基準にMSLN（{mg_msln/10:.1f}g/m²）〜SLAN（{mg_slan/10:.1f}g/m²）の範囲を設定し、"
            f"土壌診断値（{soil_mg:.1f}mg/100g）が基準下限（{mg_ref_min:.1f}mg/100g）を下回るため、"
            f"不足分を補う設計としてMSLNを上回る値を採用しました。"
        )
    else:
        # 適正範囲以上：MSLN程度（上限追求しない）
        annual_mg = mg_msln * 0.9  # MSLNよりやや控えめ
        position_text = "MSLN未満（控えめ設計）"
        reason = (
            f"マグネシウムは、N量（{n_annual/10:.1f}g/m²）を基準にMSLN（{mg_msln/10:.1f}g/m²）〜SLAN（{mg_slan/10:.1f}g/m²）の範囲を設定し、"
            f"土壌診断値（{soil_mg:.1f}mg/100g）が基準範囲内以上（{mg_ref_min:.1f}mg/100g以上）のため、"
            f"過剰施肥を避ける設計としてMSLN未満の控えめな値を採用しました。"
        )
    
    # MSLN未満にはしない（最低でもMSLNの0.8倍）
    annual_mg = max(mg_msln * 0.8, annual_mg)
    
    return {
        "annual_value": round(annual_mg, 1),
        "msln": round(mg_msln, 1),
        "slan": round(mg_slan, 1),
        "position": position_text,
        "reason": reason,
    }


def calculate_annual_nutrient_requirements(
    grass_type: GrassType,
    usage_type: UsageType,
    management_intensity: ManagementIntensity,
    soil_values: Dict[str, float],  # {"P": float, "K": float, "Ca": float, "Mg": float}
    fertilizer_stance: FertilizerStance,
) -> Dict[str, Dict]:
    """
    MSLN/SLAN理論に基づいて年間施肥量を決定（GPには依存しない）
    
    Args:
        grass_type: 芝種区分
        usage_type: 利用形態
        management_intensity: 管理強度
        soil_values: 土壌診断値
        fertilizer_stance: 施肥スタンス
    
    Returns:
        {
            "N": {"annual_value": float, "msln": float, "slan": float, "position": str, "reason": str},
            "P": {...},
            "K": {...},
            "Ca": {...},
            "Mg": {...},
        }
    """
    # 1. Nの年間量を決定
    n_result = calculate_annual_nitrogen(
        grass_type, usage_type, management_intensity, fertilizer_stance
    )
    
    # 2. Pの年間量を決定
    p_result = calculate_annual_phosphorus(
        n_result["annual_value"],
        n_result["msln"],
        n_result["slan"],
        soil_values.get("P", 20.0),
    )
    
    # 3. Kの年間量を決定
    k_result = calculate_annual_potassium(
        n_result["annual_value"],
        n_result["msln"],
        n_result["slan"],
        soil_values.get("K", 20.0),
    )
    
    # 4. Caの年間量を決定
    ca_result = calculate_annual_calcium(
        n_result["annual_value"],
        n_result["msln"],
        n_result["slan"],
        soil_values.get("Ca", 300.0),
    )
    
    # 5. Mgの年間量を決定
    mg_result = calculate_annual_magnesium(
        n_result["annual_value"],
        n_result["msln"],
        n_result["slan"],
        soil_values.get("Mg", 30.0),
    )
    
    return {
        "N": n_result,
        "P": p_result,
        "K": k_result,
        "Ca": ca_result,
        "Mg": mg_result,
    }
