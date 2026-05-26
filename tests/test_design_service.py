"""design_service のスモークテスト（回帰防止）。"""

from logic.design_service import (
    DesignInputs,
    compute_gp_distribution,
    run_design,
    run_design_with_gp,
)


def test_compute_gp_distribution_wos():
    gp = compute_gp_distribution(
        turf_type="ウィンターオーバーシード（WOS）",
        management_target="ゴルフグリーン",
        latitude=35.0,
        longitude=139.0,
        allocation_method="春重点50",
    )
    assert len(gp.gp_chart_series) == 3
    assert abs(sum(gp.monthly_dist_ratios) - 1.0) < 1e-6


def test_run_design_with_soil_deficit():
    out = run_design(
        DesignInputs(
            turf_type="寒地型芝",
            management_target="競技場",
            latitude=35.0,
            longitude=139.0,
            allocation_method="春重点50",
            soil={"N": 0.0, "P": 0.0, "K": 0.0, "Ca": 150.0, "Mg": 3.0},
        )
    )
    assert out.soil_evaluations["N"].status == "不足"
    assert out.soil_evaluations["N"].monthly_plan is not None
    assert out.plan_mode == "mixed"
    assert out.export_rows
    d = out.to_dict()
    assert "inputs" in d and "gp" in d


def test_run_design_all_appropriate_uses_annual_gp():
    gp = compute_gp_distribution(
        turf_type="寒地型芝",
        management_target="競技場",
        latitude=35.0,
        longitude=139.0,
        allocation_method="春重点50",
    )
    out = run_design_with_gp(
        DesignInputs(
            turf_type="寒地型芝",
            management_target="競技場",
            latitude=35.0,
            longitude=139.0,
            allocation_method="春重点50",
            soil_target_position="中央",
            soil={"N": 10.0, "P": 2.0, "K": 20.0, "Ca": 150.0, "Mg": 3.0},
        ),
        gp,
    )
    assert out.plan_mode == "annual_gp"
    assert out.soil_evaluations["N"].status == "適正"
    total_n = sum(
        out.monthly_fertilizer_plan[str(m)]["N"] for m in range(1, 13)
    )
    assert total_n > 0
    # 月別表は g/㎡（要素量）。annual_nutrients は kg/ha なので 0.1 倍して比較する。
    assert abs(total_n - (out.annual_nutrients["N"]["annual_value"] * 0.1)) < 0.02


def test_k_deficit_keeps_n_p_annual_gp():
    gp = compute_gp_distribution(
        turf_type="寒地型芝",
        management_target="競技場",
        latitude=35.0,
        longitude=139.0,
        allocation_method="春重点50",
    )
    out = run_design_with_gp(
        DesignInputs(
            turf_type="寒地型芝",
            management_target="競技場",
            latitude=35.0,
            longitude=139.0,
            allocation_method="春重点50",
            soil_target_position="中央",
            soil={"N": 10.0, "P": 2.0, "K": 5.0, "Ca": 150.0, "Mg": 3.0},
        ),
        gp,
    )
    assert out.soil_evaluations["K"].status == "不足"
    assert out.soil_evaluations["N"].status == "適正"
    assert out.plan_mode == "mixed"
    assert out.monthly_fertilizer_plan["4"]["N"] > 0
    assert out.monthly_fertilizer_plan["4"]["P"] > 0
    assert out.monthly_fertilizer_plan["4"]["K"] > 0
