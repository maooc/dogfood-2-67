"""配置导出功能."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import toml
import yaml

from envsync.config import ConfigManager
from envsync.models import ConfigFile, ConfigFormat


class ConfigExporter:
    """配置导出器."""

    def __init__(self, config_manager: ConfigManager) -> None:
        """初始化导出器.

        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager

    def export_environment(
        self,
        environment: str,
        output_dir: Path,
        include_templates: bool = False,
        decrypt: bool = False,
    ) -> Path:
        """导出整个环境的配置.

        Args:
            environment: 环境名称
            output_dir: 输出目录
            include_templates: 是否包含模板文件
            decrypt: 是否解密敏感字段

        Returns:
            输出目录路径
        """
        output_dir = output_dir / environment
        output_dir.mkdir(parents=True, exist_ok=True)

        env = self.config_manager.get_environment(environment)
        if not env:
            raise ValueError(f"环境不存在: {environment}")

        variables_file = output_dir / "variables.yaml"
        variables_data = {
            name: {
                "value": var.value,
                "description": var.description,
                "is_sensitive": var.is_sensitive,
            }
            for name, var in env.variables.items()
        }
        with open(variables_file, "w", encoding="utf-8") as f:
            yaml.dump(variables_data, f, allow_unicode=True)

        config_files = self.config_manager.get_environment_files(environment)
        for cf in config_files:
            if cf.path.exists():
                data = ConfigManager.load_config_file(cf.path, cf.format)

                if decrypt and cf.encrypted_fields:
                    from envsync.crypto import CryptoManager

                    crypto = CryptoManager(self.config_manager)
                    data = crypto.decrypt_config(data)

                target_path = output_dir / f"{cf.name}.{cf.format.value}"
                ConfigManager.save_config_file(target_path, cf.format, data)

                if include_templates and cf.template and cf.template.exists():
                    template_target = output_dir / "templates" / cf.template.name
                    template_target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(cf.template, template_target)

        return output_dir

    def export_to_format(
        self,
        environment: str,
        output_path: Path,
        format: ConfigFormat,
        decrypt: bool = False,
    ) -> Path:
        """导出环境配置为指定格式.

        Args:
            environment: 环境名称
            output_path: 输出路径
            format: 输出格式
            decrypt: 是否解密敏感字段

        Returns:
            输出文件路径
        """
        env = self.config_manager.get_environment(environment)
        if not env:
            raise ValueError(f"环境不存在: {environment}")

        data: Dict[str, Any] = {
            "environment": environment,
            "variables": {},
            "configs": {},
        }

        for name, var in env.variables.items():
            data["variables"][name] = {
                "value": var.value,
                "description": var.description,
                "is_sensitive": var.is_sensitive,
            }

        config_files = self.config_manager.get_environment_files(environment)
        for cf in config_files:
            if cf.path.exists():
                config_data = ConfigManager.load_config_file(cf.path, cf.format)

                if decrypt and cf.encrypted_fields:
                    from envsync.crypto import CryptoManager

                    crypto = CryptoManager(self.config_manager)
                    config_data = crypto.decrypt_config(config_data)

                data["configs"][cf.name] = config_data

        if format == ConfigFormat.JSON:
            if not output_path.suffix == ".json":
                output_path = output_path.with_suffix(".json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        elif format == ConfigFormat.YAML:
            if not output_path.suffix in (".yaml", ".yml"):
                output_path = output_path.with_suffix(".yaml")
            with open(output_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True)

        elif format == ConfigFormat.ENV:
            if not output_path.suffix == ".env":
                output_path = output_path.with_suffix(".env")
            with open(output_path, "w", encoding="utf-8") as f:
                for name, var in env.variables.items():
                    value = var.value
                    if var.is_sensitive and not decrypt:
                        value = "***"
                    f.write(f"{name}={value}\n")

        elif format == ConfigFormat.TOML:
            if not output_path.suffix == ".toml":
                output_path = output_path.with_suffix(".toml")
            with open(output_path, "w", encoding="utf-8") as f:
                toml.dump(data, f)

        else:
            raise ValueError(f"不支持的导出格式: {format}")

        return output_path

    def export_csv(
        self,
        environments: List[str],
        output_path: Path,
        include_sensitive: bool = False,
    ) -> Path:
        """导出变量为 CSV 格式.

        Args:
            environments: 环境名称列表
            output_path: 输出路径
            include_sensitive: 是否包含敏感变量

        Returns:
            输出文件路径
        """
        if not output_path.suffix == ".csv":
            output_path = output_path.with_suffix(".csv")

        all_vars: Dict[str, Dict[str, str]] = {}

        for env_name in environments:
            env = self.config_manager.get_environment(env_name)
            if not env:
                continue

            for var_name, var in env.variables.items():
                if var.is_sensitive and not include_sensitive:
                    continue

                if var_name not in all_vars:
                    all_vars[var_name] = {}
                all_vars[var_name][env_name] = var.value

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            header = ["Variable"] + environments
            writer.writerow(header)

            for var_name in sorted(all_vars.keys()):
                row = [var_name]
                for env_name in environments:
                    row.append(all_vars[var_name].get(env_name, ""))
                writer.writerow(row)

        return output_path

    def export_table(
        self,
        environments: List[str],
        include_sensitive: bool = False,
    ) -> str:
        """导出为表格格式字符串.

        Args:
            environments: 环境名称列表
            include_sensitive: 是否包含敏感变量

        Returns:
            表格字符串
        """
        from rich.table import Table
        from rich.console import Console
        from io import StringIO

        table = Table(title="环境变量对比")
        table.add_column("Variable", style="cyan")

        for env_name in environments:
            table.add_column(env_name, style="green")

        all_vars: Dict[str, Dict[str, str]] = {}

        for env_name in environments:
            env = self.config_manager.get_environment(env_name)
            if not env:
                continue

            for var_name, var in env.variables.items():
                if var.is_sensitive and not include_sensitive:
                    continue

                if var_name not in all_vars:
                    all_vars[var_name] = {}
                all_vars[var_name][env_name] = var.value

        for var_name in sorted(all_vars.keys()):
            row = [var_name]
            for env_name in environments:
                value = all_vars[var_name].get(env_name, "")
                row.append(value)
            table.add_row(*row)

        console = Console(file=StringIO(), force_terminal=False)
        console.print(table)
        return console.file.getvalue() or ""

    def export_docker_env(
        self,
        environment: str,
        output_path: Path,
        service_prefix: Optional[str] = None,
    ) -> Path:
        """导出为 Docker 环境文件格式.

        Args:
            environment: 环境名称
            output_path: 输出路径
            service_prefix: 服务名称前缀

        Returns:
            输出文件路径
        """
        if not output_path.suffix == ".env":
            output_path = output_path.with_suffix(".env")

        env = self.config_manager.get_environment(environment)
        if not env:
            raise ValueError(f"环境不存在: {environment}")

        prefix = f"{service_prefix}_" if service_prefix else ""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# Environment: {environment}\n\n")

            for name, var in env.variables.items():
                env_name = f"{prefix}{name.upper()}"
                f.write(f"# {var.description or ''}\n")
                f.write(f"{env_name}={var.value}\n\n")

        return output_path

    def export_kubernetes_secret(
        self,
        environment: str,
        output_path: Path,
        secret_name: Optional[str] = None,
        namespace: str = "default",
    ) -> Path:
        """导出为 Kubernetes Secret YAML.

        Args:
            environment: 环境名称
            output_path: 输出路径
            secret_name: Secret 名称，默认为环境名
            namespace: 命名空间

        Returns:
            输出文件路径
        """
        if not output_path.suffix in (".yaml", ".yml"):
            output_path = output_path.with_suffix(".yaml")

        env = self.config_manager.get_environment(environment)
        if not env:
            raise ValueError(f"环境不存在: {environment}")

        import base64

        secret_data: Dict[str, str] = {}
        for name, var in env.variables.items():
            encoded = base64.b64encode(var.value.encode()).decode()
            secret_data[name] = encoded

        secret = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": secret_name or environment,
                "namespace": namespace,
            },
            "type": "Opaque",
            "data": secret_data,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(secret, f, allow_unicode=True)

        return output_path

    def export_terraform_vars(
        self,
        environment: str,
        output_path: Path,
    ) -> Path:
        """导出为 Terraform 变量文件.

        Args:
            environment: 环境名称
            output_path: 输出路径

        Returns:
            输出文件路径
        """
        if not output_path.suffix == ".tfvars":
            output_path = output_path.with_suffix(".tfvars")

        env = self.config_manager.get_environment(environment)
        if not env:
            raise ValueError(f"环境不存在: {environment}")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# Environment: {environment}\n\n")

            for name, var in env.variables.items():
                f.write(f"# {var.description or ''}\n")

                if isinstance(var.value, str):
                    escaped = var.value.replace('"', '\\"')
                    f.write(f'{name} = "{escaped}"\n')
                else:
                    f.write(f"{name} = {var.value}\n")
                f.write("\n")

        return output_path
