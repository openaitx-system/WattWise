"""Energy cost calculation for WattWise."""


def calculate_cost(watts: float, rate: float, hours: float = 1.0) -> float:
    """Calculate energy cost for a given power draw over time.

    Args:
        watts: Power consumption in watts.
        rate: Cost per kWh.
        hours: Duration in hours.

    Returns:
        Cost in the configured currency.
    """
    kwh = (watts / 1000.0) * hours
    return kwh * rate


def format_cost(cost: float, symbol: str = "$") -> str:
    """Format a cost value with currency symbol."""
    return f"{symbol}{cost:.2f}"


def estimate_costs(
    watts: float, rate: float, symbol: str = "$"
) -> dict[str, str]:
    """Estimate costs for various time periods.

    Args:
        watts: Current power draw in watts.
        rate: Cost per kWh.
        symbol: Currency symbol.

    Returns:
        Dict with hourly, daily, monthly, yearly cost strings.
    """
    return {
        "hourly": format_cost(calculate_cost(watts, rate, 1), symbol),
        "daily": format_cost(calculate_cost(watts, rate, 24), symbol),
        "monthly": format_cost(calculate_cost(watts, rate, 24 * 30), symbol),
        "yearly": format_cost(calculate_cost(watts, rate, 24 * 365), symbol),
    }
