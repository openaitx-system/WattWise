"""Tests for wattwise.homeassistant module."""

from unittest.mock import MagicMock, patch

from wattwise.homeassistant import HomeAssistant


class TestHomeAssistantInit:
    def test_init_sets_attributes(self):
        ha = HomeAssistant(
            "http://localhost:8123",
            "token123",
            "sensor.power",
            current_entity_id="sensor.current",
        )
        assert ha.host == "http://localhost:8123"
        assert ha.entity_id == "sensor.power"
        assert ha.current_entity_id == "sensor.current"
        assert not ha.mock

    def test_init_strips_trailing_slash(self):
        ha = HomeAssistant("http://localhost:8123/", "token", "sensor.power")
        assert ha.host == "http://localhost:8123"

    def test_mock_mode(self):
        ha = HomeAssistant("", "", "sensor.power", mock=True)
        assert ha.mock


class TestValidateConnection:
    def test_mock_always_succeeds(self):
        ha = HomeAssistant("", "", "sensor.power", mock=True)
        success, error = ha.validate_connection()
        assert success is True
        assert error is None

    def test_missing_host_fails(self):
        ha = HomeAssistant("", "token", "sensor.power")
        success, error = ha.validate_connection()
        assert success is False
        assert "Missing" in error

    def test_missing_token_fails(self):
        ha = HomeAssistant("http://localhost", "", "sensor.power")
        success, error = ha.validate_connection()
        assert success is False

    @patch("wattwise.homeassistant.requests.get")
    def test_successful_connection(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "entity_id": "sensor.power",
            "state": "150.0",
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        ha = HomeAssistant("http://localhost:8123", "token", "sensor.power")
        success, error = ha.validate_connection()
        assert success is True

    @patch("wattwise.homeassistant.requests.get")
    def test_failed_connection(self, mock_get):
        import requests

        mock_get.side_effect = requests.ConnectionError("refused")

        ha = HomeAssistant("http://localhost:8123", "token", "sensor.power")
        success, error = ha.validate_connection()
        assert success is False


class TestGetPowerUsage:
    def test_mock_returns_float(self):
        ha = HomeAssistant("", "", "sensor.power", mock=True)
        watts = ha.get_power_usage()
        assert isinstance(watts, float)
        assert watts > 0

    def test_mock_appends_history(self):
        ha = HomeAssistant("", "", "sensor.power", mock=True)
        ha.get_power_usage()
        assert len(ha.power_history) == 1

    @patch("wattwise.homeassistant.requests.get")
    def test_real_power_reading(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "entity_id": "sensor.power",
            "state": "250.5",
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        ha = HomeAssistant("http://localhost:8123", "token", "sensor.power")
        watts = ha.get_power_usage()
        assert watts == 250.5


class TestGetCurrentAmperage:
    def test_returns_none_without_entity(self):
        ha = HomeAssistant("http://localhost:8123", "token", "sensor.power")
        assert ha.get_current_amperage() is None

    def test_mock_returns_float(self):
        ha = HomeAssistant(
            "", "", "sensor.power", current_entity_id="sensor.current", mock=True
        )
        amperes = ha.get_current_amperage()
        assert isinstance(amperes, float)


class TestGetPowerTrend:
    def test_returns_none_with_no_history(self):
        ha = HomeAssistant("", "", "sensor.power", mock=True)
        assert ha.get_power_trend() is None

    def test_returns_none_with_insufficient_history(self):
        import time

        ha = HomeAssistant("", "", "sensor.power", mock=True)
        ha.power_history = [(time.time(), 100.0)]
        assert ha.get_power_trend() is None

    def test_returns_trend_data(self):
        import time

        ha = HomeAssistant("", "", "sensor.power", mock=True)
        now = time.time()
        ha.power_history = [
            (now - 120, 100.0),
            (now - 60, 200.0),
            (now, 150.0),
        ]
        trend = ha.get_power_trend(minutes=5)
        assert trend is not None
        assert trend["min"] == 100.0
        assert trend["max"] == 200.0
        assert trend["avg"] == 150.0
        assert trend["samples"] == 3
