"""模板引擎测试."""

import tempfile
from pathlib import Path

import pytest

from envsync.config import ConfigManager
from envsync.models import ConfigFormat
from envsync.template import TemplateEngine


class TestTemplateEngine:
    """模板引擎测试."""

    @pytest.fixture
    def temp_dir(self):
        """临时目录."""
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def template_engine(self, temp_dir):
        """模板引擎实例."""
        config_manager = ConfigManager(base_dir=temp_dir)
        config_manager.init_project(name="test")
        config_manager.add_environment("dev")
        config_manager.set_variable("dev", "HOST", "localhost")
        config_manager.set_variable("dev", "PORT", "8080")
        return TemplateEngine(config_manager)

    def test_render_simple(self, template_engine):
        """测试简单渲染."""
        template = "host=${HOST}, port=${PORT}"
        variables = {"HOST": "localhost", "PORT": "8080"}
        result = template_engine.render(template, variables)

        assert result == "host=localhost, port=8080"

    def test_render_with_default(self, template_engine):
        """测试带默认值的渲染."""
        template = "port=${PORT:3000}"
        variables = {}
        result = template_engine.render(template, variables)

        assert result == "port=3000"

    def test_render_missing_variable(self, template_engine):
        """测试缺少变量."""
        template = "host=${MISSING}"
        variables = {}
        result = template_engine.render(template, variables, strict=False)

        assert result == "host=${MISSING}"

    def test_extract_variables(self, template_engine):
        """测试提取变量."""
        template = "${VAR1} and ${VAR2:default} and ${VAR1}"
        variables = template_engine.extract_variables(template)

        assert len(variables) == 2
        assert {"name": "VAR1", "default": None} in variables
        assert {"name": "VAR2", "default": "default"} in variables

    def test_validate_template(self, template_engine):
        """测试模板验证."""
        template = "${KNOWN} and ${UNKNOWN}"
        variables = {"KNOWN": "value"}
        missing = template_engine.validate_template(template, variables)

        assert "UNKNOWN" in missing
        assert "KNOWN" not in missing
