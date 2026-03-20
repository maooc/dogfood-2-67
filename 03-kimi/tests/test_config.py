"""配置管理测试."""

import tempfile
from pathlib import Path

import pytest

from envsync.config import ConfigManager
from envsync.models import ConfigFormat


class TestConfigManager:
    """配置管理器测试."""

    @pytest.fixture
    def temp_dir(self):
        """临时目录."""
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def config_manager(self, temp_dir):
        """配置管理器实例."""
        return ConfigManager(base_dir=temp_dir)

    def test_init_project(self, config_manager):
        """测试初始化项目."""
        config = config_manager.init_project(
            name="test_project",
            description="Test project",
            environments=["dev", "prod"],
        )

        assert config.name == "test_project"
        assert config.description == "Test project"
        assert "dev" in config.environments
        assert "prod" in config.environments

    def test_add_environment(self, config_manager):
        """测试添加环境."""
        config_manager.init_project(name="test", environments=["dev"])
        env = config_manager.add_environment("staging", "Staging environment")

        assert env.name == "staging"
        assert env.description == "Staging environment"
        assert "staging" in config_manager.config.environments

    def test_set_variable(self, config_manager):
        """测试设置变量."""
        config_manager.init_project(name="test")
        config_manager.add_environment("dev")
        config_manager.set_variable("dev", "DB_HOST", "localhost", "Database host")

        env = config_manager.get_environment("dev")
        assert "DB_HOST" in env.variables
        assert env.variables["DB_HOST"].value == "localhost"

    def test_add_config_file(self, config_manager, temp_dir):
        """测试添加配置文件."""
        config_manager.init_project(name="test")
        config_manager.add_environment("dev")

        config_file = config_manager.add_config_file(
            name="app",
            path=temp_dir / "app.yaml",
            format=ConfigFormat.YAML,
            environment="dev",
        )

        assert config_file.name == "app"
        assert config_file.environment == "dev"

    def test_get_merged_variables(self, config_manager):
        """测试获取合并变量."""
        config_manager.init_project(name="test")
        config_manager.add_environment("base")
        config_manager.add_environment("dev", parent="base")

        config_manager.set_variable("base", "SHARED", "base_value")
        config_manager.set_variable("dev", "SPECIFIC", "dev_value")
        config_manager.set_variable("dev", "SHARED", "dev_override")

        merged = config_manager.get_merged_variables("dev")
        assert merged["SPECIFIC"] == "dev_value"
        assert merged["SHARED"] == "dev_override"
