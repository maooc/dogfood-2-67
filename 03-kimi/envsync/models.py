"""数据模型定义."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ConfigFormat(str, Enum):
    """支持的配置文件格式."""

    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    ENV = "env"


class Variable(BaseModel):
    """模板变量定义."""

    name: str
    value: str
    description: Optional[str] = None
    is_sensitive: bool = False


class Environment(BaseModel):
    """环境配置."""

    name: str
    description: Optional[str] = None
    variables: Dict[str, Variable] = Field(default_factory=dict)
    parent: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @model_validator(mode="after")
    def update_timestamp(self) -> Environment:
        """更新时自动修改 updated_at."""
        self.updated_at = datetime.now()
        return self


class ConfigFile(BaseModel):
    """配置文件定义."""

    name: str
    path: Path
    format: ConfigFormat
    environment: str
    template: Optional[Path] = None
    encrypted_fields: List[str] = Field(default_factory=list)
    schema_path: Optional[Path] = None


class Snapshot(BaseModel):
    """配置快照."""

    id: str
    environment: str
    created_at: datetime = Field(default_factory=datetime.now)
    description: Optional[str] = None
    files: Dict[str, str] = Field(default_factory=dict)
    variables: Dict[str, str] = Field(default_factory=dict)


class ValidationRule(BaseModel):
    """配置校验规则."""

    field: str
    required: bool = True
    type: Optional[str] = None
    pattern: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[Any]] = None
    custom_message: Optional[str] = None


class ValidationResult(BaseModel):
    """校验结果."""

    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ProjectConfig(BaseModel):
    """项目配置."""

    model_config = {"arbitrary_types_allowed": True}

    name: str
    version: str = "1.0.0"
    description: Optional[str] = None
    base_dir: Path = Field(default=Path("."))
    environments: Dict[str, Environment] = Field(default_factory=dict)
    config_files: List[ConfigFile] = Field(default_factory=list)
    validation_rules: List[ValidationRule] = Field(default_factory=list)
    encryption_key_path: Optional[Path] = None
    snapshots_dir: Path = Field(default=Path(".envsync/snapshots"))
    templates_dir: Path = Field(default=Path(".envsync/templates"))
