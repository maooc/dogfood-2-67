"""Core configuration management for envsync."""

import os
import json
import hashlib
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import yaml
import toml
from dotenv import dotenv_values


class ConfigFormat(Enum):
    """Supported configuration file formats."""
    ENV = "env"
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"


@dataclass
class ConfigVariable:
    """Represents a configuration variable with metadata."""
    name: str
    value: str
    description: Optional[str] = None
    encrypted: bool = False
    required: bool = False
    type: str = "string"  # string, int, bool, float
    pattern: Optional[str] = None


@dataclass
class Environment:
    """Represents an environment configuration."""
    name: str
    variables: Dict[str, ConfigVariable]
    created_at: str
    updated_at: str
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "variables": {k: asdict(v) for k, v in self.variables.items()},
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Environment":
        """Create from dictionary."""
        variables = {
            k: ConfigVariable(**v) for k, v in data.get("variables", {}).items()
        }
        return cls(
            name=data["name"],
            description=data.get("description"),
            variables=variables,
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


@dataclass
class Template:
    """Represents a configuration template."""
    name: str
    variables: Dict[str, Dict[str, Any]]  # variable name -> schema
    required: List[str]
    sensitive: List[str]
    created_at: str
    updated_at: str
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "variables": self.variables,
            "required": self.required,
            "sensitive": self.sensitive,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Template":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            description=data.get("description"),
            variables=data.get("variables", {}),
            required=data.get("required", []),
            sensitive=data.get("sensitive", []),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


@dataclass
class Snapshot:
    """Represents a configuration snapshot."""
    id: str
    name: str
    timestamp: str
    environments: List[str]
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Snapshot":
        """Create from dictionary."""
        return cls(**data)


class ConfigManager:
    """Manages configuration storage and retrieval."""

    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize the config manager.

        Args:
            base_dir: Optional base directory for storing configurations.
                     Defaults to ~/.config/envsync.
        """
        if base_dir is None:
            self.base_dir = Path.home() / ".config" / "envsync"
        else:
            self.base_dir = Path(base_dir)

        self.environments_dir = self.base_dir / "environments"
        self.templates_dir = self.base_dir / "templates"
        self.snapshots_dir = self.base_dir / "snapshots"
        self.snapshot_data_dir = self.base_dir / "snapshot_data"

        # Create directories if they don't exist
        for d in [
            self.base_dir,
            self.environments_dir,
            self.templates_dir,
            self.snapshots_dir,
            self.snapshot_data_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

    def get_environment_path(self, name: str) -> Path:
        """Get the path to an environment file."""
        return self.environments_dir / f"{name}.json"

    def get_template_path(self, name: str) -> Path:
        """Get the path to a template file."""
        return self.templates_dir / f"{name}.json"

    def get_snapshot_path(self, snapshot_id: str) -> Path:
        """Get the path to a snapshot metadata file."""
        return self.snapshots_dir / f"{snapshot_id}.json"

    def get_snapshot_data_path(self, snapshot_id: str) -> Path:
        """Get the path to a snapshot data directory."""
        return self.snapshot_data_dir / snapshot_id

    def save_environment(self, env: Environment) -> None:
        """Save an environment to disk."""
        env.updated_at = datetime.now().isoformat()
        path = self.get_environment_path(env.name)
        with open(path, "w") as f:
            json.dump(env.to_dict(), f, indent=2)

    def load_environment(self, name: str) -> Optional[Environment]:
        """Load an environment from disk."""
        path = self.get_environment_path(name)
        if not path.exists():
            return None
        with open(path, "r") as f:
            data = json.load(f)
        return Environment.from_dict(data)

    def delete_environment(self, name: str) -> bool:
        """Delete an environment."""
        path = self.get_environment_path(name)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_environments(self) -> List[str]:
        """List all available environments."""
        return [f.stem for f in self.environments_dir.glob("*.json")]

    def environment_exists(self, name: str) -> bool:
        """Check if an environment exists."""
        return self.get_environment_path(name).exists()

    def save_template(self, template: Template) -> None:
        """Save a template to disk."""
        template.updated_at = datetime.now().isoformat()
        path = self.get_template_path(template.name)
        with open(path, "w") as f:
            json.dump(template.to_dict(), f, indent=2)

    def load_template(self, name: str) -> Optional[Template]:
        """Load a template from disk."""
        path = self.get_template_path(name)
        if not path.exists():
            return None
        with open(path, "r") as f:
            data = json.load(f)
        return Template.from_dict(data)

    def delete_template(self, name: str) -> bool:
        """Delete a template."""
        path = self.get_template_path(name)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_templates(self) -> List[str]:
        """List all available templates."""
        return [f.stem for f in self.templates_dir.glob("*.json")]

    def template_exists(self, name: str) -> bool:
        """Check if a template exists."""
        return self.get_template_path(name).exists()

    def create_snapshot(self, name: str, description: Optional[str] = None) -> Snapshot:
        """Create a snapshot of all environments."""
        snapshot_id = hashlib.md5(
            (name + datetime.now().isoformat()).encode()
        ).hexdigest()[:8]

        snapshot = Snapshot(
            id=snapshot_id,
            name=name,
            description=description,
            timestamp=datetime.now().isoformat(),
            environments=self.list_environments(),
        )

        # Save snapshot metadata
        with open(self.get_snapshot_path(snapshot_id), "w") as f:
            json.dump(snapshot.to_dict(), f, indent=2)

        # Copy environment files to snapshot data directory
        snapshot_data_dir = self.get_snapshot_data_path(snapshot_id)
        snapshot_data_dir.mkdir(exist_ok=True)

        for env_name in snapshot.environments:
            src = self.get_environment_path(env_name)
            dst = snapshot_data_dir / f"{env_name}.json"
            shutil.copy2(src, dst)

        return snapshot

    def load_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        """Load snapshot metadata."""
        path = self.get_snapshot_path(snapshot_id)
        if not path.exists():
            return None
        with open(path, "r") as f:
            data = json.load(f)
        return Snapshot.from_dict(data)

    def restore_snapshot(self, snapshot_id: str) -> bool:
        """Restore environments from a snapshot."""
        snapshot_data_dir = self.get_snapshot_data_path(snapshot_id)
        if not snapshot_data_dir.exists():
            return False

        # Clear existing environments
        for env_file in self.environments_dir.glob("*.json"):
            env_file.unlink()

        # Restore from snapshot
        for env_file in snapshot_data_dir.glob("*.json"):
            dst = self.environments_dir / env_file.name
            shutil.copy2(env_file, dst)

        return True

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot."""
        metadata_path = self.get_snapshot_path(snapshot_id)
        data_dir = self.get_snapshot_data_path(snapshot_id)

        deleted = False
        if metadata_path.exists():
            metadata_path.unlink()
            deleted = True

        if data_dir.exists():
            shutil.rmtree(data_dir)
            deleted = True

        return deleted

    def list_snapshots(self) -> List[Snapshot]:
        """List all snapshots."""
        snapshots = []
        for f in self.snapshots_dir.glob("*.json"):
            with open(f, "r") as fp:
                data = json.load(fp)
            snapshots.append(Snapshot.from_dict(data))
        return sorted(snapshots, key=lambda x: x.timestamp, reverse=True)

    def snapshot_exists(self, snapshot_id: str) -> bool:
        """Check if a snapshot exists."""
        return self.get_snapshot_path(snapshot_id).exists()


class ConfigFileHandler:
    """Handles reading and writing configuration files in various formats."""

    @staticmethod
    def read_env_file(path: Path) -> Dict[str, str]:
        """Read a .env file."""
        return dict(dotenv_values(path))

    @staticmethod
    def read_json_file(path: Path) -> Dict[str, Any]:
        """Read a JSON file."""
        with open(path, "r") as f:
            return json.load(f)

    @staticmethod
    def read_yaml_file(path: Path) -> Dict[str, Any]:
        """Read a YAML file."""
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}

    @staticmethod
    def read_toml_file(path: Path) -> Dict[str, Any]:
        """Read a TOML file."""
        return toml.load(path)

    @classmethod
    def read_file(cls, path: Path, fmt: Optional[ConfigFormat] = None) -> Dict[str, Any]:
        """Read a configuration file in any supported format."""
        if fmt is None:
            # Auto-detect from file extension
            if path.suffix == ".env":
                fmt = ConfigFormat.ENV
            elif path.suffix == ".json":
                fmt = ConfigFormat.JSON
            elif path.suffix in (".yaml", ".yml"):
                fmt = ConfigFormat.YAML
            elif path.suffix in (".toml", ".tml"):
                fmt = ConfigFormat.TOML
            else:
                raise ValueError(f"Cannot determine format for file: {path}")

        if fmt == ConfigFormat.ENV:
            return cls.read_env_file(path)
        elif fmt == ConfigFormat.JSON:
            return cls.read_json_file(path)
        elif fmt == ConfigFormat.YAML:
            return cls.read_yaml_file(path)
        elif fmt == ConfigFormat.TOML:
            return cls.read_toml_file(path)
        else:
            raise ValueError(f"Unsupported format: {fmt}")

    @staticmethod
    def write_env_file(path: Path, data: Dict[str, str]) -> None:
        """Write a .env file."""
        with open(path, "w") as f:
            for key, value in data.items():
                f.write(f"{key}={value}\n")

    @staticmethod
    def write_json_file(path: Path, data: Dict[str, Any]) -> None:
        """Write a JSON file."""
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def write_yaml_file(path: Path, data: Dict[str, Any]) -> None:
        """Write a YAML file."""
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    @staticmethod
    def write_toml_file(path: Path, data: Dict[str, Any]) -> None:
        """Write a TOML file."""
        with open(path, "w") as f:
            toml.dump(data, f)

    @classmethod
    def write_file(
        cls, path: Path, data: Dict[str, Any], fmt: Optional[ConfigFormat] = None
    ) -> None:
        """Write a configuration file in any supported format."""
        if fmt is None:
            # Auto-detect from file extension
            if path.suffix == ".env":
                fmt = ConfigFormat.ENV
            elif path.suffix == ".json":
                fmt = ConfigFormat.JSON
            elif path.suffix in (".yaml", ".yml"):
                fmt = ConfigFormat.YAML
            elif path.suffix in (".toml", ".tml"):
                fmt = ConfigFormat.TOML
            else:
                raise ValueError(f"Cannot determine format for file: {path}")

        if fmt == ConfigFormat.ENV:
            cls.write_env_file(path, data)
        elif fmt == ConfigFormat.JSON:
            cls.write_json_file(path, data)
        elif fmt == ConfigFormat.YAML:
            cls.write_yaml_file(path, data)
        elif fmt == ConfigFormat.TOML:
            cls.write_toml_file(path, data)
        else:
            raise ValueError(f"Unsupported format: {fmt}")


class TemplateRenderer:
    """Renders templates with variable substitution."""

    @staticmethod
    def render_string(template: str, variables: Dict[str, str]) -> str:
        """Render a template string with variable substitution.

        Supports:
        - {{ variable_name }} for substitution
        - {{ variable_name | default('value') }} for defaults
        """
        result = template

        # Handle defaults first (to avoid partial substitution)
        import re

        # Pattern for {{ var | default('val') }} or {{ var | default("val") }}
        # This handles:
        # - {{ var | default('value') }}
        # - {{ var | default("value") }}
        # - {{var|default('value')}}
        # - {{ var | default(5) }} (for numeric values)
        pattern = r"\{\{\s*(\w+)\s*\|\s*default\(\s*['\"]?([^'\")\s]+)['\"]?\s*\)\s*\}\}"

        def replace_default(match):
            var_name = match.group(1)
            default_val = match.group(2)
            return str(variables.get(var_name, default_val))

        result = re.sub(pattern, replace_default, result)

        # Simple substitution
        for key, value in variables.items():
            # Try multiple patterns for variable substitution
            result = result.replace("{{ " + key + " }}", str(value))
            result = result.replace("{{" + key + "}}", str(value))
            result = result.replace("{{ " + key + "}}", str(value))
            result = result.replace("{{" + key + " }}", str(value))

        return result

    @staticmethod
    def render_dict(
        template_dict: Dict[str, Any], variables: Dict[str, str]
    ) -> Dict[str, Any]:
        """Render a dictionary with template strings."""
        result = {}
        for key, value in template_dict.items():
            if isinstance(value, str):
                result[key] = TemplateRenderer.render_string(value, variables)
            elif isinstance(value, dict):
                result[key] = TemplateRenderer.render_dict(value, variables)
            elif isinstance(value, list):
                result[key] = [
                    (
                        TemplateRenderer.render_string(item, variables)
                        if isinstance(item, str)
                        else item
                    )
                    for item in value
                ]
            else:
                result[key] = value
        return result

    @staticmethod
    def render_file(
        input_path: Path,
        output_path: Path,
        variables: Dict[str, str],
        fmt: Optional[ConfigFormat] = None,
    ) -> None:
        """Render a template file to an output file."""
        data = ConfigFileHandler.read_file(input_path, fmt)
        rendered = TemplateRenderer.render_dict(data, variables)
        ConfigFileHandler.write_file(output_path, rendered, fmt)

    @staticmethod
    def render_environment(
        environment: Environment, extra_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Render all variables in an environment, resolving any template references."""
        variables = {k: v.value for k, v in environment.variables.items()}
        if extra_vars:
            variables.update(extra_vars)

        # First pass: collect all variable values
        # Second pass: render any variable that references others
        rendered = {}
        for key, value in variables.items():
            if isinstance(value, str):
                rendered[key] = TemplateRenderer.render_string(value, variables)
            else:
                rendered[key] = value

        return rendered
