"""Tests for export module."""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from envsync.export import (
    ConfigExporter,
    ExportFormat,
    ExportService,
    MultiEnvironmentExporter,
)


class TestConfigExporter:
    def test_export_to_json(self):
        exporter = ConfigExporter()
        data = {"key": "value", "nested": {"a": 1}}
        
        result = exporter.export_to_json(data)
        
        loaded = json.loads(result)
        assert loaded["key"] == "value"
        assert loaded["nested"]["a"] == 1

    def test_export_to_json_with_metadata(self):
        exporter = ConfigExporter()
        data = {"key": "value"}
        
        result = exporter.export_to_json(data, metadata={"env": "prod"})
        
        loaded = json.loads(result)
        assert "_metadata" in loaded
        assert loaded["_metadata"]["env"] == "prod"

    def test_export_to_yaml(self):
        exporter = ConfigExporter()
        data = {"key": "value", "nested": {"a": 1}}
        
        result = exporter.export_to_yaml(data)
        
        loaded = yaml.safe_load(result)
        assert loaded["key"] == "value"
        assert loaded["nested"]["a"] == 1

    def test_export_to_toml(self):
        exporter = ConfigExporter()
        data = {"key": "value", "nested": {"a": 1}}
        
        result = exporter.export_to_toml(data)
        
        assert 'key = "value"' in result

    def test_export_to_env(self):
        exporter = ConfigExporter()
        data = {"DB_HOST": "localhost", "DB_PORT": 5432}
        
        result = exporter.export_to_env(data)
        
        assert "DB_HOST=localhost" in result
        assert "DB_PORT=5432" in result

    def test_export_to_env_flatten(self):
        exporter = ConfigExporter(flatten_nested=True)
        data = {"database": {"host": "localhost", "port": 5432}}
        
        result = exporter.export_to_env(data)
        
        assert "DATABASE_HOST=localhost" in result
        assert "DATABASE_PORT=5432" in result

    def test_export_to_env_no_flatten(self):
        exporter = ConfigExporter(flatten_nested=False)
        data = {"database": {"host": "localhost"}}
        
        result = exporter.export_to_env(data)
        
        assert "DATABASE=" in result

    def test_export_to_csv(self):
        exporter = ConfigExporter()
        data = {"key1": "value1", "key2": "value2"}
        
        result = exporter.export_to_csv(data)
        
        assert "key,value,type" in result
        assert "key1,value1" in result

    def test_export_with_mask_sensitive(self):
        exporter = ConfigExporter(mask_sensitive=True, sensitive_fields=["*password*"])
        data = {"username": "admin", "password": "secret"}
        
        result = exporter.export_to_json(data)
        
        loaded = json.loads(result)
        assert loaded["username"] == "admin"
        assert loaded["password"] == "******"

    def test_export_method_json(self):
        exporter = ConfigExporter()
        data = {"key": "value"}
        
        result = exporter.export(data, "json")
        
        loaded = json.loads(result)
        assert loaded["key"] == "value"

    def test_export_method_yaml(self):
        exporter = ConfigExporter()
        data = {"key": "value"}
        
        result = exporter.export(data, "yaml")
        
        loaded = yaml.safe_load(result)
        assert loaded["key"] == "value"

    def test_export_method_env(self):
        exporter = ConfigExporter(flatten_nested=True)
        data = {"db_host": "localhost"}
        
        result = exporter.export(data, "env")
        
        assert "DB_HOST=localhost" in result

    def test_export_unsupported_format(self):
        exporter = ConfigExporter()
        
        with pytest.raises(ValueError):
            exporter.export({}, "invalid_format")

    def test_flatten_dict(self):
        exporter = ConfigExporter()
        
        data = {"a": {"b": {"c": 1}}}
        result = exporter._flatten_dict(data)
        
        assert result == {"a_b_c": 1}

    def test_flatten_dict_with_list(self):
        exporter = ConfigExporter()
        
        data = {"items": [1, 2, 3]}
        result = exporter._flatten_dict(data)
        
        assert "items_0" in result
        assert "items_1" in result


class TestMultiEnvironmentExporter:
    def test_export_to_directory(self, tmp_path):
        exporter = MultiEnvironmentExporter()
        
        environments = {
            "production": {"key": "prod"},
            "development": {"key": "dev"}
        }
        
        output_dir = tmp_path / "exports"
        files = exporter.export_to_directory(environments, output_dir)
        
        assert len(files) == 2
        assert (output_dir / "production.json").exists()
        assert (output_dir / "development.json").exists()

    def test_export_to_directory_custom_pattern(self, tmp_path):
        exporter = MultiEnvironmentExporter()
        
        environments = {"production": {"key": "value"}}
        
        output_dir = tmp_path / "exports"
        files = exporter.export_to_directory(
            environments,
            output_dir,
            format="yaml",
            filename_pattern="config_{environment}.{format}"
        )
        
        assert len(files) == 1
        assert (output_dir / "config_production.yaml").exists()

    def test_export_to_archive(self, tmp_path):
        exporter = MultiEnvironmentExporter()
        
        environments = {
            "production": {"key": "prod"},
            "development": {"key": "dev"}
        }
        
        archive_path = tmp_path / "configs.zip"
        result = exporter.export_to_archive(environments, archive_path)
        
        assert result.exists()
        assert result.suffix == ".zip"

    def test_export_combined(self):
        exporter = MultiEnvironmentExporter()
        
        environments = {
            "production": {"key": "prod"},
            "development": {"key": "dev"}
        }
        
        result = exporter.export_combined(environments)
        
        loaded = json.loads(result)
        assert "environments" in loaded
        assert "production" in loaded["environments"]

    def test_export_diff_report(self):
        exporter = MultiEnvironmentExporter()
        
        diff_data = {
            "added": [{"path": "new_key", "value": "new_value"}],
            "removed": [],
            "changed": []
        }
        
        result = exporter.export_diff_report(diff_data)
        
        loaded = json.loads(result)
        assert "added" in loaded


class TestExportService:
    def test_export_environment(self, tmp_path):
        service = ExportService(tmp_path)
        
        data = {"key": "value"}
        result = service.export_environment("production", data, "json")
        
        assert result.exists()
        assert result.name == "production.json"

    def test_export_environment_custom_path(self, tmp_path):
        service = ExportService(tmp_path)
        
        data = {"key": "value"}
        output_path = tmp_path / "custom" / "config.json"
        result = service.export_environment("production", data, "json", output_path)
        
        assert result == output_path
        assert output_path.exists()

    def test_export_environment_with_flatten(self, tmp_path):
        service = ExportService(tmp_path)
        
        data = {"database": {"host": "localhost"}}
        result = service.export_environment("production", data, "env", flatten=True)
        
        content = result.read_text()
        assert "DATABASE_HOST=localhost" in content

    def test_export_all_environments(self, tmp_path):
        service = ExportService(tmp_path)
        
        environments = {
            "production": {"key": "prod"},
            "development": {"key": "dev"}
        }
        
        files = service.export_all_environments(environments, format="yaml")
        
        assert len(files) == 2

    def test_export_to_archive(self, tmp_path):
        service = ExportService(tmp_path)
        
        environments = {
            "production": {"key": "prod"},
            "development": {"key": "dev"}
        }
        
        result = service.export_to_archive(environments)
        
        assert result.exists()
        assert result.suffix == ".zip"


class TestExportFormat:
    def test_format_values(self):
        assert ExportFormat.JSON == "json"
        assert ExportFormat.YAML == "yaml"
        assert ExportFormat.TOML == "toml"
        assert ExportFormat.ENV == "env"
        assert ExportFormat.DOTENV == "dotenv"
        assert ExportFormat.CSV == "csv"
