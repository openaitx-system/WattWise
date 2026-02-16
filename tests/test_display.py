"""Tests for wattwise.display module."""

from io import StringIO

import pytest
from rich.console import Console

from wattwise.display import DisplayManager


@pytest.fixture
def display_mgr():
    """Create a DisplayManager with default config."""
    return DisplayManager({})


@pytest.fixture
def display_mgr_custom():
    """Create a DisplayManager with custom thresholds."""
    return DisplayManager(
        {
            "display": {
                "thresholds": {"warning": 200, "critical": 800},
                "colors": {"normal": "green", "warning": "yellow", "critical": "red"},
            }
        }
    )


class TestGetColorForWatts:
    def test_normal_color(self, display_mgr):
        assert display_mgr.get_color_for_watts(100) == "green"

    def test_warning_color(self, display_mgr):
        assert display_mgr.get_color_for_watts(500) == "yellow"

    def test_critical_color(self, display_mgr):
        assert display_mgr.get_color_for_watts(1500) == "red"

    def test_custom_thresholds(self, display_mgr_custom):
        assert display_mgr_custom.get_color_for_watts(100) == "green"
        assert display_mgr_custom.get_color_for_watts(300) == "yellow"
        assert display_mgr_custom.get_color_for_watts(900) == "red"


class TestAddToHistory:
    def test_appends_reading(self, display_mgr):
        display_mgr.add_to_history(150.0)
        assert len(display_mgr.history) == 1
        assert display_mgr.history[0][1] == 150.0

    def test_trims_history(self, display_mgr):
        display_mgr.max_history_size = 5
        for i in range(10):
            display_mgr.add_to_history(float(i))
        assert len(display_mgr.history) == 5


class TestDisplayCurrentUsage:
    def test_displays_without_error(self, display_mgr):
        # Capture output to prevent terminal noise
        display_mgr.console = Console(file=StringIO())
        display_mgr.display_current_usage(150.0, "Test Source")

    def test_displays_with_current(self, display_mgr):
        display_mgr.console = Console(file=StringIO())
        display_mgr.display_current_usage(150.0, "Test Source", current_amperes=1.5)
        assert len(display_mgr.current_history) == 1


class TestDisplayStats:
    def test_renders_panel(self, display_mgr):
        output = StringIO()
        display_mgr.console = Console(file=output)
        display_mgr.display_stats("Test", {"key1": "value1", "key2": "value2"})
        rendered = output.getvalue()
        assert "value1" in rendered
        assert "value2" in rendered


class TestShowError:
    def test_renders_error(self, display_mgr):
        output = StringIO()
        display_mgr.console = Console(file=output)
        display_mgr.show_error("Test Error", "Something went wrong")
        rendered = output.getvalue()
        assert "Something went wrong" in rendered


class TestShowSuccess:
    def test_renders_success(self, display_mgr):
        output = StringIO()
        display_mgr.console = Console(file=output)
        display_mgr.show_success("Test Success", "It worked!")
        rendered = output.getvalue()
        assert "It worked!" in rendered
