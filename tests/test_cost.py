"""Tests for wattwise.cost module."""

from wattwise.cost import calculate_cost, estimate_costs, format_cost


class TestCalculateCost:
    def test_basic_calculation(self):
        # 1000W for 1 hour at $0.12/kWh = $0.12
        assert calculate_cost(1000, 0.12, 1) == pytest.approx(0.12)

    def test_zero_watts(self):
        assert calculate_cost(0, 0.12, 1) == 0.0

    def test_zero_rate(self):
        assert calculate_cost(500, 0.0, 24) == 0.0

    def test_24_hours(self):
        # 100W for 24h at $0.10/kWh = 2.4 kWh * 0.10 = $0.24
        assert calculate_cost(100, 0.10, 24) == pytest.approx(0.24)

    def test_fractional_hours(self):
        # 500W for 0.5h at $0.20/kWh = 0.25 kWh * 0.20 = $0.05
        assert calculate_cost(500, 0.20, 0.5) == pytest.approx(0.05)


class TestFormatCost:
    def test_default_symbol(self):
        assert format_cost(1.50) == "$1.50"

    def test_custom_symbol(self):
        assert format_cost(2.99, "EUR ") == "EUR 2.99"

    def test_zero(self):
        assert format_cost(0.0) == "$0.00"

    def test_rounding(self):
        assert format_cost(1.999) == "$2.00"


class TestEstimateCosts:
    def test_returns_all_periods(self):
        costs = estimate_costs(100, 0.12)
        assert "hourly" in costs
        assert "daily" in costs
        assert "monthly" in costs
        assert "yearly" in costs

    def test_daily_is_24x_hourly(self):
        costs = estimate_costs(500, 0.10)
        # Parse numeric values
        hourly = float(costs["hourly"].replace("$", ""))
        daily = float(costs["daily"].replace("$", ""))
        assert daily == pytest.approx(hourly * 24, abs=0.02)

    def test_custom_symbol(self):
        costs = estimate_costs(100, 0.15, "GBP ")
        assert costs["hourly"].startswith("GBP ")


import pytest
