"""Tests for config module."""

import json
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from envsync.core.config import (
    ConfigManager,
    ConfigFileHandler,
    TemplateRenderer,
    Environment,
    Template,
    Snapshot,
    ConfigVariable,
    ConfigFormat,
)


class TestConfigVariable:
    """Tests for ConfigVariable dataclass."""

    def test_config_variable_creation(self):
        """Test creating a ConfigVariable."""
        var = ConfigVariable(
            name="TEST_VAR",
            value="test_value",
            description="A test variable",
            encrypted=False,
            required=True,
            type="string",
        )
        assert var.name == "TEST_VAR"
        assert var.value == "test_value"
        assert var.description == "A test variable"
        assert var.encrypted is False
        assert var.required is True
        assert var.type == "string"

    def test_config_variable_defaults(self):
        """Test ConfigVariable default values."""
        var = ConfigVariable(name="TEST_VAR", value="test_value")
        assert var.description is None
        assert var.encrypted is False
        assert var.required is False
        assert var.type == "string"
        assert var.pattern is None


class TestEnvironment:
    """Tests for Environment dataclass."""

    def test_environment_creation(self):
        """Test creating an Environment."""
        now = datetime.now().isoformat()
        env = Environment(
            name="test",
            description="Test environment",
            variables={"TEST_VAR": ConfigVariable(name="TEST_VAR", value="test")},
            created_at=now,
            updated_at=now,
        )
        assert env.name == "test"
        assert env.description == "Test environment"
        assert len(env.variables) == 1
        assert env.created_at == now
        assert env.updated_at == now

    def test_environment_to_dict(self):
        """Test converting Environment to dict."""
        now = datetime.now().isoformat()
        env = Environment(
            name="test",
            variables={"TEST_VAR": ConfigVariable(name="TEST_VAR", value="test")},
            created_at=now,
            updated_at=now,
        )
        env_dict = env.to_dict()
        assert env_dict["name"] == "test"
        assert "variables" in env_dict
        assert "TEST_VAR" in env_dict["variables"]

    def test_environment_from_dict(self):
        """Test creating Environment from dict."""
        data = {
            "name": "test",
            "description": "Test",
            "variables": {
                "TEST_VAR": {
                    "name": "TEST_VAR",
                    "value": "test",
                    "description": "Test var",
                }
            },
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }
        env = Environment.from_dict(data)
        assert env.name == "test"
        assert env.variables["TEST_VAR"].value == "test"


class TestTemplate:
    """Tests for Template dataclass."""

    def test_template_creation(self):
        """Test creating a Template."""
        now = datetime.now().isoformat()
        template = Template(
            name="test",
            variables={"TEST_VAR": {"type": "string"}},
            required=["TEST_VAR"],
            sensitive=[],
            created_at=now,
            updated_at=now,
        )
        assert template.name == "test"
        assert len(template.variables) == 1
        assert template.required == ["TEST_VAR"]

    def test_template_to_dict(self):
        """Test converting Template to dict."""
        now = datetime.now().isoformat()
        template = Template(
            name="test",
            variables={"TEST_VAR": {"type": "string"}},
            required=["TEST_VAR"],
            sensitive=["TEST_VAR"],
            created_at=now,
            updated_at=now,
        )
        template_dict = template.to_dict()
        assert template_dict["name"] == "test"
        assert template_dict["required"] == ["TEST_VAR"]
        assert template_dict["sensitive"] == ["TEST_VAR"]

    def test_template_from_dict(self):
        """Test creating Template from dict."""
        data = {
            "name": "test",
            "variables": {"TEST_VAR": {"type": "string"}},
            "required": ["TEST_VAR"],
            "sensitive": [],
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }
        template = Template.from_dict(data)
        assert template.name == "test"
        assert template.variables["TEST_VAR"]["type"] == "string"


class TestSnapshot:
    """Tests for Snapshot dataclass."""

    def test_snapshot_creation(self):
        """Test creating a Snapshot."""
        snapshot = Snapshot(
            id="test123",
            name="Test Snapshot",
            timestamp="2023-01-01T00:00:00",
            environments=["dev", "prod"],
            description="Test snapshot",
        )
        assert snapshot.id == "test123"
        assert snapshot.name == "Test Snapshot"
        assert snapshot.environments == ["dev", "prod"]
        assert snapshot.description == "Test snapshot"

    def test_snapshot_to_dict(self):
        """Test converting Snapshot to dict."""
        snapshot = Snapshot(
            id="test123",
            name="Test Snapshot",
            timestamp="2023-01-01T00:00:00",
            environments=["dev"],
        )
        snapshot_dict = snapshot.to_dict()
        assert snapshot_dict["id"] == "test123"
        assert snapshot_dict["environments"] == ["dev"]

    def test_snapshot_from_dict(self):
        """Test creating Snapshot from dict."""
        data = {
            "id": "test123",
            "name": "Test Snapshot",
            "timestamp": "2023-01-01T00:00:00",
            "environments": ["dev", "prod"],
            "description": "Test snapshot",
        }
        snapshot = Snapshot.from_dict(data)
        assert snapshot.id == "test123"
        assert snapshot.environments == ["dev", "prod"]


class TestConfigManager:
    """Tests for ConfigManager."""

    def test_initialization(self, tmp_path):
        """Test ConfigManager initialization."""
        config_manager = ConfigManager(base_dir=tmp_path)
        assert config_manager.base_dir == tmp_path
        assert config_manager.environments_dir == tmp_path / "environments"
        assert config_manager.templates_dir == tmp_path / "templates"
        assert config_manager.snapshots_dir == tmp_path / "snapshots"
        assert config_manager.snapshot_data_dir == tmp_path / "snapshot_data"

    def test_directories_creation(self, tmp_path):
        """Test that ConfigManager creates necessary directories."""
        ConfigManager(base_dir=tmp_path)
        assert (tmp_path / "environments").exists()
        assert (tmp_path / "templates").exists()
        assert (tmp_path / "snapshots").exists()
        assert (tmp_path / "snapshot_data").exists()

    def test_save_and_load_environment(self, tmp_path):
        """Test saving and loading an environment."""
        config_manager = ConfigManager(base_dir=tmp_path)
        now = datetime.now().isoformat()
        env = Environment(
            name="test",
            variables={"TEST_VAR": ConfigVariable(name="TEST_VAR", value="test")},
            created_at=now,
            updated_at=now,
        )
        config_manager.save_environment(env)

        loaded_env = config_manager.load_environment("test")
        assert loaded_env is not None
        assert loaded_env.name == "test"
        assert loaded_env.variables["TEST_VAR"].value == "test"

    def test_delete_environment(self, tmp_path):
        """Test deleting an environment."""
        config_manager = ConfigManager(base_dir=tmp_path)
        now = datetime.now().isoformat()
        env = Environment(
            name="test",
            variables={"TEST_VAR": ConfigVariable(name="TEST_VAR", value="test")},
            created_at=now,
            updated_at=now,
        )
        config_manager.save_environment(env)
        assert config_manager.environment_exists("test") is True

        result = config_manager.delete_environment("test")
        assert result is True
        assert config_manager.environment_exists("test") is False

    def test_list_environments(self, tmp_path):
        """Test listing environments."""
        config_manager = ConfigManager(base_dir=tmp_path)
        now = datetime.now().isoformat()

        for name in ["dev", "prod", "staging"]:
            env = Environment(
                name=name,
                variables={},
                created_at=now,
                updated_at=now,
            )
            config_manager.save_environment(env)

        environments = config_manager.list_environments()
        assert len(environments) == 3
        assert set(environments) == {"dev", "prod", "staging"}

    def test_create_and_load_snapshot(self, tmp_path):
        """Test creating and loading a snapshot."""
        config_manager = ConfigManager(base_dir=tmp_path)
        now = datetime.now().isoformat()

        # Create test environments
        env = Environment(
            name="test",
            variables={"TEST_VAR": ConfigVariable(name="TEST_VAR", value="test")},
            created_at=now,
            updated_at=now,
        )
        config_manager.save_environment(env)

        # Create snapshot
        snapshot = config_manager.create_snapshot("test_snapshot", "Test snapshot")
        assert snapshot.id is not None
        assert snapshot.name == "test_snapshot"
        assert "test" in snapshot.environments

        # Load snapshot metadata
        loaded_snapshot = config_manager.load_snapshot(snapshot.id)
        assert loaded_snapshot is not None
        assert loaded_snapshot.name == "test_snapshot"

    def test_restore_snapshot(self, tmp_path):
        """Test restoring from a snapshot."""
        config_manager = ConfigManager(base_dir=tmp_path)
        now = datetime.now().isoformat()

        # Create and save an environment
        env = Environment(
            name="test",
            variables={"TEST_VAR": ConfigVariable(name="TEST_VAR", value="original_value")},
            created_at=now,
            updated_at=now,
        )
        config_manager.save_environment(env)

        # Create snapshot
        snapshot = config_manager.create_snapshot("backup")

        # Modify the environment
        env.variables["TEST_VAR"].value = "modified_value"
        config_manager.save_environment(env)

        # Verify modification
        modified_env = config_manager.load_environment("test")
        assert modified_env.variables["TEST_VAR"].value == "modified_value"

        # Restore snapshot
        result = config_manager.restore_snapshot(snapshot.id)
        assert result is True

        # Verify restoration
        restored_env = config_manager.load_environment("test")
        assert restored_env.variables["TEST_VAR"].value == "original_value"


class TestConfigFileHandler:
    """Tests for ConfigFileHandler."""

    def test_read_env_file(self, tmp_path):
        """Test reading a .env file."""
        env_file = tmp_path / "test.env"
        env_file.write_text("TEST_VAR=test_value\nANOTHER_VAR=another_value")

        result = ConfigFileHandler.read_env_file(env_file)
        assert result["TEST_VAR"] == "test_value"
        assert result["ANOTHER_VAR"] == "another_value"

    def test_read_json_file(self, tmp_path):
        """Test reading a JSON file."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"TEST_VAR": "test_value", "NUMBER": 42}')

        result = ConfigFileHandler.read_json_file(json_file)
        assert result["TEST_VAR"] == "test_value"
        assert result["NUMBER"] == 42

    def test_read_yaml_file(self, tmp_path):
        """Test reading a YAML file."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("TEST_VAR: test_value\nNUMBER: 42")

        result = ConfigFileHandler.read_yaml_file(yaml_file)
        assert result["TEST_VAR"] == "test_value"
        assert result["NUMBER"] == 42

    def test_read_toml_file(self, tmp_path):
        """Test reading a TOML file."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('TEST_VAR = "test_value"\nNUMBER = 42')

        result = ConfigFileHandler.read_toml_file(toml_file)
        assert result["TEST_VAR"] == "test_value"
        assert result["NUMBER"] == 42

    def test_write_env_file(self, tmp_path):
        """Test writing a .env file."""
        env_file = tmp_path / "test.env"
        data = {"TEST_VAR": "test_value", "ANOTHER_VAR": "another_value"}

        ConfigFileHandler.write_env_file(env_file, data)
        content = env_file.read_text()
        assert "TEST_VAR=test_value" in content
        assert "ANOTHER_VAR=another_value" in content

    def test_write_json_file(self, tmp_path):
        """Test writing a JSON file."""
        json_file = tmp_path / "test.json"
        data = {"TEST_VAR": "test_value", "NUMBER": 42}

        ConfigFileHandler.write_json_file(json_file, data)
        result = json.loads(json_file.read_text())
        assert result["TEST_VAR"] == "test_value"
        assert result["NUMBER"] == 42

    def test_write_yaml_file(self, tmp_path):
        """Test writing a YAML file."""
        yaml_file = tmp_path / "test.yaml"
        data = {"TEST_VAR": "test_value", "NUMBER": 42}

        ConfigFileHandler.write_yaml_file(yaml_file, data)
        import yaml
        result = yaml.safe_load(yaml_file.read_text())
        assert result["TEST_VAR"] == "test_value"
        assert result["NUMBER"] == 42

    def test_write_toml_file(self, tmp_path):
        """Test writing a TOML file."""
        toml_file = tmp_path / "test.toml"
        data = {"TEST_VAR": "test_value", "NUMBER": 42}

        ConfigFileHandler.write_toml_file(toml_file, data)
        import toml
        result = toml.loads(toml_file.read_text())
        assert result["TEST_VAR"] == "test_value"
        assert result["NUMBER"] == 42


class TestTemplateRenderer:
    """Tests for TemplateRenderer."""

    def test_render_string_simple(self):
        """Test simple string rendering."""
        template = "Hello, {{ NAME }}!"
        variables = {"NAME": "World"}
        result = TemplateRenderer.render_string(template, variables)
        assert result == "Hello, World!"

    def test_render_string_with_spaces(self):
        """Test string rendering with variable spacing."""
        template = "Value: {{VALUE}}"
        variables = {"VALUE": "test"}
        result = TemplateRenderer.render_string(template, variables)
        assert result == "Value: test"

    def test_render_string_default(self):
        """Test string rendering with default values."""
        template = "Value: {{ MISSING | default('default_value') }}"
        variables = {}
        result = TemplateRenderer.render_string(template, variables)
        assert result == "Value: default_value"

    def test_render_dict(self):
        """Test dictionary rendering."""
        template_dict = {
            "greeting": "Hello, {{ NAME }}!",
            "nested": {
                "value": "{{ VALUE }}",
            },
        }
        variables = {"NAME": "World", "VALUE": "test"}
        result = TemplateRenderer.render_dict(template_dict, variables)
        assert result["greeting"] == "Hello, World!"
        assert result["nested"]["value"] == "test"

    def test_render_environment(self):
        """Test rendering environment variables."""
        now = datetime.now().isoformat()
        env = Environment(
            name="test",
            variables={
                "VAR1": ConfigVariable(name="VAR1", value="value1"),
                "VAR2": ConfigVariable(name="VAR2", value="value2"),
            },
            created_at=now,
            updated_at=now,
        )
        result = TemplateRenderer.render_environment(env)
        assert result["VAR1"] == "value1"
        assert result["VAR2"] == "value2"

    def test_render_environment_references(self):
        """Test rendering environment with variable references."""
        now = datetime.now().isoformat()
        env = Environment(
            name="test",
            variables={
                "BASE_URL": ConfigVariable(name="BASE_URL", value="http://example.com"),
                "API_URL": ConfigVariable(name="API_URL", value="{{ BASE_URL }}/api"),
            },
            created_at=now,
            updated_at=now,
        )
        result = TemplateRenderer.render_environment(env)
        assert result["BASE_URL"] == "http://example.com"
        assert result["API_URL"] == "http://example.com/api"
