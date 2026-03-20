"""Tests for template module."""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from envsync.template import TemplateEngine, TemplateManager


class TestTemplateEngine:
    def test_render_env_style(self):
        engine = TemplateEngine(variables={"NAME": "world"})
        result = engine.render_string("Hello ${NAME}!")
        assert result == "Hello world!"

    def test_render_env_style_with_default(self):
        engine = TemplateEngine(variables={})
        result = engine.render_string("Hello ${NAME:-default}!")
        assert result == "Hello default!"

    def test_render_jinja_style(self):
        engine = TemplateEngine(variables={"name": "world"})
        result = engine.render_string("Hello {{ name }}!")
        assert result == "Hello world!"

    def test_render_nested_config(self):
        engine = TemplateEngine(variables={
            "DB_HOST": "localhost",
            "DB_PORT": "5432"
        })
        config = {
            "database": {
                "host": "${DB_HOST}",
                "port": "${DB_PORT}"
            }
        }
        result = engine.render_config(config)
        assert result["database"]["host"] == "localhost"
        assert result["database"]["port"] == "5432"

    def test_load_from_env(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "test_value")
        
        engine = TemplateEngine()
        engine.load_from_env()
        
        assert "test_var" in engine.variables

    def test_load_from_file(self, tmp_path):
        vars_file = tmp_path / "vars.json"
        vars_file.write_text(json.dumps({"KEY": "value"}))
        
        engine = TemplateEngine()
        engine.load_from_file(vars_file)
        
        assert engine.variables["KEY"] == "value"

    def test_strict_mode_undefined(self):
        engine = TemplateEngine(strict=True)
        
        with pytest.raises(ValueError):
            engine.render_string("${UNDEFINED}")

    def test_non_str_value(self):
        engine = TemplateEngine()
        result = engine.render_value(123)
        assert result == 123

    def test_render_list(self):
        engine = TemplateEngine(variables={"ITEM": "value"})
        result = engine.render_value(["${ITEM}", "static"])
        assert result == ["value", "static"]


class TestTemplateManager:
    def test_create_template(self, tmp_path):
        manager = TemplateManager(tmp_path)
        
        content = "app:\n  name: {{ name }}"
        variables = {"name": "myapp"}
        
        template_path = manager.create_template("test", content, variables)
        
        assert template_path.exists()
        assert template_path.name == "test.yaml"

    def test_load_template(self, tmp_path):
        manager = TemplateManager(tmp_path)
        
        content = "app:\n  name: {{ name }}"
        manager.create_template("test", content)
        
        loaded = manager.load_template("test")
        assert loaded == content

    def test_load_template_not_found(self, tmp_path):
        manager = TemplateManager(tmp_path)
        
        with pytest.raises(FileNotFoundError):
            manager.load_template("nonexistent")

    def test_save_variables(self, tmp_path):
        manager = TemplateManager(tmp_path)
        
        vars_path = manager.save_variables("test", {"key": "value"})
        
        assert vars_path.exists()
        loaded = json.loads(vars_path.read_text())
        assert loaded == {"key": "value"}

    def test_list_templates(self, tmp_path):
        manager = TemplateManager(tmp_path)
        
        manager.create_template("template1", "content1")
        manager.create_template("template2", "content2")
        
        templates = manager.list_templates()
        assert set(templates) == {"template1", "template2"}

    def test_render_template(self, tmp_path):
        manager = TemplateManager(tmp_path)
        
        content = "app:\n  name: ${NAME}\n  debug: ${DEBUG:-false}"
        manager.create_template("test", content)
        manager.save_variables("test", {"NAME": "myapp"})
        
        result = manager.render_template("test", variables={"DEBUG": "true"}, env_vars=False)
        
        assert result["app"]["name"] == "myapp"
        assert result["app"]["debug"] == "true"
