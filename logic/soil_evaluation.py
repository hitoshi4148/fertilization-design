"""
土壌分析値の評価と不足分の月別配分。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

# 土壌評価基準（mg/100g）— N/P/K
SOIL_ELEMENT_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "N": {"mlsn": 5.0, "slan": 15.0},
    "P": {"mlsn": 1.0, "slan": 3.0},
    "K": {"mlsn": 15.0, "slan": 25.0},
}

CA_THRESHOLDS = {"mlsn": 100.0, "slan": 200.0}
MG_THRESHOLDS = {"mlsn": 2.0, "slan": 4.0}

MG100G_TO_KG10A = 0.15

FERTILIZERS: Dict[str, Dict] = {
    "N": {"name": "硫安", "nutrient": "N", "rate": 0.21},
    "P": {"name": "過リン酸石灰", "nutrient": "P2O5", "rate": 0.17},
    "K": {"name": "塩化カリ", "nutrient": "K2O", "rate": 0.60},
}


@dataclass
class ElementEvaluation:
    name: str
    value: float
    mlsn: float
    slan: float
    status: str
    comment: str
    deficit_mg: float
    fert_kg_10a: Optional[float]
    fertilizer_name: Optional[str]
    monthly_plan: Optional[Dict[str, float]]


@dataclass
class CaMgEvaluation:
    ratio: Optional[float]
    comment: str


def judge_status(value: float, mlsn: float, slan: float) -> str:
    if value < mlsn:
        return "不足"
    if value > slan:
        return "過剰"
    return "適正"


def comment_for_status(status: str, name: str) -> str:
    if status == "不足":
        return f"土壌中の{name}は、目安とする範囲を下回っています。"
    if status == "適正":
        return f"土壌中の{name}は、概ね適正な範囲にあります。"
    return f"土壌中の{name}は、目安とする範囲を上回っています。"


def calc_fertilizer_amount(deficit_kg: float, elem: str) -> Optional[float]:
    fert = FERTILIZERS.get(elem)
    if fert is None:
        return None
    return deficit_kg / fert["rate"]


def split_by_month(total_kg_10a: float, monthly_dist_ratios: List[float]) -> Dict[str, float]:
    return {str(m + 1): total_kg_10a * monthly_dist_ratios[m] for m in range(12)}


def evaluate_element(
    name: str,
    value: float,
    mlsn: float,
    slan: float,
    monthly_dist_ratios: List[float],
) -> ElementEvaluation:
    status = judge_status(value, mlsn, slan)
    comment = comment_for_status(status, name)
    deficit_mg = 0.0
    fert_kg = None
    fertilizer_name = None
    monthly_plan = None

    if status == "不足":
        deficit_mg = max(0.0, mlsn - value)
        deficit_kg_10a = max(0.0, deficit_mg * MG100G_TO_KG10A)
        fert_kg = calc_fertilizer_amount(deficit_kg_10a, name)
        if fert_kg is not None and name in ("N", "P", "K"):
            fertilizer_name = FERTILIZERS[name]["name"]
            monthly_plan = split_by_month(fert_kg, monthly_dist_ratios)

    return ElementEvaluation(
        name=name,
        value=value,
        mlsn=mlsn,
        slan=slan,
        status=status,
        comment=comment,
        deficit_mg=deficit_mg,
        fert_kg_10a=fert_kg,
        fertilizer_name=fertilizer_name,
        monthly_plan=monthly_plan,
    )


def evaluate_ca_mg(ca: float, mg: float) -> CaMgEvaluation:
    if mg <= 0:
        return CaMgEvaluation(
            ratio=None,
            comment="Mg が未測定のため、推定モードで評価します。",
        )
    ratio = ca / mg
    if ratio < 10:
        comment = "Mg 優位です。通気性や軟らかさを意識した管理が必要です。"
    elif ratio > 30:
        comment = "Ca が優位です。表層の締まりや乾きやすさに留意してください。"
    else:
        comment = "Ca と Mg のバランスは概ね良好です。"
    return CaMgEvaluation(ratio=ratio, comment=comment)


def build_monthly_fertilizer_plan(
    evaluations: Dict[str, ElementEvaluation],
) -> Dict[str, Dict[str, float]]:
    monthly_all: Dict[str, Dict[str, float]] = {}
    for elem in ("N", "P", "K"):
        ev = evaluations.get(elem)
        if ev is None or ev.monthly_plan is None:
            continue
        for month, kg in ev.monthly_plan.items():
            if month not in monthly_all:
                monthly_all[month] = {"N": 0.0, "P": 0.0, "K": 0.0}
            monthly_all[month][elem] = kg
    return monthly_all


def build_export_rows(
    monthly_gp: Dict[str, float],
    monthly_dist_ratios: List[float],
    monthly_all: Dict[str, Dict[str, float]],
) -> List[Dict]:
    export_rows: List[Dict] = []
    for m in range(1, 13):
        m_str = str(m)
        n_gm2 = round(monthly_all.get(m_str, {}).get("N", 0.0), 3)
        p_gm2 = round(monthly_all.get(m_str, {}).get("P", 0.0), 3)
        k_gm2 = round(monthly_all.get(m_str, {}).get("K", 0.0), 3)
        export_rows.append({
            "月": f"{m}月",
            "GP": round(monthly_gp.get(m_str, 0.0), 2),
            "配分係数": round(monthly_dist_ratios[m - 1], 3),
            "N (g/㎡)": n_gm2,
            "P (g/㎡)": p_gm2,
            "K (g/㎡)": k_gm2,
        })

    export_rows.append({
        "月": "年間合計",
        "GP": "",
        "配分係数": "",
        "N (g/㎡)": round(sum(r["N (g/㎡)"] for r in export_rows), 3),
        "P (g/㎡)": round(sum(r["P (g/㎡)"] for r in export_rows), 3),
        "K (g/㎡)": round(sum(r["K (g/㎡)"] for r in export_rows), 3),
    })
    return export_rows
