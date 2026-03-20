"""Tests for config module."""

import json
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from envsync.config import (
    ConfigFormat,
    ConfigLoader,
    ConfigManager,
    EnvironmentConfig,
    ProjectConfig,
)


class TestConfigFormat:
    def test_detect_json(self):
        assert ConfigFormat.detect(Path("config.json")) == ConfigFormat.JSON

    def test_detect_yaml(self):
        assert ConfigFormat.detect(Path("config.yaml")) == ConfigFormat.YAML
        assert ConfigFormat.detect(Path("config.yml")) == ConfigFormat.YAML

    def test_detect_toml(self):
        assert ConfigFormat.detect(Path("config.toml")) == ConfigFormat.TOML

    def test_detect_env(self):
        assert ConfigFormat.detect(Path(".env")) == "env"

    def test_detect_unknown(self):
        assert ConfigFormat.detect(Path("config.txt")) == ConfigFormat.JSON


class TestConfigLoader:
    def test_load_json(self, tmp_path):
        config_file = tmp_path / "config.json"
        data = {"key": "value", "nested": {"a": 1}}
        config_file.write_text(json.dumps(data))
        
        loaded = ConfigLoader.load(config_file)
        assert loaded == data

    def test_load_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        data = {"key": "value", "nested": {"a": 1}}
        config_file.write_text(yaml.dump(data))
        
        loaded = ConfigLoader.load(config_file)
        assert loaded == data

    def test_load_env(self, tmp_path):
        config_file = tmp_path / ".env"
        config_file.write_text("KEY1=value1\nKEY2=value2\n# comment\nKEY3=\"value with spaces\"")
        
        loaded = ConfigLoader.load(config_file)
        assert loaded["KEY1"] == "value1"
        assert loaded["KEY2"] == "value2"
        assert loaded["KEY3"] == "value with spaces"

    def test_load_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            ConfigLoader.load(Path("/nonexistent/config.json"))

    def test_save_json(self, tmp_path):
        config_file = tmp_path / "config.json"
        data = {"key": "value"}
        
        ConfigLoader.save(config_file, data)
        
        loaded = json.loads(config_file.read_text())
        assert loaded == data

    def test_save_yaml(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        data = {"key": "value"}
        
        ConfigLoader.save(config_file, data)
        
        loaded = yaml.safe_load(config_file.read_text())
        assert loaded == data

    def test_save_env(self, tmp_path):
        config_file = tmp_path / ".env"
        data = {"KEY1": "value1", "KEY2": "value with spaces"}
        
        ConfigLoader.save(config_file, data, ConfigFormat.ENV)
        
        content = config_file.read_text()
        assert "KEY1=value1" in content
        assert 'KEY2="value with spaces"' in content


class TestConfigManager:
    def test_init_project(self, tmp_path):
        manager = ConfigManager(tmp_path)
        config_file = manager.init_project("test_project")
        
        assert config_file.exists()
        assert manager.project_config is not None
        assert manager.project_config.project_name == "test_project"

    def test_load_project_config(self, tmp_path):
        manager = ConfigManager(tmp_path)
        manager.init_project("test_project")
        
        manager2 = ConfigManager(tmp_path)
        config = manager2.load_project_config()
        
        assert config.project_name == "test_project"

    def test_load_project_config_not_initialized(self, tmp_path):
        manager = ConfigManager(tmp_path)
        
        with pytest.raises(FileNotFoundError):
            manager.load_project_config()

    def test_add_environment(self, tmp_path):
        manager = ConfigManager(tmp_path)
        manager.init_project("test_project")
        
        config_file = tmp_path / "config.json"
        config_file.write_text('{"key": "value"}')
        
        env_config = manager.add_environment("dev", config_file)
        
        assert env_config.name == "dev"
        assert env_config.format == ConfigFormat.JSON
        assert "dev" in manager.project_config.environments

    def test_remove_environment(self, tmp_path):
        manager = ConfigManager(tmp_path)
        manager.init_project("test_project")
        
        config_file = tmp_path / "config.json"
        config_file.write_text('{"key": "value"}')
        
        manager.add_environment("dev", config_file)
        result = manager.remove_environment("dev")
        
        assert result is True
        assert "dev" not in manager.project_config.environments

    def test_remove_environment_not_found(self, tmp_path):
        manager = ConfigManager(tmp_path)
        manager.init_project("test_project")
        
        result = manager.remove_environment("nonexistent")
        assert result is False

    def test_load_environment(self, tmp_path):
        manager = ConfigManager(tmp_path)
        manager.init_project("test_project")
        
        config_file = tmp_path / "config.json"
        data = {"key": "value", "nested": {"a": 1}}
        config_file.write_text(json.dumps(data))
        
        manager.add_environment("dev", config_file)
        loaded = manager.load_environment("dev")
        
        assert loaded == data

    def test_save_environment(self, tmp_path):
        manager = ConfigManager(tmp_path)
        manager.init_project("test_project")
        
        config_file = tmp_path / "config.json"
        config_file.write_text('{}')
        
        manager.add_environment("dev", config_file)
        new_data = {"new_key": "new_value"}
        manager.save_environment("dev", new_data)
        
        loaded = json.loads(config_file.read_text())
        assert loaded == new_data

    def test_list_environments(self, tmp_path):
        manager = ConfigManager(tmp_path)
        manager.init_project("test_project")
        
        config_file = tmp_path / "config.json"
        config_file.write_text('{}')
        
        manager.add_environment("dev", config_file)
        manager.add_environment("prod", config_file)
        
        envs = manager.list_environments()
        assert set(envs) == {"dev", "prod"}

    def test_set_sensitive_fields(self, tmp_path):
        manager = ConfigManager(tmp_path)
        manager.init_project("test_project")
        
        manager.set_sensitive_fields(["*password*", "*secret*"])
        
        assert manager.project_config.sensitive_fields == ["*password*", "*secret*"]
