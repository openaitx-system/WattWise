"""Shared fixtures for WattWise tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def tmp_config_dir(tmp_path):
    """Provide a temporary config directory."""
    config_dir = tmp_path / ".config" / "wattwise"
    config_dir.mkdir(parents=True)
    return config_dir


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provide a temporary data directory."""
    data_dir = tmp_path / ".local" / "share" / "wattwise"
    data_dir.mkdir(parents=True)
    return data_dir


@pytest.fixture
def sample_config():
    """Return a sample configuration dict."""
    return {
        "homeassistant": {
            "host": "http://10.0.0.43",
            "token": "test-token-abc123",
            "entity_id": "sensor.workstation_current_consumption",
            "current_entity_id": "sensor.workstation_current",
        },
        "kasa": {
            "device_ip": "192.168.1.100",
            "alias": "TestPlug",
        },
    }


@pytest.fixture
def sample_history():
    """Return sample history data."""
    import time

    now = time.time()
    return {
        "power": [(now - i * 60, 200.0 + i) for i in range(10)],
        "current": [(now - i * 60, 2.0 + i * 0.1) for i in range(10)],
    }


@pytest.fixture
def mock_kasa_device():
    """Create a mock Kasa Device with Energy module."""
    device = MagicMock()
    device.alias = "TestPlug"
    device.model = "HS110"
    device.device_id = "ABC123"
    device.has_emeter = True
    device.is_on = True

    energy_module = MagicMock()
    energy_module.current_consumption = 150.5
    energy_module.voltage = 120.3
    energy_module.current = 1.25
    energy_module.consumption_today = 2.5
    energy_module.consumption_this_month = 75.0

    # Module.Energy key mock
    device.modules = {MagicMock(): energy_module}

    # Make update() async
    device.update = AsyncMock()

    return device, energy_module


@pytest.fixture
def mock_discover_single(mock_kasa_device):
    """Patch Discover.discover_single to return a mock device."""
    device, _ = mock_kasa_device
    with patch("wattwise.kasa.Discover") as mock_discover:
        mock_discover.discover_single = AsyncMock(return_value=device)
        mock_discover.discover = AsyncMock(return_value={"192.168.1.100": device})
        yield mock_discover
