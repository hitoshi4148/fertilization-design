"""
施肥設計の統合 API（Streamlit UI / 他アプリ連携の共通入口）。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .gp_daily import (
    MONTHS_LABEL,
    build_gp_chart_series,
    calculate_daily_gp,
    gp_values_and_ratios,
    monthly_gp_averages,
)
from .gp_temperature import (
    build_gp_chart_series_from_temps,
    monthly_gp_from_temperatures,
)
from .nasa_power import NasaPowerError, fetch_monthly_t2m_celsius, last_calendar_year
from .monthly_distribution import (
    calculate_monthly_distribution_ratios,
    get_season_factors,
)
from .annual_nutrient_model import calculate_annual_nutrient_requirements
from .input_mapping import (
    resolve_fertilizer_stance,
    resolve_grass_type,
    resolve_management_intensity,
    resolve_usage_type,
)
from .soil_evaluation import (
    CA_THRESHOLDS,
    FERTILIZERS,
    MG_THRESHOLDS,
    SOIL_ELEMENT_THRESHOLDS,
    CaMgEvaluation,
    ElementEvaluation,
    build_export_rows,
    evaluate_ca_mg,
    evaluate_element,
)


def usage_type_from_management_target(management_target: str) -> str:
    if "ゴルフ" in management_target or "フェアウェイ" in management_target:
        return "ゴルフ場"
    return "競技場"


@dataclass
class DesignInputs:
    """施肥設計の入力（JSON 化可能）。"""

    turf_type: str
    management_target: str
    latitude: float
    longitude: float
    allocation_method: str
    soil_target_position: str = "中央"
    soil: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GpDistributionResult:
    monthly_gp: Dict[str, float]
    gp_values_list: List[float]
    gp_ratios_list: List[float]
    monthly_dist_ratios: List[float]
    gp_chart_series: Dict[str, List[float]]
    usage_type: str
    temperature_year: int | None = None
    monthly_temperatures_c: List[float] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DesignOutputs:
    """施肥設計の出力（JSON 化可能）。"""

    inputs: DesignInputs
    gp: GpDistributionResult
    soil_evaluations: Dict[str, ElementEvaluation] = field(default_factory=dict)
    ca_mg: Optional[CaMgEvaluation] = None
    monthly_fertilizer_plan: Dict[str, Dict[str, float]] = field(default_factory=dict)
    export_rows: List[Dict[str, Any]] = field(default_factory=list)
    # annual_gp: 全適正 / mixed: 適正は年間GP・不足は土壌補正
    plan_mode: str = ""
    annual_nutrients: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inputs": self.inputs.to_dict(),
            "gp": self.gp.to_dict(),
            "soil_evaluations": {
                k: asdict(v) for k, v in self.soil_evaluations.items()
            },
            "ca_mg": asdict(self.ca_mg) if self.ca_mg else None,
            "monthly_fertilizer_plan": self.monthly_fertilizer_plan,
            "export_rows": self.export_rows,
            "plan_mode": self.plan_mode,
            "annual_nutrients": self.annual_nutrients,
        }


def build_annual_gp_monthly_plan(
    inputs: DesignInputs,
    gp: GpDistributionResult,
) -> tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, Any]]]:
    """
    MSLN/SLAN 年間設計量（kg/ha）を、算出済み GP 配分係数で月別に割り、
    g/㎡（要素量）として返す。
    """
    grass = resolve_grass_type(inputs.turf_type, inputs.management_target)
    usage = resolve_usage_type(inputs.management_target)
    intensity = resolve_management_intensity()
    stance = resolve_fertilizer_stance(inputs.soil_target_position)
    soil = inputs.soil or {}
    soil_for_annual = {
        "P": soil.get("P", 0.0),
        "K": soil.get("K", 0.0),
        "Ca": soil.get("Ca", 0.0),
        "Mg": soil.get("Mg", 0.0),
    }
    annual = calculate_annual_nutrient_requirements(
        grass, usage, intensity, soil_for_annual, stance
    )
    ratios = gp.monthly_dist_ratios
    monthly_all: Dict[str, Dict[str, float]] = {}
    for m in range(1, 13):
        r = ratios[m - 1]
        # kg/ha -> g/㎡ : (kg/ha) * 1000 / 10000 = (kg/ha) * 0.1
        monthly_all[str(m)] = {
            "N": round(annual["N"]["annual_value"] * 0.1 * r, 3),
            "P": round(annual["P"]["annual_value"] * 0.1 * r, 3),
            "K": round(annual["K"]["annual_value"] * 0.1 * r, 3),
        }
    return monthly_all, annual


def build_combined_monthly_plan(
    inputs: DesignInputs,
    gp: GpDistributionResult,
    evaluations: Dict[str, ElementEvaluation],
) -> tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, Any]], str]:
    """
    適正要素は MSLN/SLAN 年間量の GP 配分、不足要素は土壌不足分の GP 配分を統合する。
    統合表の単位は g/㎡（要素量）で揃える。
    """
    annual_monthly, annual = build_annual_gp_monthly_plan(inputs, gp)
    deficit_elems = [
        e
        for e in ("N", "P", "K")
        if evaluations.get(e) is not None and evaluations[e].status == "不足"
    ]
    if not deficit_elems:
        return annual_monthly, annual, "annual_gp"

    merged: Dict[str, Dict[str, float]] = {}
    for m in range(1, 13):
        ms = str(m)
        merged[ms] = {}
        for elem in ("N", "P", "K"):
            ev = evaluations[elem]
            if ev.status == "不足" and ev.monthly_plan:
                fert = FERTILIZERS.get(elem, {})
                rate = float(fert.get("rate", 1.0))
                fert_kg = ev.monthly_plan.get(ms, 0.0)
                # ev.monthly_plan は「肥料換算（kg / 10a）」。
                # 要素量へ戻す: kg/10a * rate = kg/10a(要素)。
                # 1 kg/10a = 1 g/㎡ なので、そのまま g/㎡ として扱える。
                merged[ms][elem] = round(fert_kg * rate, 3)
            else:
                merged[ms][elem] = annual_monthly[ms][elem]
    return merged, annual, "mixed"


def compute_gp_distribution(
    turf_type: str,
    management_target: str,
    latitude: float,
    longitude: float,
    allocation_method: str,
) -> GpDistributionResult:
    """GP と月別配分比率を算出する。"""
    _ = longitude  # 将来の気象 API 用に保持

    daily_gp = calculate_daily_gp(latitude, turf_type)
    monthly_gp = monthly_gp_averages(daily_gp)
    gp_values_list, gp_ratios_list = gp_values_and_ratios(monthly_gp)

    usage_type = usage_type_from_management_target(management_target)
    base_stance = (
        "春重点" if allocation_method.startswith("春重点") else allocation_method
    )
    season_factors = get_season_factors(
        turf_type, usage_type, base_stance, use_heavy=True
    )
    monthly_dist_ratios = calculate_monthly_distribution_ratios(
        gp_ratios_list,
        season_factors,
        allocation_method,
        gp_values_list,
    )
    monthly_dist_ratios = [max(0.0, r) for r in monthly_dist_ratios]
    ratio_total = sum(monthly_dist_ratios)
    if ratio_total > 0:
        monthly_dist_ratios = [r / ratio_total for r in monthly_dist_ratios]
    else:
        monthly_dist_ratios = [1.0 / 12] * 12

    return GpDistributionResult(
        monthly_gp=monthly_gp,
        gp_values_list=gp_values_list,
        gp_ratios_list=gp_ratios_list,
        monthly_dist_ratios=monthly_dist_ratios,
        gp_chart_series=build_gp_chart_series(latitude, turf_type),
        usage_type=usage_type,
    )


def _distribution_from_monthly_gp(
    monthly_gp: Dict[str, float],
    turf_type: str,
    management_target: str,
    allocation_method: str,
    gp_chart_series: Dict[str, List[float]],
    temperature_year: int | None = None,
    monthly_temperatures_c: List[float] | None = None,
) -> GpDistributionResult:
    """月別 GP から配分比率まで組み立てる。"""
    gp_values_list, gp_ratios_list = gp_values_and_ratios(monthly_gp)
    usage_type = usage_type_from_management_target(management_target)
    base_stance = (
        "春重点" if allocation_method.startswith("春重点") else allocation_method
    )
    season_factors = get_season_factors(
        turf_type, usage_type, base_stance, use_heavy=True
    )
    monthly_dist_ratios = calculate_monthly_distribution_ratios(
        gp_ratios_list,
        season_factors,
        allocation_method,
        gp_values_list,
    )
    monthly_dist_ratios = [max(0.0, r) for r in monthly_dist_ratios]
    ratio_total = sum(monthly_dist_ratios)
    if ratio_total > 0:
        monthly_dist_ratios = [r / ratio_total for r in monthly_dist_ratios]
    else:
        monthly_dist_ratios = [1.0 / 12] * 12

    return GpDistributionResult(
        monthly_gp=monthly_gp,
        gp_values_list=gp_values_list,
        gp_ratios_list=gp_ratios_list,
        monthly_dist_ratios=monthly_dist_ratios,
        gp_chart_series=gp_chart_series,
        usage_type=usage_type,
        temperature_year=temperature_year,
        monthly_temperatures_c=monthly_temperatures_c,
    )


def compute_gp_distribution_from_nasa(
    turf_type: str,
    management_target: str,
    latitude: float,
    longitude: float,
    allocation_method: str,
    year: int | None = None,
) -> GpDistributionResult:
    """
    NASA POWER の昨年（暦年）月別気温から GP と配分を算出する。
    """
    monthly_temps, used_year = fetch_monthly_t2m_celsius(
        latitude, longitude, year=year
    )
    monthly_gp = monthly_gp_from_temperatures(monthly_temps, turf_type)
    gp_chart_series = build_gp_chart_series_from_temps(monthly_temps, turf_type)
    return _distribution_from_monthly_gp(
        monthly_gp,
        turf_type,
        management_target,
        allocation_method,
        gp_chart_series,
        temperature_year=used_year,
        monthly_temperatures_c=monthly_temps,
    )


def run_design(inputs: DesignInputs) -> DesignOutputs:
    """
    施肥設計を一括計算する（他アプリ連携用の主入口）。

    soil が None の場合は GP・配分のみ返す。
    """
    gp = compute_gp_distribution(
        inputs.turf_type,
        inputs.management_target,
        inputs.latitude,
        inputs.longitude,
        inputs.allocation_method,
    )
    return run_design_with_gp(inputs, gp)


def run_design_with_gp(inputs: DesignInputs, gp: GpDistributionResult) -> DesignOutputs:
    """事前に算出済みの GP 結果を使って施肥設計まで行う。"""
    outputs = DesignOutputs(inputs=inputs, gp=gp)

    if not inputs.soil:
        return outputs

    soil = inputs.soil
    ratios = gp.monthly_dist_ratios
    evaluations: Dict[str, ElementEvaluation] = {}

    for elem, thresholds in SOIL_ELEMENT_THRESHOLDS.items():
        evaluations[elem] = evaluate_element(
            elem,
            soil.get(elem, 0.0),
            thresholds["mlsn"],
            thresholds["slan"],
            ratios,
        )

    evaluations["Ca"] = evaluate_element(
        "Ca",
        soil.get("Ca", 0.0),
        CA_THRESHOLDS["mlsn"],
        CA_THRESHOLDS["slan"],
        ratios,
    )
    evaluations["Mg"] = evaluate_element(
        "Mg",
        soil.get("Mg", 0.0),
        MG_THRESHOLDS["mlsn"],
        MG_THRESHOLDS["slan"],
        ratios,
    )

    outputs.soil_evaluations = evaluations
    outputs.ca_mg = evaluate_ca_mg(soil.get("Ca", 0.0), soil.get("Mg", 0.0))

    monthly_all, annual, plan_mode = build_combined_monthly_plan(
        inputs, gp, evaluations
    )
    outputs.monthly_fertilizer_plan = monthly_all
    outputs.annual_nutrients = annual
    outputs.plan_mode = plan_mode

    outputs.export_rows = build_export_rows(
        gp.monthly_gp,
        gp.monthly_dist_ratios,
        outputs.monthly_fertilizer_plan,
    )

    return outputs
