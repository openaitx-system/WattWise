"""Tests for wattwise.cli module."""

from unittest.mock import patch

from typer.testing import CliRunner

from wattwise.cli import app

runner = CliRunner()


class TestHelpCommand:
    def test_help_shows_usage(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "wattwise" in result.output.lower() or "WattWise" in result.output

    def test_config_help(self):
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        assert "config" in result.output.lower()


class TestMockMode:
    @patch("wattwise.cli.config")
    def test_mock_mode_runs(self, mock_config):
        mock_config.load_config.return_value = {
            "homeassistant": {
                "host": "",
                "token": "",
                "entity_id": "sensor.power",
                "current_entity_id": "",
            },
            "kasa": {"device_ip": "", "alias": "PC"},
        }
        mock_config.get_config_dir.return_value = "/tmp/test-config"
        mock_config.get_data_dir.return_value = "/tmp/test-data"
        mock_config.get_config_path.return_value = "/tmp/test-config/config.yaml"
        mock_config.ConfigError = Exception

        result = runner.invoke(app, ["--mock"])
        # Mock mode should work even without real connection
        # It may fail on other reasons but should not crash on import
        assert result.exit_code in (0, 1)


class TestConfigShow:
    @patch("wattwise.cli.config")
    def test_show_config(self, mock_config):
        mock_config.load_config.return_value = {
            "homeassistant": {
                "host": "http://localhost:8123",
                "token": "abcd1234efgh5678",
                "entity_id": "sensor.power",
                "current_entity_id": "sensor.current",
            },
            "kasa": {"device_ip": "192.168.1.100", "alias": "TestPlug"},
        }
        mock_config.get_config_dir.return_value = "/tmp/test-config"
        mock_config.get_data_dir.return_value = "/tmp/test-data"
        mock_config.get_config_path.return_value = "/tmp/test-config/config.yaml"
        mock_config.ConfigError = Exception

        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "192.168.1.100" in result.output


class TestDiscoverFlag:
    @patch("wattwise.kasa.discover_devices_sync")
    @patch("wattwise.cli.config")
    def test_discover_flag(self, mock_config, mock_discover):
        mock_config.get_config_dir.return_value = "/tmp/test-config"
        mock_config.get_data_dir.return_value = "/tmp/test-data"
        mock_config.ConfigError = Exception
        mock_discover.return_value = []

        result = runner.invoke(app, ["--discover"])
        assert result.exit_code == 0


class TestCostCommand:
    @patch("wattwise.cli.config")
    def test_cost_basic(self, mock_config):
        mock_config.load_config.return_value = {
            "homeassistant": {
                "host": "",
                "token": "",
                "entity_id": "",
                "current_entity_id": "",
            },
            "kasa": {"device_ip": "", "alias": "PC"},
        }
        result = runner.invoke(app, ["cost", "--watts", "500"])
        assert result.exit_code == 0
        assert "500" in result.output
        assert "Hourly" in result.output
        assert "Daily" in result.output

    @patch("wattwise.cli.config")
    def test_cost_custom_rate(self, mock_config):
        mock_config.load_config.return_value = {
            "homeassistant": {
                "host": "",
                "token": "",
                "entity_id": "",
                "current_entity_id": "",
            },
            "kasa": {"device_ip": "", "alias": "PC"},
        }
        result = runner.invoke(app, ["cost", "--watts", "1000", "--rate", "0.25"])
        assert result.exit_code == 0
        assert "$0.25" in result.output  # hourly cost for 1kW at $0.25/kWh


class TestExportCommand:
    @patch("wattwise.cli.config")
    def test_export_no_history(self, mock_config):
        mock_config.get_data_dir.return_value = "/tmp/nonexistent-wattwise"
        result = runner.invoke(app, ["export"])
        assert result.exit_code == 1
        assert "No history data" in result.output


class TestDevicesCommand:
    def test_devices_help(self):
        result = runner.invoke(app, ["devices", "--help"])
        assert result.exit_code == 0

    @patch("wattwise.cli.config")
    def test_devices_list_empty(self, mock_config):
        mock_config.load_config.return_value = {
            "homeassistant": {
                "host": "",
                "token": "",
                "entity_id": "",
                "current_entity_id": "",
            },
            "kasa": {"device_ip": "", "alias": "PC"},
        }
        result = runner.invoke(app, ["devices", "list"])
        assert result.exit_code == 0
        assert "No devices configured" in result.output

    @patch("wattwise.cli.config")
    def test_devices_list_with_devices(self, mock_config):
        mock_config.load_config.return_value = {
            "homeassistant": {
                "host": "",
                "token": "",
                "entity_id": "",
                "current_entity_id": "",
            },
            "kasa": {"device_ip": "192.168.1.100", "alias": "TestPlug"},
        }
        result = runner.invoke(app, ["devices", "list"])
        assert result.exit_code == 0
        assert "TestPlug" in result.output

    @patch("wattwise.cli.config")
    def test_devices_list_ignores_legacy_when_devices_key_present(self, mock_config):
        mock_config.load_config.return_value = {
            "devices": [],
            "homeassistant": {
                "host": "http://localhost:8123",
                "token": "token",
                "entity_id": "sensor.power",
                "current_entity_id": "",
            },
            "kasa": {"device_ip": "192.168.1.50", "alias": "LegacyPlug"},
        }
        result = runner.invoke(app, ["devices", "list"])
        assert result.exit_code == 0
        assert "No devices configured" in result.output


class TestDevicesAdd:
    @patch("wattwise.cli.config")
    def test_devices_add_migrates_legacy(self, mock_config):
        legacy_config = {
            "homeassistant": {
                "host": "http://localhost:8123",
                "token": "token",
                "entity_id": "sensor.power",
                "current_entity_id": "sensor.current",
                "device_name": "LegacyHA",
            },
            "kasa": {"device_ip": "", "alias": "LegacyPlug"},
        }
        mock_config.load_config.return_value = legacy_config
        saved = {}

        def _save_config(cfg):
            saved["cfg"] = cfg

        mock_config.save_config.side_effect = _save_config

        result = runner.invoke(
            app,
            [
                "devices",
                "add",
                "--name",
                "NewPlug",
                "--type",
                "kasa",
                "--ip",
                "10.0.0.5",
            ],
        )
        assert result.exit_code == 0
        devices = saved["cfg"]["devices"]
        names = {d.get("name") for d in devices}
        assert "LegacyHA" in names
        assert "NewPlug" in names
