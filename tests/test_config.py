"""Tests for wattwise.config module."""

import base64
import os
from unittest.mock import patch

import yaml

from wattwise import config


class TestGetConfigDir:
    def test_returns_string(self):
        result = config.get_config_dir()
        assert isinstance(result, str)

    def test_directory_exists(self):
        result = config.get_config_dir()
        assert os.path.isdir(result)

    def test_ends_with_wattwise(self):
        result = config.get_config_dir()
        assert result.endswith("wattwise")


class TestGetDataDir:
    def test_returns_string(self):
        result = config.get_data_dir()
        assert isinstance(result, str)

    def test_directory_exists(self):
        result = config.get_data_dir()
        assert os.path.isdir(result)


class TestLoadConfig:
    def test_load_creates_default_if_missing(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        with patch.object(config, "get_config_dir", return_value=str(tmp_path)):
            with patch.object(config, "get_config_path", return_value=str(config_path)):
                with patch.object(
                    config,
                    "get_token_path",
                    return_value=str(tmp_path / "token.secret"),
                ):
                    cfg = config.load_config()

        assert "homeassistant" in cfg
        assert "kasa" in cfg
        assert cfg["homeassistant"]["host"] == ""
        assert cfg["kasa"]["device_ip"] == ""

    def test_load_existing_config(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        test_config = {
            "homeassistant": {
                "host": "http://test.local",
                "token": "",
                "entity_id": "sensor.test",
                "current_entity_id": "",
            },
            "kasa": {"device_ip": "10.0.0.1", "alias": "MyPlug"},
        }
        with open(config_path, "w") as f:
            yaml.dump(test_config, f)

        with patch.object(config, "get_config_dir", return_value=str(tmp_path)):
            with patch.object(config, "get_config_path", return_value=str(config_path)):
                with patch.object(
                    config,
                    "get_token_path",
                    return_value=str(tmp_path / "token.secret"),
                ):
                    cfg = config.load_config()

        assert cfg["homeassistant"]["host"] == "http://test.local"
        assert cfg["kasa"]["device_ip"] == "10.0.0.1"

    def test_load_with_token_file(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        token_path = tmp_path / "token.secret"

        test_config = {
            "homeassistant": {
                "host": "http://test.local",
                "token": "",
                "entity_id": "sensor.test",
                "current_entity_id": "",
            },
            "kasa": {"device_ip": "", "alias": "PC"},
        }
        with open(config_path, "w") as f:
            yaml.dump(test_config, f)

        encoded_token = base64.b64encode(b"my-secret-token").decode("utf-8")
        with open(token_path, "w") as f:
            f.write(encoded_token)

        with patch.object(config, "get_config_dir", return_value=str(tmp_path)):
            with patch.object(config, "get_config_path", return_value=str(config_path)):
                with patch.object(
                    config, "get_token_path", return_value=str(token_path)
                ):
                    cfg = config.load_config()

        assert cfg["homeassistant"]["token"] == "my-secret-token"


class TestSaveConfig:
    def test_save_creates_file(self, tmp_path):
        config_path = tmp_path / "config.yaml"
        token_path = tmp_path / "token.secret"

        test_config = {
            "homeassistant": {
                "host": "http://test.local",
                "token": "my-token",
                "entity_id": "sensor.test",
                "current_entity_id": "",
            },
            "kasa": {"device_ip": "10.0.0.1", "alias": "Plug"},
        }

        with patch.object(config, "get_config_dir", return_value=str(tmp_path)):
            with patch.object(config, "get_config_path", return_value=str(config_path)):
                with patch.object(
                    config, "get_token_path", return_value=str(token_path)
                ):
                    config.save_config(test_config)

        assert config_path.exists()
        assert token_path.exists()

        # Token should NOT be in the config file (stored separately)
        with open(config_path) as f:
            saved = yaml.safe_load(f)
        assert saved["homeassistant"]["token"] == ""

        # Token should be base64 encoded in token file
        with open(token_path) as f:
            encoded = f.read().strip()
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert decoded == "my-token"


class TestSaveToken:
    def test_save_empty_token_noop(self, tmp_path):
        with patch.object(config, "get_config_dir", return_value=str(tmp_path)):
            with patch.object(
                config, "get_token_path", return_value=str(tmp_path / "token.secret")
            ):
                config.save_token("")
        assert not (tmp_path / "token.secret").exists()

    def test_save_token_creates_file(self, tmp_path):
        token_path = tmp_path / "token.secret"
        with patch.object(config, "get_config_dir", return_value=str(tmp_path)):
            with patch.object(config, "get_token_path", return_value=str(token_path)):
                config.save_token("test-token")
        assert token_path.exists()

    def test_token_file_permissions(self, tmp_path):
        token_path = tmp_path / "token.secret"
        with patch.object(config, "get_config_dir", return_value=str(tmp_path)):
            with patch.object(config, "get_token_path", return_value=str(token_path)):
                config.save_token("test-token")
        mode = oct(os.stat(token_path).st_mode)[-3:]
        assert mode == "600"
