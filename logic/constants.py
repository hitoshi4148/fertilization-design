"""
定数定義
"""

from enum import Enum
from typing import Dict, Tuple


class GrassType(str, Enum):
    """芝種区分"""
    COOL_COMPETITION = "寒地型（競技場）"
    COOL_GREEN = "寒地型（ゴルフグリーン）"
    WARM_COMPETITION = "暖地型（競技場）"
    WARM_GREEN = "暖地型（暖地芝グリーン）"
    WARM_FAIRWAY = "暖地型（フェアウェイ）"
    JAPANESE_FAIRWAY = "日本芝（フェアウェイ）"
    JAPANESE_ZOYSIA = "日本芝（ゾイシアグリーン）"
    WOS = "WOS（季節で寒地型／暖地型が優勢）"


class UsageType(str, Enum):
    """利用形態"""
    COMPETITION = "競技場"
    GOLF = "ゴルフ場"


class ManagementIntensity(str, Enum):
    """管理強度"""
    LOW = "低"
    MEDIUM = "中"
    HIGH = "高"


class FertilizerStance(str, Enum):
    """施肥スタンス"""
    LOWER = "下限寄り"
    CENTER = "中央"
    UPPER = "上限寄り"


# 年間N要求量の基準値（kg/ha/年）
# 芝種区分 × 利用形態 × 管理強度
ANNUAL_N_REQUIREMENT: Dict[Tuple[GrassType, UsageType, ManagementIntensity], float] = {
    # 寒地型
    (GrassType.COOL_COMPETITION, UsageType.COMPETITION, ManagementIntensity.LOW): 150.0,
    (GrassType.COOL_COMPETITION, UsageType.COMPETITION, ManagementIntensity.MEDIUM): 200.0,
    (GrassType.COOL_COMPETITION, UsageType.COMPETITION, ManagementIntensity.HIGH): 250.0,
    (GrassType.COOL_GREEN, UsageType.GOLF, ManagementIntensity.LOW): 180.0,
    (GrassType.COOL_GREEN, UsageType.GOLF, ManagementIntensity.MEDIUM): 220.0,
    (GrassType.COOL_GREEN, UsageType.GOLF, ManagementIntensity.HIGH): 280.0,
    
    # 暖地型
    (GrassType.WARM_COMPETITION, UsageType.COMPETITION, ManagementIntensity.LOW): 120.0,
    (GrassType.WARM_COMPETITION, UsageType.COMPETITION, ManagementIntensity.MEDIUM): 160.0,
    (GrassType.WARM_COMPETITION, UsageType.COMPETITION, ManagementIntensity.HIGH): 200.0,
    (GrassType.WARM_GREEN, UsageType.GOLF, ManagementIntensity.LOW): 140.0,
    (GrassType.WARM_GREEN, UsageType.GOLF, ManagementIntensity.MEDIUM): 180.0,
    (GrassType.WARM_GREEN, UsageType.GOLF, ManagementIntensity.HIGH): 220.0,
    (GrassType.WARM_FAIRWAY, UsageType.GOLF, ManagementIntensity.LOW): 100.0,
    (GrassType.WARM_FAIRWAY, UsageType.GOLF, ManagementIntensity.MEDIUM): 130.0,
    (GrassType.WARM_FAIRWAY, UsageType.GOLF, ManagementIntensity.HIGH): 160.0,
    
    # 日本芝
    (GrassType.JAPANESE_FAIRWAY, UsageType.GOLF, ManagementIntensity.LOW): 80.0,
    (GrassType.JAPANESE_FAIRWAY, UsageType.GOLF, ManagementIntensity.MEDIUM): 110.0,
    (GrassType.JAPANESE_FAIRWAY, UsageType.GOLF, ManagementIntensity.HIGH): 140.0,
    (GrassType.JAPANESE_ZOYSIA, UsageType.GOLF, ManagementIntensity.LOW): 100.0,
    (GrassType.JAPANESE_ZOYSIA, UsageType.GOLF, ManagementIntensity.MEDIUM): 130.0,
    (GrassType.JAPANESE_ZOYSIA, UsageType.GOLF, ManagementIntensity.HIGH): 160.0,
    
    # WOS
    (GrassType.WOS, UsageType.COMPETITION, ManagementIntensity.LOW): 135.0,
    (GrassType.WOS, UsageType.COMPETITION, ManagementIntensity.MEDIUM): 180.0,
    (GrassType.WOS, UsageType.COMPETITION, ManagementIntensity.HIGH): 225.0,
    (GrassType.WOS, UsageType.GOLF, ManagementIntensity.LOW): 160.0,
    (GrassType.WOS, UsageType.GOLF, ManagementIntensity.MEDIUM): 200.0,
    (GrassType.WOS, UsageType.GOLF, ManagementIntensity.HIGH): 250.0,
}

# 施肥スタンスによる補正係数（MSLN〜SLAN内の位置）
FERTILIZER_STANCE_FACTOR: Dict[FertilizerStance, float] = {
    FertilizerStance.LOWER: 0.85,  # 下限寄り
    FertilizerStance.CENTER: 1.0,   # 中央
    FertilizerStance.UPPER: 1.15,   # 上限寄り
}

# 土壌診断値の基準範囲（mg/100g）
SOIL_REFERENCE_RANGES = {
    "P": (10.0, 30.0),   # リン酸
    "K": (15.0, 25.0),   # カリウム
    "Ca": (200.0, 400.0),  # カルシウム
    "Mg": (20.0, 40.0),    # マグネシウム
}

# N:P:K:Ca:Mg の理想的な比率（年間施肥量の基準）
IDEAL_RATIO = {
    "N": 1.0,
    "P": 0.3,   # Nの30%
    "K": 0.5,   # Nの50%
    "Ca": 0.4,  # Nの40%
    "Mg": 0.15, # Nの15%
}
