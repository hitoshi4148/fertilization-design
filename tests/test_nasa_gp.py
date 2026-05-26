"""NASA POWER + 月別気温 GP のスモークテスト。"""

from logic.design_service import compute_gp_distribution_from_nasa
from logic.gp_temperature import monthly_gp_from_temperatures
from logic.nasa_power import fetch_monthly_t2m_celsius, last_calendar_year


def test_fetch_monthly_t2m():
    temps, year = fetch_monthly_t2m_celsius(35.0, 139.0, year=2025)
    assert len(temps) == 12
    assert year == 2025
    assert -30 < temps[0] < 40


def test_monthly_gp_from_temps():
    temps = [5.0] * 6 + [25.0] * 6
    gp = monthly_gp_from_temperatures(temps, "暖地型芝")
    assert 0 <= gp["7"] <= 1


def test_compute_gp_from_nasa_integration():
    gp = compute_gp_distribution_from_nasa(
        "寒地型芝", "競技場", 35.0, 139.0, "春重点50", year=2025
    )
    assert len(gp.gp_values_list) == 12
    assert abs(sum(gp.monthly_dist_ratios) - 1.0) < 1e-5
    assert gp.temperature_year == 2025
