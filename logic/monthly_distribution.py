"""
月別施肥配分モジュール（GP × 季節補正）

GP（生理的成長能）と季節補正係数（管理戦略）を組み合わせて
月別配分を決定する。
"""

from typing import List, Dict, Tuple
from enum import Enum
from .constants import GrassType, UsageType


class DistributionStance(str, Enum):
    """配分スタンス"""
    SPRING_70 = "春重点70"
    SPRING_50 = "春重点50"  # デフォルト
    SPRING_30 = "春重点30"
    GP_BASED = "GP準拠"


# 季節補正係数テーブル（標準版）
# キー: (芝種区分, 利用形態, 配分スタンス)
# 値: 12ヶ月分の季節補正係数のリスト
SEASON_FACTOR_TABLE: Dict[Tuple[str, str, str], List[float]] = {
    # 寒地型・ゴルフグリーン・春重点
    ("寒地型", "ゴルフ場", "春重点"): [
        0.2,  # 1月
        0.2,  # 2月
        1.3,  # 3月
        1.5,  # 4月
        1.4,  # 5月
        1.0,  # 6月
        0.4,  # 7月
        0.4,  # 8月
        0.8,  # 9月
        0.9,  # 10月
        0.3,  # 11月
        0.3,  # 12月
    ],
    
    # 寒地型・競技場・春重点
    ("寒地型", "競技場", "春重点"): [
        0.2,  # 1月
        0.2,  # 2月
        1.2,  # 3月
        1.4,  # 4月
        1.3,  # 5月
        1.0,  # 6月
        0.5,  # 7月
        0.5,  # 8月
        0.9,  # 9月
        1.0,  # 10月
        0.4,  # 11月
        0.3,  # 12月
    ],
    
    # 暖地型・ゴルフグリーン・春重点
    ("暖地型", "ゴルフ場", "春重点"): [
        0.3,  # 1月
        0.4,  # 2月
        1.1,  # 3月
        1.3,  # 4月
        1.2,  # 5月
        0.8,  # 6月
        0.3,  # 7月
        0.3,  # 8月
        0.7,  # 9月
        0.9,  # 10月
        0.5,  # 11月
        0.4,  # 12月
    ],
    
    # 暖地型・競技場・春重点
    ("暖地型", "競技場", "春重点"): [
        0.3,  # 1月
        0.4,  # 2月
        1.0,  # 3月
        1.2,  # 4月
        1.1,  # 5月
        0.9,  # 6月
        0.4,  # 7月
        0.4,  # 8月
        0.8,  # 9月
        1.0,  # 10月
        0.6,  # 11月
        0.5,  # 12月
    ],
    
    # 日本芝・ゴルフ場・春重点
    ("日本芝", "ゴルフ場", "春重点"): [
        0.1,  # 1月
        0.2,  # 2月
        0.8,  # 3月
        1.2,  # 4月
        1.4,  # 5月
        1.3,  # 6月
        0.5,  # 7月
        0.4,  # 8月
        0.6,  # 9月
        0.7,  # 10月
        0.3,  # 11月
        0.2,  # 12月
    ],
    
    # WOS・ゴルフ場・春重点
    ("WOS", "ゴルフ場", "春重点"): [
        0.2,  # 1月
        0.3,  # 2月
        1.2,  # 3月
        1.4,  # 4月
        1.3,  # 5月
        0.9,  # 6月
        0.4,  # 7月
        0.4,  # 8月
        0.8,  # 9月
        0.9,  # 10月
        0.4,  # 11月
        0.3,  # 12月
    ],
    
    # WOS・競技場・春重点
    ("WOS", "競技場", "春重点"): [
        0.2,  # 1月
        0.3,  # 2月
        1.1,  # 3月
        1.3,  # 4月
        1.2,  # 5月
        1.0,  # 6月
        0.5,  # 7月
        0.5,  # 8月
        0.9,  # 9月
        1.0,  # 10月
        0.5,  # 11月
        0.4,  # 12月
    ],
}

# 管理強度による春ピーク倍率
# 管理強度は「芝をどこまで作り込むか」の意思決定
# 高管理ほど春先に体力を前倒しで投入する
# 低管理では急激な生育変動を避け、平準配分に近づける
MANAGEMENT_PEAK_MULTIPLIER: Dict[str, float] = {
    "低": 0.6,   # 低管理：春ピークを抑え、平準配分に近づける
    "中": 0.85,  # 中管理：標準的な春ピーク
    "高": 1.1,   # 高管理：春ピークを強調
}

# GP制御係数（GPを上限リミッターとして使用）
# GPは芝の生理的な受け皿
# 施肥量は GP に比例させるのではない
# GPが低い時期は効かせない
# GPが高すぎる時期は暴走させない
GP_CONTROL_FACTOR: Dict[str, float] = {
    "low": 0.4,       # GP < 0.30: ほぼ効かせない
    "optimal": 1.0,   # 0.30 <= GP < 0.75: 設計どおり
    "excess": 0.7,    # GP >= 0.75: 効きすぎ防止
}

# 季節補正係数テーブル（強化版：春前倒し施肥）
# ゴルフグリーンでは、夏期高温前に根量・貯蔵養分を確保するため、
# 年間施肥量の大部分を春〜初夏に前倒しする管理が一般的
# GPは生理的成長能であり、施肥戦略そのものではない
# そのため GP × 季節戦略 による配分を行う
# 目標：年間N量の60-70%を6月までに配分
# 注意：このテーブルは基準値であり、管理強度による調整が後で適用される
SEASON_FACTOR_SPRING_HEAVY: Dict[Tuple[str, str], List[float]] = {
    # 寒地型・ゴルフグリーン（春重点・強化版）
    ("寒地型", "ゴルフ場"): [
        0.15,  # 1月
        0.20,  # 2月
        1.6,   # 3月（春先重点）
        1.9,   # 4月（最大ピーク）
        1.7,   # 5月（高く維持）
        1.1,   # 6月（初夏）
        0.30,  # 7月（夏期抑制）
        0.25,  # 8月（夏期抑制）
        0.60,  # 9月（秋期）
        0.70,  # 10月（秋期）
        0.25,  # 11月（冬期抑制）
        0.15,  # 12月（冬期抑制）
    ],
    
    # 寒地型・競技場（春重点・強化版）
    ("寒地型", "競技場"): [
        0.15,  # 1月
        0.20,  # 2月
        1.5,   # 3月
        1.8,   # 4月
        1.6,   # 5月
        1.0,   # 6月
        0.35,  # 7月
        0.30,  # 8月
        0.65,  # 9月
        0.75,  # 10月
        0.30,  # 11月
        0.20,  # 12月
    ],
    
    # 暖地型・ゴルフグリーン（春重点・強化版）
    ("暖地型", "ゴルフ場"): [
        0.20,  # 1月
        0.30,  # 2月
        1.4,   # 3月
        1.7,   # 4月
        1.5,   # 5月
        0.9,   # 6月
        0.25,  # 7月
        0.20,  # 8月
        0.55,  # 9月
        0.65,  # 10月
        0.30,  # 11月
        0.25,  # 12月
    ],
    
    # 暖地型・競技場（春重点・強化版）
    ("暖地型", "競技場"): [
        0.20,  # 1月
        0.30,  # 2月
        1.3,   # 3月
        1.6,   # 4月
        1.4,   # 5月
        1.0,   # 6月
        0.30,  # 7月
        0.25,  # 8月
        0.60,  # 9月
        0.70,  # 10月
        0.35,  # 11月
        0.30,  # 12月
    ],
    
    # 日本芝・ゴルフ場（春重点・強化版）
    ("日本芝", "ゴルフ場"): [
        0.10,  # 1月
        0.15,  # 2月
        1.0,   # 3月
        1.5,   # 4月
        1.6,   # 5月
        1.4,   # 6月
        0.40,  # 7月
        0.35,  # 8月
        0.50,  # 9月
        0.60,  # 10月
        0.20,  # 11月
        0.15,  # 12月
    ],
    
    # WOS・ゴルフ場（春重点・強化版）
    ("WOS", "ゴルフ場"): [
        0.15,  # 1月
        0.25,  # 2月
        1.5,   # 3月
        1.8,   # 4月
        1.6,   # 5月
        1.0,   # 6月
        0.30,  # 7月
        0.25,  # 8月
        0.65,  # 9月
        0.75,  # 10月
        0.30,  # 11月
        0.20,  # 12月
    ],
    
    # WOS・競技場（春重点・強化版）
    ("WOS", "競技場"): [
        0.15,  # 1月
        0.25,  # 2月
        1.4,   # 3月
        1.7,   # 4月
        1.5,   # 5月
        1.1,   # 6月
        0.35,  # 7月
        0.30,  # 8月
        0.70,  # 9月
        0.80,  # 10月
        0.35,  # 11月
        0.25,  # 12月
    ],
}


def gp_zone(gp: float) -> str:
    """
    GPを3段階に区分
    
    GPは芝の生理的な受け皿
    施肥量は GP に比例させるのではない
    GPが低い時期は効かせない
    GPが高すぎる時期は暴走させない
    
    Args:
        gp: GP値（0.0〜1.0）
    
    Returns:
        "low", "optimal", "excess"のいずれか
    """
    if gp < 0.30:
        return "low"      # GPが低い：ほぼ効かせない
    elif gp < 0.75:
        return "optimal"  # GPが適正：設計どおり
    else:
        return "excess"   # GPが過剰：効きすぎ防止


def apply_gp_control(
    monthly_weights: List[float],
    gp_values: List[float]
) -> List[float]:
    """
    GP制御を適用（GPを上限リミッターとして使用）
    
    GPは芝の生理的な受け皿
    施肥量は GP に比例させるのではない
    GPが低い時期は効かせない
    GPが高すぎる時期は暴走させない
    
    Args:
        monthly_weights: 月別ウェイト（GP × 季節係数 × 管理強度適用後）
        gp_values: 月別GP値（12ヶ月分）
    
    Returns:
        GP制御適用後の月別ウェイト
    """
    controlled_weights = []
    for weight, gp in zip(monthly_weights, gp_values):
        zone = gp_zone(gp)
        control_factor = GP_CONTROL_FACTOR[zone]
        controlled_weights.append(weight * control_factor)
    
    return controlled_weights


def apply_management_intensity(
    factors: List[float],
    management_intensity: str
) -> List[float]:
    """
    管理強度による春ピーク倍率を適用
    
    管理強度は「芝をどこまで作り込むか」の意思決定
    高管理ほど春先に体力を前倒しで投入する
    低管理では急激な生育変動を避け、平準配分に近づける
    
    Args:
        factors: 基準季節係数（12ヶ月分）
        management_intensity: 管理強度（"低", "中", "高"）
    
    Returns:
        管理強度を反映した季節係数（春期3-5月のみ倍率適用）
    """
    multiplier = MANAGEMENT_PEAK_MULTIPLIER.get(management_intensity, 0.85)
    adjusted = factors.copy()
    
    # 春期（3-5月、0-indexed: 2-4）のみ倍率を適用
    # 夏・秋・冬は変更しない（「春の山の鋭さ」だけが変わる設計）
    for m in [2, 3, 4]:  # 3月、4月、5月
        adjusted[m] *= multiplier
    
    return adjusted


def get_season_factors(
    grass_type: str,
    usage_type: str,
    stance: str,
    use_heavy: bool = True,  # 強化版を使用するか（デフォルト：True）
    management_intensity: str = "中"  # 管理強度（デフォルト：中）
) -> List[float]:
    """
    季節補正係数を取得
    
    Args:
        grass_type: 芝種区分（"寒地型", "暖地型", "日本芝", "WOS"）
        usage_type: 利用形態（"ゴルフ場", "競技場"）
        stance: 配分スタンス（"春重点", "GP準拠"）
        use_heavy: 強化版を使用するか（春重点の場合のみ有効）
    
    Returns:
        12ヶ月分の季節補正係数
    """
    # 芝種区分を正規化
    if "寒地型" in grass_type:
        grass_key = "寒地型"
    elif "暖地型" in grass_type:
        grass_key = "暖地型"
    elif "日本芝" in grass_type:
        grass_key = "日本芝"
    else:  # WOS
        grass_key = "WOS"
    
    # 利用形態を正規化
    if "ゴルフ" in usage_type:
        usage_key = "ゴルフ場"
    else:
        usage_key = "競技場"
    
    # 配分スタンスに応じた処理
    if stance == "GP準拠":
        # GPのみ（季節補正なし）
        return [1.0] * 12
    else:  # 春重点（デフォルト：70/50/30）
        # 強化版を使用する場合
        if use_heavy:
            heavy_key = (grass_key, usage_key)
            base_factors = SEASON_FACTOR_SPRING_HEAVY.get(heavy_key)
            if base_factors is not None:
                # 管理強度による春ピーク倍率を適用
                return apply_management_intensity(base_factors, management_intensity)
        
        # 標準版を使用
        stance_key = "春重点"
        key = (grass_key, usage_key, stance_key)
        base_factors = SEASON_FACTOR_TABLE.get(key)
        
        if base_factors is None:
            # デフォルト：春重点パターン（寒地型・ゴルフ場）
            base_factors = SEASON_FACTOR_TABLE.get(("寒地型", "ゴルフ場", "春重点"), [1.0] * 12)
        
        # 管理強度による春ピーク倍率を適用
        return apply_management_intensity(base_factors, management_intensity)


def _get_spring_scale(stance: str) -> float:
    """
    配分スタンスから春重点スケール係数を取得
    
    春重点50 を基準（1.0）として、70 は強調、30 は抑制。
    季節補正係数の偏差（factor - 1.0）に対してスケーリングする。
    
    Args:
        stance: 配分スタンス（"春重点70", "春重点50", "春重点30"）
    
    Returns:
        スケール係数（春重点50 = 1.0）
    """
    if "70" in stance:
        return 1.4
    elif "30" in stance:
        return 0.6
    else:  # 50 or default
        return 1.0


def calculate_monthly_distribution_ratios(
    gp_ratios: List[float],
    season_factors: List[float],
    stance: str,
    gp_values: List[float],  # 月別GP値（制御用）
) -> List[float]:
    """
    GP比率と季節補正係数から月別配分比率を計算
    
    処理順序：
    ① GP（月別）
    ② 季節係数（春重点スケーリング適用）
    ③ 管理強度（春ピーク）
    ④ GP制御（生理的上限）
    ⑤ 正規化
    
    Args:
        gp_ratios: 正規化されたGP比率（合計=1.0）
        season_factors: 季節補正係数（管理強度適用済み）
        stance: 配分スタンス（"春重点70", "春重点50", "春重点30", "GP準拠"）
        gp_values: 月別GP値（0.0〜1.0、GP制御用）
    
    Returns:
        月別配分比率（合計=1.0）
    """
    if stance == "GP準拠":
        # GPのみ（季節補正なし、GP制御は適用）
        raw_weights = gp_ratios.copy()
        gp_controlled = apply_gp_control(raw_weights, gp_values)
    
    else:  # 春重点（70/50/30）
        # 春重点スケーリング：50%を基準に偏差を拡縮
        spring_scale = _get_spring_scale(stance)
        scaled_season = [
            max(0.0, 1.0 + (sf - 1.0) * spring_scale) for sf in season_factors
        ]
        
        # ① GP × スケーリング済み季節補正（管理強度適用済み）
        raw_weights = [
            gp_ratio * season_factor
            for gp_ratio, season_factor in zip(gp_ratios, scaled_season)
        ]
        
        # ② GP制御を適用（GPを上限リミッターとして使用）
        gp_controlled = apply_gp_control(raw_weights, gp_values)
    
    # ── 負値クリップ + 正規化（全配分方法共通） ──
    clamped = [max(0.0, w) for w in gp_controlled]
    total = sum(clamped)
    if total == 0:
        return [1.0 / 12] * 12
    monthly_ratios = [w / total for w in clamped]
    
    assert all(v >= 0 for v in monthly_ratios), \
        f"配分係数に負値が含まれています: {monthly_ratios}"
    
    return monthly_ratios


def calculate_monthly_fertilizer_distribution(
    annual_amount: float,
    gp_ratios: List[float],
    grass_type: str,
    usage_type: str,
    stance: str,
    management_intensity: str = "中",  # 管理強度
    gp_values: List[float] = None,  # 月別GP値（GP制御用）
) -> List[float]:
    """
    年間施肥量を月別に配分
    
    処理順序：
    ① GP（月別）
    ② 季節係数（春重点スケーリング適用）
    ③ 管理強度（春ピーク）
    ④ GP制御（生理的上限）
    ⑤ 正規化
    
    Args:
        annual_amount: 年間施肥量（kg/ha）
        gp_ratios: 正規化されたGP比率
        grass_type: 芝種区分
        usage_type: 利用形態
        stance: 配分スタンス（"春重点70", "春重点50", "春重点30", "GP準拠"）
        management_intensity: 管理強度（"低", "中", "高"）
        gp_values: 月別GP値（0.0〜1.0、GP制御用）
    
    Returns:
        12ヶ月分の月別施肥量（kg/ha）
    """
    # GP値が提供されていない場合は、GP比率から逆算（簡易版）
    if gp_values is None:
        # GP比率から元のGP値を推定（簡易版：比率×定数）
        gp_sum = sum(gp_ratios)
        if gp_sum > 0:
            gp_values = [ratio / gp_sum * 12 for ratio in gp_ratios]  # 簡易推定
        else:
            gp_values = [0.5] * 12  # デフォルト
    
    # 季節補正係数を取得（春重点の場合は強化版を使用、管理強度を反映）
    # 春重点70/50/30 → いずれも "春重点" として季節係数を取得
    base_stance = "春重点" if stance.startswith("春重点") else stance
    season_factors = get_season_factors(
        grass_type, usage_type, base_stance, use_heavy=True, management_intensity=management_intensity
    )
    
    # 月別配分比率を計算（GP制御を含む）
    monthly_ratios = calculate_monthly_distribution_ratios(
        gp_ratios, season_factors, stance, gp_values
    )
    
    # 年間量を配分
    monthly_amounts = [annual_amount * ratio for ratio in monthly_ratios]
    
    return monthly_amounts
