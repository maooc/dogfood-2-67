"""Template variable replacement module."""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from jinja2 import Environment, BaseLoader, TemplateSyntaxError


class TemplateEngine:
    """Template variable replacement engine supporting multiple syntaxes."""
    
    ENV_VAR_PATTERN = re.compile(r'\$\{([^}]+)\}')
    DOUBLE_BRACE_PATTERN = re.compile(r'\{\{([^}]+)\}\}')
    
    def __init__(
        self,
        variables: Optional[Dict[str, Any]] = None,
        env_prefix: str = "",
        strict: bool = False
    ):
        self.variables = variables or {}
        self.env_prefix = env_prefix
        self.strict = strict
        self.jinja_env = Environment(
            loader=BaseLoader(),
            undefined=self._get_undefined_handler()
        )
    
    def _get_undefined_handler(self):
        """Get Jinja2 undefined handler based on strict mode."""
        from jinja2 import StrictUndefined, Undefined
        return StrictUndefined if self.strict else Undefined
    
    def set_variables(self, variables: Dict[str, Any]) -> None:
        """Set template variables."""
        self.variables = variables
    
    def add_variable(self, key: str, value: Any) -> None:
        """Add a single template variable."""
        self.variables[key] = value
    
    def load_from_env(self, prefix: Optional[str] = None) -> None:
        """Load variables from environment variables."""
        prefix = prefix or self.env_prefix
        for key, value in os.environ.items():
            if prefix:
                if key.startswith(prefix):
                    var_name = key[len(prefix):].lstrip('_').lower()
                    self.variables[var_name] = value
            else:
                self.variables[key.lower()] = value
    
    def load_from_file(self, file_path: Path) -> None:
        """Load variables from a .env or JSON file."""
        if not file_path.exists():
            raise FileNotFoundError(f"Variables file not found: {file_path}")
        
        content = file_path.read_text(encoding="utf-8")
        
        if file_path.suffix == ".json":
            import json
            self.variables.update(json.loads(content))
        elif file_path.suffix in (".yaml", ".yml"):
            import yaml
            self.variables.update(yaml.safe_load(content) or {})
        else:
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    self.variables[key.strip()] = value.strip()
    
    def render_string(self, template: str) -> str:
        """Render a template string with variable substitution."""
        if not isinstance(template, str):
            return template
        
        if self.ENV_VAR_PATTERN.search(template):
            template = self._render_env_style(template)
        
        if self.DOUBLE_BRACE_PATTERN.search(template):
            template = self._render_jinja_style(template)
        
        return template
    
    def _render_env_style(self, template: str) -> str:
        """Render ${VAR} style templates."""
        def replace_var(match):
            var_expr = match.group(1).strip()
            
            if ":-" in var_expr:
                var_name, default = var_expr.split(":-", 1)
                return str(self.variables.get(var_name.strip(), default))
            elif "-" in var_expr:
                var_name, default = var_expr.split("-", 1)
                return str(self.variables.get(var_name.strip(), default))
            else:
                if var_expr in self.variables:
                    return str(self.variables[var_expr])
                elif self.strict:
                    raise ValueError(f"Undefined variable: {var_expr}")
                return match.group(0)
        
        return self.ENV_VAR_PATTERN.sub(replace_var, template)
    
    def _render_jinja_style(self, template: str) -> str:
        """Render {{ var }} style templates using Jinja2."""
        try:
            jinja_template = self.jinja_env.from_string(template)
            return jinja_template.render(**self.variables)
        except TemplateSyntaxError as e:
            raise ValueError(f"Template syntax error: {e}")
    
    def render_value(self, value: Any) -> Any:
        """Render a value, handling nested structures."""
        if isinstance(value, str):
            return self.render_string(value)
        elif isinstance(value, dict):
            return {k: self.render_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.render_value(item) for item in value]
        return value
    
    def render_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Render entire configuration with template substitution."""
        return self.render_value(config)


class TemplateManager:
    """Manage template files and variable files."""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.templates_dir = self.project_root / ".envsync" / "templates"
        self.variables_dir = self.project_root / ".envsync" / "variables"
    
    def create_template(
        self,
        name: str,
        content: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Create a new template file."""
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        template_path = self.templates_dir / f"{name}.yaml"
        template_path.write_text(content, encoding="utf-8")
        
        if variables:
            self.save_variables(name, variables)
        
        return template_path
    
    def save_variables(self, template_name: str, variables: Dict[str, Any]) -> Path:
        """Save variables file for a template."""
        self.variables_dir.mkdir(parents=True, exist_ok=True)
        variables_path = self.variables_dir / f"{template_name}.json"
        
        import json
        variables_path.write_text(
            json.dumps(variables, indent=2),
            encoding="utf-8"
        )
        
        return variables_path
    
    def load_template(self, name: str) -> str:
        """Load template content by name."""
        for ext in [".yaml", ".yml", ".json", ".toml"]:
            template_path = self.templates_dir / f"{name}{ext}"
            if template_path.exists():
                return template_path.read_text(encoding="utf-8")
        
        raise FileNotFoundError(f"Template '{name}' not found")
    
    def load_variables(self, name: str) -> Dict[str, Any]:
        """Load variables for a template."""
        for ext in [".json", ".yaml", ".yml", ".env"]:
            variables_path = self.variables_dir / f"{name}{ext}"
            if variables_path.exists():
                if ext == ".json":
                    import json
                    return json.loads(variables_path.read_text(encoding="utf-8"))
                elif ext in [".yaml", ".yml"]:
                    import yaml
                    return yaml.safe_load(variables_path.read_text(encoding="utf-8")) or {}
                else:
                    variables = {}
                    for line in variables_path.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            variables[key.strip()] = value.strip()
                    return variables
        
        return {}
    
    def list_templates(self) -> List[str]:
        """List all available templates."""
        if not self.templates_dir.exists():
            return []
        
        templates = []
        for file in self.templates_dir.iterdir():
            if file.is_file() and file.suffix in [".yaml", ".yml", ".json", ".toml"]:
                templates.append(file.stem)
        
        return sorted(templates)
    
    def render_template(
        self,
        template_name: str,
        variables: Optional[Dict[str, Any]] = None,
        env_vars: bool = True,
        strict: bool = False
    ) -> Dict[str, Any]:
        """Render a template with variables."""
        import yaml
        
        template_content = self.load_template(template_name)
        template_data = yaml.safe_load(template_content) or {}
        
        all_variables = {}
        
        if env_vars:
            engine = TemplateEngine(strict=strict)
            engine.load_from_env()
            all_variables.update(engine.variables)
        
        saved_variables = self.load_variables(template_name)
        all_variables.update(saved_variables)
        
        if variables:
            all_variables.update(variables)
        
        engine = TemplateEngine(variables=all_variables, strict=strict)
        return engine.render_config(template_data)
    
    def apply_template_to_environment(
        self,
        template_name: str,
        environment: str,
        variables: Optional[Dict[str, Any]] = None,
        output_path: Optional[Path] = None
    ) -> Path:
        """Apply a template to create or update an environment config."""
        from .config import ConfigManager, ConfigLoader, ConfigFormat
        
        rendered = self.render_template(template_name, variables)
        
        config_manager = ConfigManager(self.project_root)
        config_manager.load_project_config()
        
        env_config = config_manager.get_environment(environment)
        output_path = output_path or env_config.file_path
        
        ConfigLoader.save(output_path, rendered, env_config.format)
        
        return output_path
