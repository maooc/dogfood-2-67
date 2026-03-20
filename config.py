"""配置管理核心模块."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import toml
import yaml
from dotenv import dotenv_values

from envsync.models import (
    ConfigFile,
    ConfigFormat,
    Environment,
    ProjectConfig,
    ValidationRule,
)


class ConfigManager:
    """配置管理器."""

    CONFIG_FILE = ".envsync/config.yaml"

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        """初始化配置管理器.

        Args:
            base_dir: 项目根目录，默认为当前目录
        """
        self.base_dir = base_dir or Path.cwd()
        self.config_path = self.base_dir / self.CONFIG_FILE
        self._config: Optional[ProjectConfig] = None

    @property
    def config(self) -> ProjectConfig:
        """获取项目配置."""
        if self._config is None:
            self._config = self.load_config()
        return self._config

    def init_project(
        self,
        name: str,
        description: Optional[str] = None,
        environments: Optional[List[str]] = None,
    ) -> ProjectConfig:
        """初始化新项目.

        Args:
            name: 项目名称
            description: 项目描述
            environments: 初始环境列表

        Returns:
            项目配置对象
        """
        envsync_dir = self.base_dir / ".envsync"
        envsync_dir.mkdir(exist_ok=True)

        (envsync_dir / "snapshots").mkdir(exist_ok=True)
        (envsync_dir / "templates").mkdir(exist_ok=True)
        (envsync_dir / "keys").mkdir(exist_ok=True)

        envs: Dict[str, Environment] = {}
        for env_name in environments or ["development", "staging", "production"]:
            envs[env_name] = Environment(name=env_name)

        project_config = ProjectConfig(
            name=name,
            description=description,
            base_dir=self.base_dir,
            environments=envs,
            encryption_key_path=envsync_dir / "keys" / "master.key",
        )

        self._config = project_config
        self.save_config()
        return project_config

    def load_config(self) -> ProjectConfig:
        """加载项目配置.

        Returns:
            项目配置对象

        Raises:
            FileNotFoundError: 配置文件不存在
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return ProjectConfig(**data)

    def save_config(self) -> None:
        """保存项目配置到文件."""
        if self._config is None:
            return

        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        data = self._config.model_dump()
        data["base_dir"] = str(data["base_dir"])
        data["snapshots_dir"] = str(data["snapshots_dir"])
        data["templates_dir"] = str(data["templates_dir"])
        data["encryption_key_path"] = (
            str(data["encryption_key_path"]) if data["encryption_key_path"] else None
        )

        for cf in data.get("config_files", []):
            cf["path"] = str(cf["path"])
            if cf.get("template"):
                cf["template"] = str(cf["template"])
            if cf.get("schema_path"):
                cf["schema_path"] = str(cf["schema_path"])

        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    def add_environment(
        self,
        name: str,
        description: Optional[str] = None,
        parent: Optional[str] = None,
    ) -> Environment:
        """添加新环境.

        Args:
            name: 环境名称
            description: 环境描述
            parent: 父环境名称（用于继承变量）

        Returns:
            新创建的环境对象
        """
        if name in self.config.environments:
            raise ValueError(f"环境已存在: {name}")

        if parent and parent not in self.config.environments:
            raise ValueError(f"父环境不存在: {parent}")

        env = Environment(name=name, description=description, parent=parent)
        self.config.environments[name] = env
        self.save_config()
        return env

    def remove_environment(self, name: str, force: bool = False) -> None:
        """删除环境.

        Args:
            name: 环境名称
            force: 是否强制删除，即使存在关联的配置文件

        Raises:
            ValueError: 环境不存在或存在关联配置文件
        """
        if name not in self.config.environments:
            raise ValueError(f"环境不存在: {name}")

        related_files = [cf for cf in self.config.config_files if cf.environment == name]
        if related_files and not force:
            raise ValueError(f"环境 {name} 存在 {len(related_files)} 个关联配置文件，使用 --force 强制删除")

        del self.config.environments[name]

        self.config.config_files = [cf for cf in self.config.config_files if cf.environment != name]

        self.save_config()

    def add_config_file(
        self,
        name: str,
        path: Path,
        format: ConfigFormat,
        environment: str,
        template: Optional[Path] = None,
        encrypted_fields: Optional[List[str]] = None,
        schema_path: Optional[Path] = None,
    ) -> ConfigFile:
        """添加配置文件.

        Args:
            name: 配置文件名称
            path: 配置文件路径
            format: 配置文件格式
            environment: 所属环境
            template: 模板文件路径
            encrypted_fields: 需要加密的字段列表
            schema_path: 校验模式文件路径

        Returns:
            新创建的配置文件对象
        """
        if environment not in self.config.environments:
            raise ValueError(f"环境不存在: {environment}")

        config_file = ConfigFile(
            name=name,
            path=path,
            format=format,
            environment=environment,
            template=template,
            encrypted_fields=encrypted_fields or [],
            schema_path=schema_path,
        )

        self.config.config_files.append(config_file)
        self.save_config()
        return config_file

    def remove_config_file(self, name: str) -> None:
        """删除配置文件.

        Args:
            name: 配置文件名称
        """
        self.config.config_files = [cf for cf in self.config.config_files if cf.name != name]
        self.save_config()

    def get_environment(self, name: str) -> Optional[Environment]:
        """获取环境配置.

        Args:
            name: 环境名称

        Returns:
            环境对象，不存在则返回 None
        """
        return self.config.environments.get(name)

    def get_config_file(self, name: str) -> Optional[ConfigFile]:
        """获取配置文件.

        Args:
            name: 配置文件名称

        Returns:
            配置文件对象，不存在则返回 None
        """
        for cf in self.config.config_files:
            if cf.name == name:
                return cf
        return None

    def get_environment_files(self, environment: str) -> List[ConfigFile]:
        """获取环境的所有配置文件.

        Args:
            environment: 环境名称

        Returns:
            配置文件列表
        """
        return [cf for cf in self.config.config_files if cf.environment == environment]

    def set_variable(
        self,
        environment: str,
        name: str,
        value: str,
        description: Optional[str] = None,
        is_sensitive: bool = False,
    ) -> None:
        """设置环境变量.

        Args:
            environment: 环境名称
            name: 变量名
            value: 变量值
            description: 变量描述
            is_sensitive: 是否为敏感字段
        """
        from envsync.models import Variable

        env = self.config.environments.get(environment)
        if not env:
            raise ValueError(f"环境不存在: {environment}")

        env.variables[name] = Variable(
            name=name,
            value=value,
            description=description,
            is_sensitive=is_sensitive,
        )
        self.save_config()

    def remove_variable(self, environment: str, name: str) -> None:
        """删除环境变量.

        Args:
            environment: 环境名称
            name: 变量名
        """
        env = self.config.environments.get(environment)
        if env and name in env.variables:
            del env.variables[name]
            self.save_config()

    def get_merged_variables(self, environment: str) -> Dict[str, str]:
        """获取合并后的变量（包含继承的父环境变量）.

        Args:
            environment: 环境名称

        Returns:
            变量名字典
        """
        env = self.config.environments.get(environment)
        if not env:
            raise ValueError(f"环境不存在: {environment}")

        result: Dict[str, str] = {}

        if env.parent:
            result.update(self.get_merged_variables(env.parent))

        for var in env.variables.values():
            result[var.name] = var.value

        return result

    @staticmethod
    def load_config_file(path: Path, format: ConfigFormat) -> Dict[str, Any]:
        """加载配置文件内容.

        Args:
            path: 文件路径
            format: 文件格式

        Returns:
            配置数据字典
        """
        if not path.exists():
            return {}

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        if format == ConfigFormat.JSON:
            return json.loads(content) if content.strip() else {}
        elif format == ConfigFormat.YAML:
            return yaml.safe_load(content) or {}
        elif format == ConfigFormat.TOML:
            return toml.loads(content)
        elif format == ConfigFormat.ENV:
            return dict(dotenv_values(path))
        else:
            raise ValueError(f"不支持的格式: {format}")

    @staticmethod
    def save_config_file(path: Path, format: ConfigFormat, data: Dict[str, Any]) -> None:
        """保存配置文件内容.

        Args:
            path: 文件路径
            format: 文件格式
            data: 配置数据
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            if format == ConfigFormat.JSON:
                json.dump(data, f, indent=2, ensure_ascii=False)
            elif format == ConfigFormat.YAML:
                yaml.dump(data, f, allow_unicode=True, sort_keys=False)
            elif format == ConfigFormat.TOML:
                toml.dump(data, f)
            elif format == ConfigFormat.ENV:
                for key, value in data.items():
                    f.write(f"{key}={value}\n")
            else:
                raise ValueError(f"不支持的格式: {format}")

    def add_validation_rule(self, rule: ValidationRule) -> None:
        """添加校验规则.

        Args:
            rule: 校验规则
        """
        self.config.validation_rules.append(rule)
        self.save_config()

    def remove_validation_rule(self, field: str) -> None:
        """删除校验规则.

        Args:
            field: 字段名
        """
        self.config.validation_rules = [r for r in self.config.validation_rules if r.field != field]
        self.save_config()
