"""Pytest configuration and fixtures."""

import json
import tempfile
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project with configuration files."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    
    envsync_dir = project_root / ".envsync"
    envsync_dir.mkdir()
    
    project_config = {
        "project_name": "test_app",
        "environments": {},
        "schema_file": None,
        "sensitive_fields": []
    }
    
    config_file = envsync_dir / "config.json"
    config_file.write_text(json.dumps(project_config))
    
    configs_dir = project_root / "configs"
    configs_dir.mkdir()
    
    prod_config = {
        "app": {"name": "test_app", "version": "1.0.0"},
        "database": {"host": "localhost", "port": 5432},
        "debug": False
    }
    (configs_dir / "production.json").write_text(json.dumps(prod_config))
    
    dev_config = {
        "app": {"name": "test_app", "version": "1.0.0-dev"},
        "database": {"host": "localhost", "port": 5432},
        "debug": True
    }
    (configs_dir / "development.json").write_text(json.dumps(dev_config))
    
    staging_config = {
        "app": {"name": "test_app", "version": "1.0.0-staging"},
        "database": {"host": "staging.db", "port": 5432},
        "debug": False
    }
    (configs_dir / "staging.yaml").write_text(yaml.dump(staging_config))
    
    return project_root


@pytest.fixture
def sample_config():
    """Sample configuration data."""
    return {
        "app": {
            "name": "myapp",
            "version": "1.0.0",
            "debug": False
        },
        "database": {
            "host": "localhost",
            "port": 5432,
            "name": "mydb",
            "username": "admin",
            "password": "secret"
        },
        "features": {
            "cache_enabled": True,
            "rate_limit": 1000
        }
    }


@pytest.fixture
def sample_schema():
    """Sample JSON schema for validation."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["app", "database"],
        "properties": {
            "app": {
                "type": "object",
                "required": ["name", "version"],
                "properties": {
                    "name": {"type": "string"},
                    "version": {"type": "string"},
                    "debug": {"type": "boolean"}
                }
            },
            "database": {
                "type": "object",
                "required": ["host", "port"],
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                    "name": {"type": "string"}
                }
            }
        }
    }
