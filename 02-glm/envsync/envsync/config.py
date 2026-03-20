"""Core configuration management module."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import toml
import yaml
from pydantic import BaseModel, Field


class ConfigFormat:
    """Supported configuration file formats."""
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    ENV = "env"

    @classmethod
    def detect(cls, file_path: Path) -> str:
        """Detect configuration format from file extension."""
        suffix = file_path.suffix.lower()
        name = file_path.name.lower()
        format_map = {
            ".json": cls.JSON,
            ".yaml": cls.YAML,
            ".yml": cls.YAML,
            ".toml": cls.TOML,
            ".env": cls.ENV,
        }
        if name == ".env":
            return cls.ENV
        return format_map.get(suffix, cls.JSON)


class EnvironmentConfig(BaseModel):
    """Configuration for a single environment."""
    name: str
    file_path: Path
    format: str
    data: Dict[str, Any] = Field(default_factory=dict)
    sensitive_fields: List[str] = Field(default_factory=list)
    
    class Config:
        arbitrary_types_allowed = True


class ProjectConfig(BaseModel):
    """Project-level configuration for envsync."""
    project_name: str
    environments: Dict[str, EnvironmentConfig] = Field(default_factory=dict)
    sensitive_fields: List[str] = Field(default_factory=list)
    schema_file: Optional[Path] = None
    snapshots_dir: Path = Field(default_factory=lambda: Path(".envsync/snapshots"))
    
    class Config:
        arbitrary_types_allowed = True


class ConfigLoader:
    """Load and parse configuration files in various formats."""
    
    @staticmethod
    def load(file_path: Path) -> Dict[str, Any]:
        """Load configuration from file."""
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        config_format = ConfigFormat.detect(file_path)
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        if config_format == ConfigFormat.JSON:
            return json.loads(content)
        elif config_format == ConfigFormat.YAML:
            return yaml.safe_load(content) or {}
        elif config_format == ConfigFormat.TOML:
            return toml.loads(content)
        elif config_format == ConfigFormat.ENV:
            return ConfigLoader._parse_env(content)
        else:
            raise ValueError(f"Unsupported configuration format: {config_format}")
    
    @staticmethod
    def _parse_env(content: str) -> Dict[str, Any]:
        """Parse .env file format."""
        result = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                result[key] = value
        return result
    
    @staticmethod
    def save(file_path: Path, data: Dict[str, Any], config_format: Optional[str] = None) -> None:
        """Save configuration to file."""
        if config_format is None:
            config_format = ConfigFormat.detect(file_path)
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        if config_format == ConfigFormat.JSON:
            content = json.dumps(data, indent=2, ensure_ascii=False)
        elif config_format == ConfigFormat.YAML:
            content = yaml.dump(data, default_flow_style=False, allow_unicode=True)
        elif config_format == ConfigFormat.TOML:
            content = toml.dumps(data)
        elif config_format == ConfigFormat.ENV:
            content = ConfigLoader._format_env(data)
        else:
            raise ValueError(f"Unsupported configuration format: {config_format}")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
    
    @staticmethod
    def _format_env(data: Dict[str, Any]) -> str:
        """Format data as .env file content."""
        lines = []
        for key, value in data.items():
            if isinstance(value, str):
                if " " in value or '"' in value or "'" in value:
                    value = f'"{value}"'
            else:
                value = str(value)
            lines.append(f"{key}={value}")
        return "\n".join(lines)


class ConfigManager:
    """Manage multiple environment configurations."""
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.config_dir = self.project_root / ".envsync"
        self.project_config: Optional[ProjectConfig] = None
    
    def init_project(self, project_name: str) -> Path:
        """Initialize envsync project configuration."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        config_file = self.config_dir / "config.json"
        self.project_config = ProjectConfig(
            project_name=project_name,
            snapshots_dir=self.config_dir / "snapshots"
        )
        
        self._save_project_config()
        return config_file
    
    def _save_project_config(self) -> None:
        """Save project configuration to disk."""
        if self.project_config is None:
            return
        
        config_file = self.config_dir / "config.json"
        config_data = {
            "project_name": self.project_config.project_name,
            "environments": {
                name: {
                    "name": env.name,
                    "file_path": str(env.file_path),
                    "format": env.format,
                    "sensitive_fields": env.sensitive_fields,
                }
                for name, env in self.project_config.environments.items()
            },
            "sensitive_fields": self.project_config.sensitive_fields,
            "schema_file": str(self.project_config.schema_file) if self.project_config.schema_file else None,
            "snapshots_dir": str(self.project_config.snapshots_dir),
        }
        
        ConfigLoader.save(config_file, config_data)
    
    def load_project_config(self) -> ProjectConfig:
        """Load project configuration from disk."""
        config_file = self.config_dir / "config.json"
        
        if not config_file.exists():
            raise FileNotFoundError(
                "Project not initialized. Run 'envsync init' first."
            )
        
        data = ConfigLoader.load(config_file)
        
        environments = {}
        for name, env_data in data.get("environments", {}).items():
            environments[name] = EnvironmentConfig(
                name=env_data["name"],
                file_path=Path(env_data["file_path"]),
                format=env_data["format"],
                sensitive_fields=env_data.get("sensitive_fields", []),
            )
        
        self.project_config = ProjectConfig(
            project_name=data["project_name"],
            environments=environments,
            sensitive_fields=data.get("sensitive_fields", []),
            schema_file=Path(data["schema_file"]) if data.get("schema_file") else None,
            snapshots_dir=Path(data.get("snapshots_dir", ".envsync/snapshots")),
        )
        
        return self.project_config
    
    def add_environment(
        self,
        name: str,
        file_path: Path,
        sensitive_fields: Optional[List[str]] = None
    ) -> EnvironmentConfig:
        """Add a new environment configuration."""
        if self.project_config is None:
            self.load_project_config()
        
        if not file_path.is_absolute():
            file_path = self.project_root / file_path
        
        config_format = ConfigFormat.detect(file_path)
        
        env_config = EnvironmentConfig(
            name=name,
            file_path=file_path,
            format=config_format,
            sensitive_fields=sensitive_fields or [],
        )
        
        self.project_config.environments[name] = env_config
        self._save_project_config()
        
        return env_config
    
    def remove_environment(self, name: str) -> bool:
        """Remove an environment configuration."""
        if self.project_config is None:
            self.load_project_config()
        
        if name in self.project_config.environments:
            del self.project_config.environments[name]
            self._save_project_config()
            return True
        return False
    
    def load_environment(self, name: str) -> Dict[str, Any]:
        """Load configuration data for an environment."""
        if self.project_config is None:
            self.load_project_config()
        
        if name not in self.project_config.environments:
            raise ValueError(f"Environment '{name}' not found")
        
        env_config = self.project_config.environments[name]
        data = ConfigLoader.load(env_config.file_path)
        env_config.data = data
        
        return data
    
    def save_environment(self, name: str, data: Dict[str, Any]) -> None:
        """Save configuration data for an environment."""
        if self.project_config is None:
            self.load_project_config()
        
        if name not in self.project_config.environments:
            raise ValueError(f"Environment '{name}' not found")
        
        env_config = self.project_config.environments[name]
        ConfigLoader.save(env_config.file_path, data, env_config.format)
        env_config.data = data
    
    def list_environments(self) -> List[str]:
        """List all configured environments."""
        if self.project_config is None:
            self.load_project_config()
        
        return list(self.project_config.environments.keys())
    
    def get_environment(self, name: str) -> EnvironmentConfig:
        """Get environment configuration by name."""
        if self.project_config is None:
            self.load_project_config()
        
        if name not in self.project_config.environments:
            raise ValueError(f"Environment '{name}' not found")
        
        return self.project_config.environments[name]
    
    def set_sensitive_fields(self, fields: List[str]) -> None:
        """Set global sensitive field patterns."""
        if self.project_config is None:
            self.load_project_config()
        
        self.project_config.sensitive_fields = fields
        self._save_project_config()
    
    def set_schema_file(self, schema_path: Path) -> None:
        """Set JSON schema file for validation."""
        if self.project_config is None:
            self.load_project_config()
        
        if not schema_path.is_absolute():
            schema_path = self.project_root / schema_path
        
        self.project_config.schema_file = schema_path
        self._save_project_config()
