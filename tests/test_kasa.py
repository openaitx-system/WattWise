"""Tests for wattwise.kasa module."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wattwise.kasa import KasaDevice, discover_devices_sync


@pytest.fixture
def mock_energy_module():
    """Create a mock Energy module."""
    energy = MagicMock()
    energy.current_consumption = 150.5
    energy.voltage = 120.3
    energy.current = 1.25
    energy.consumption_today = 2.5
    return energy


@pytest.fixture
def mock_device(mock_energy_module):
    """Create a mock python-kasa Device."""
    device = MagicMock()
    device.alias = "TestPlug"
    device.model = "HS110"
    device.device_id = "ABC123"
    device.has_emeter = True
    device.is_on = True
    device.update = AsyncMock()

    # Mock Module.Energy lookup
    with patch("wattwise.kasa.Module") as mock_module:
        mock_module.Energy = "energy_key"
        device.modules = {"energy_key": mock_energy_module}
        yield device, mock_energy_module, mock_module


class TestKasaDeviceInit:
    @patch("wattwise.kasa.KASA_AVAILABLE", True)
    @patch("wattwise.kasa.config")
    def test_init_sets_attributes(self, mock_config):
        mock_config.get_data_dir.return_value = "/tmp/test-wattwise"
        device = KasaDevice("192.168.1.100", alias="Test")
        assert device.device_ip == "192.168.1.100"
        assert device.alias == "Test"
        assert device.device is None
        assert device.history == []

    @patch("wattwise.kasa.KASA_AVAILABLE", False)
    def test_init_raises_without_kasa(self):
        with pytest.raises(ImportError, match="python-kasa"):
            KasaDevice("192.168.1.100")


class TestKasaDeviceConnect:
    @patch("wattwise.kasa.KASA_AVAILABLE", True)
    @patch("wattwise.kasa.config")
    @patch("wattwise.kasa.Discover")
    def test_validate_connection_success(self, mock_discover, mock_config):
        mock_config.get_data_dir.return_value = "/tmp/test-wattwise"
        mock_device = MagicMock()
        mock_device.update = AsyncMock()
        mock_discover.discover_single = AsyncMock(return_value=mock_device)

        device = KasaDevice("192.168.1.100")
        success, error = device.validate_connection()
        assert success is True
        assert error is None
        assert device.device is mock_device

    @patch("wattwise.kasa.KASA_AVAILABLE", True)
    @patch("wattwise.kasa.config")
    @patch("wattwise.kasa.Discover")
    def test_validate_connection_timeout(self, mock_discover, mock_config):
        mock_config.get_data_dir.return_value = "/tmp/test-wattwise"
        mock_discover.discover_single = AsyncMock(side_effect=TimeoutError())

        device = KasaDevice("192.168.1.100")
        success, error = device.validate_connection()
        assert success is False
        assert "timed out" in error


class TestKasaDevicePower:
    @patch("wattwise.kasa.KASA_AVAILABLE", True)
    @patch("wattwise.kasa.config")
    @patch("wattwise.kasa.Module")
    @patch("wattwise.kasa.Discover")
    def test_get_power_usage(self, mock_discover, mock_module, mock_config):
        mock_config.get_data_dir.return_value = "/tmp/test-wattwise"

        mock_energy = MagicMock()
        mock_energy.current_consumption = 250.5
        mock_module.Energy = "energy_key"

        mock_dev = MagicMock()
        mock_dev.update = AsyncMock()
        mock_dev.modules = {"energy_key": mock_energy}
        mock_discover.discover_single = AsyncMock(return_value=mock_dev)

        device = KasaDevice("192.168.1.100")
        device.validate_connection()
        watts = device.get_power_usage()
        assert watts == 250.5
        assert len(device.history) == 1

    @patch("wattwise.kasa.KASA_AVAILABLE", True)
    @patch("wattwise.kasa.config")
    def test_get_power_usage_not_connected(self, mock_config):
        mock_config.get_data_dir.return_value = "/tmp/test-wattwise"

        with patch("wattwise.kasa.Discover") as mock_discover:
            mock_discover.discover_single = AsyncMock(
                side_effect=ConnectionRefusedError()
            )
            device = KasaDevice("192.168.1.100")
            watts = device.get_power_usage()
            assert watts is None


class TestKasaDeviceTrend:
    @patch("wattwise.kasa.KASA_AVAILABLE", True)
    @patch("wattwise.kasa.config")
    def test_get_power_trend_no_history(self, mock_config):
        mock_config.get_data_dir.return_value = "/tmp/test-wattwise"
        device = KasaDevice("192.168.1.100")
        assert device.get_power_trend() is None

    @patch("wattwise.kasa.KASA_AVAILABLE", True)
    @patch("wattwise.kasa.config")
    def test_get_power_trend_with_data(self, mock_config):
        mock_config.get_data_dir.return_value = "/tmp/test-wattwise"
        device = KasaDevice("192.168.1.100")
        now = time.time()
        device.history = [
            (now - 120, 100.0),
            (now - 60, 200.0),
            (now, 150.0),
        ]
        trend = device.get_power_trend(minutes=5)
        assert trend is not None
        assert trend["min"] == 100.0
        assert trend["max"] == 200.0
        assert trend["avg"] == 150.0

    @patch("wattwise.kasa.KASA_AVAILABLE", True)
    @patch("wattwise.kasa.config")
    def test_get_current_trend_no_history(self, mock_config):
        mock_config.get_data_dir.return_value = "/tmp/test-wattwise"
        device = KasaDevice("192.168.1.100")
        assert device.get_current_trend() is None


class TestDiscoverDevicesSync:
    @patch("wattwise.kasa.KASA_AVAILABLE", False)
    def test_not_available(self):
        result = discover_devices_sync()
        assert result == []

    @patch("wattwise.kasa.KASA_AVAILABLE", True)
    @patch("wattwise.kasa.Discover")
    def test_no_devices_found(self, mock_discover):
        mock_discover.discover = AsyncMock(return_value={})
        result = discover_devices_sync(display=False)
        assert result == []

    @patch("wattwise.kasa.KASA_AVAILABLE", True)
    @patch("wattwise.kasa.Discover")
    def test_devices_found(self, mock_discover):
        mock_dev = MagicMock()
        mock_dev.alias = "TestPlug"
        mock_dev.model = "HS110"
        mock_dev.is_on = True
        mock_dev.has_emeter = False

        mock_discover.discover = AsyncMock(return_value={"192.168.1.100": mock_dev})
        result = discover_devices_sync(display=False)
        assert len(result) == 1
        assert result[0]["ip"] == "192.168.1.100"
        assert result[0]["name"] == "TestPlug"
