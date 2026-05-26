"""
計算ロジックモジュール
"""

from .constants import (
    FertilizerStance,
    GrassType,
    ManagementIntensity,
    UsageType,
)
from .design_service import (
    DesignInputs,
    DesignOutputs,
    GpDistributionResult,
    compute_gp_distribution,
    compute_gp_distribution_from_nasa,
    run_design,
    run_design_with_gp,
    usage_type_from_management_target,
)
from .nasa_power import NasaPowerError, last_calendar_year
from .gp import calculate_growth_potential, calculate_growth_potentials
from .fertilizer import calculate_fertilizer_requirements
from .gp_daily import MONTHS_LABEL, build_gp_chart_series
from .soil_evaluation import ElementEvaluation, FERTILIZERS, SOIL_ELEMENT_THRESHOLDS

__all__ = [
    "GrassType",
    "UsageType",
    "ManagementIntensity",
    "FertilizerStance",
    "calculate_growth_potential",
    "calculate_growth_potentials",
    "calculate_fertilizer_requirements",
    "DesignInputs",
    "DesignOutputs",
    "GpDistributionResult",
    "compute_gp_distribution",
    "compute_gp_distribution_from_nasa",
    "run_design",
    "run_design_with_gp",
    "NasaPowerError",
    "last_calendar_year",
    "usage_type_from_management_target",
    "MONTHS_LABEL",
    "build_gp_chart_series",
    "ElementEvaluation",
    "FERTILIZERS",
    "SOIL_ELEMENT_THRESHOLDS",
]
