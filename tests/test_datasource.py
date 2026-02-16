"""Tests for wattwise.datasource protocol conformance."""

from unittest.mock import MagicMock, patch

import pytest

from wattwise.datasource import CurrentCapable, DataSource
from wattwise.homeassistant import HomeAssistant


class TestHomeAssistantConformsToDataSource:
    def test_is_data_source(self):
        ha = HomeAssistant("http://localhost", "token", "sensor.power", mock=True)
        assert isinstance(ha, DataSource)

    def test_has_validate_connection(self):
        ha = HomeAssistant("http://localhost", "token", "sensor.power", mock=True)
        assert callable(ha.validate_connection)

    def test_has_get_power_usage(self):
        ha = HomeAssistant("http://localhost", "token", "sensor.power", mock=True)
        assert callable(ha.get_power_usage)

    def test_has_get_power_trend(self):
        ha = HomeAssistant("http://localhost", "token", "sensor.power", mock=True)
        assert callable(ha.get_power_trend)


class TestHomeAssistantConformsToCurrentCapable:
    def test_is_current_capable(self):
        ha = HomeAssistant(
            "http://localhost",
            "token",
            "sensor.power",
            current_entity_id="sensor.current",
            mock=True,
        )
        assert isinstance(ha, CurrentCapable)

    def test_has_get_current_amperage(self):
        ha = HomeAssistant("http://localhost", "token", "sensor.power", mock=True)
        assert callable(ha.get_current_amperage)

    def test_has_get_current_trend(self):
        ha = HomeAssistant("http://localhost", "token", "sensor.power", mock=True)
        assert callable(ha.get_current_trend)


class TestKasaDeviceConformsToDataSource:
    @patch("wattwise.kasa.KASA_AVAILABLE", True)
    @patch("wattwise.kasa.config")
    def test_is_data_source(self, mock_config):
        mock_config.get_data_dir.return_value = "/tmp/test-wattwise"
        from wattwise.kasa import KasaDevice

        device = KasaDevice("192.168.1.100")
        assert isinstance(device, DataSource)

    @patch("wattwise.kasa.KASA_AVAILABLE", True)
    @patch("wattwise.kasa.config")
    def test_is_current_capable(self, mock_config):
        mock_config.get_data_dir.return_value = "/tmp/test-wattwise"
        from wattwise.kasa import KasaDevice

        device = KasaDevice("192.168.1.100")
        assert isinstance(device, CurrentCapable)
