"""模板变量替换功能."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from envsync.models import ConfigFile, ConfigFormat
from envsync.config import ConfigManager


class TemplateEngine:
    """模板引擎."""

    VARIABLE_PATTERN = re.compile(r"\$\{(\w+)(?::([^}]+))?\}")
    ENV_PATTERN = re.compile(r"\$\{ENV:(\w+)\}")

    def __init__(self, config_manager: ConfigManager) -> None:
        """初始化模板引擎.

        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager

    def render(
        self,
        template_content: str,
        variables: Dict[str, str],
        strict: bool = False,
    ) -> str:
        """渲染模板内容.

        Args:
            template_content: 模板内容
            variables: 变量字典
            strict: 是否严格模式（缺少变量时报错）

        Returns:
            渲染后的内容

        Raises:
            ValueError: 严格模式下缺少变量
        """
        def replace_var(match: re.Match) -> str:
            var_name = match.group(1)
            default_value = match.group(2)

            if var_name in variables:
                return variables[var_name]
            elif default_value is not None:
                return default_value
            elif strict:
                raise ValueError(f"缺少变量: {var_name}")
            else:
                return match.group(0)

        result = self.VARIABLE_PATTERN.sub(replace_var, template_content)

        def replace_env(match: re.Match) -> str:
            env_var = match.group(1)
            import os
            return os.environ.get(env_var, match.group(0))

        result = self.ENV_PATTERN.sub(replace_env, result)

        return result

    def render_config(
        self,
        data: Dict[str, Any],
        variables: Dict[str, str],
        strict: bool = False,
    ) -> Dict[str, Any]:
        """递归渲染配置数据中的模板变量.

        Args:
            data: 配置数据
            variables: 变量字典
            strict: 是否严格模式

        Returns:
            渲染后的配置数据
        """
        def render_value(value: Any) -> Any:
            if isinstance(value, str):
                return self.render(value, variables, strict)
            elif isinstance(value, dict):
                return {k: render_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [render_value(item) for item in value]
            else:
                return value

        return render_value(data)

    def process_config_file(
        self,
        config_file: ConfigFile,
        environment: str,
        output_path: Optional[Path] = None,
        strict: bool = False,
    ) -> Path:
        """处理配置文件（应用模板变量）.

        Args:
            config_file: 配置文件对象
            environment: 环境名称
            output_path: 输出路径，默认为配置文件路径
            strict: 是否严格模式

        Returns:
            生成的文件路径
        """
        variables = self.config_manager.get_merged_variables(environment)

        if config_file.template and config_file.template.exists():
            with open(config_file.template, "r", encoding="utf-8") as f:
                template_content = f.read()
            rendered_content = self.render(template_content, variables, strict)

            target_path = output_path or config_file.path
            target_path.parent.mkdir(parents=True, exist_ok=True)

            with open(target_path, "w", encoding="utf-8") as f:
                f.write(rendered_content)

            return target_path
        else:
            data = ConfigManager.load_config_file(config_file.path, config_file.format)
            rendered_data = self.render_config(data, variables, strict)

            target_path = output_path or config_file.path
            ConfigManager.save_config_file(target_path, config_file.format, rendered_data)

            return target_path

    def preview(
        self,
        config_file: ConfigFile,
        environment: str,
    ) -> str:
        """预览配置文件渲染结果.

        Args:
            config_file: 配置文件对象
            environment: 环境名称

        Returns:
            渲染后的内容预览
        """
        variables = self.config_manager.get_merged_variables(environment)

        if config_file.template and config_file.template.exists():
            with open(config_file.template, "r", encoding="utf-8") as f:
                template_content = f.read()
            return self.render(template_content, variables, strict=False)
        else:
            data = ConfigManager.load_config_file(config_file.path, config_file.format)
            rendered_data = self.render_config(data, variables, strict=False)

            import json
            return json.dumps(rendered_data, indent=2, ensure_ascii=False)

    def extract_variables(self, content: str) -> List[Dict[str, Optional[str]]]:
        """从模板内容中提取变量.

        Args:
            content: 模板内容

        Returns:
            变量列表，包含名称和默认值
        """
        variables = []
        seen = set()

        for match in self.VARIABLE_PATTERN.finditer(content):
            var_name = match.group(1)
            default_value = match.group(2)

            if var_name not in seen:
                variables.append({
                    "name": var_name,
                    "default": default_value,
                })
                seen.add(var_name)

        return variables

    def validate_template(
        self,
        template_content: str,
        variables: Dict[str, str],
    ) -> List[str]:
        """验证模板变量是否都已定义.

        Args:
            template_content: 模板内容
            variables: 可用变量

        Returns:
            缺少的变量列表
        """
        missing = []

        for match in self.VARIABLE_PATTERN.finditer(template_content):
            var_name = match.group(1)
            default_value = match.group(2)

            if var_name not in variables and default_value is None:
                missing.append(var_name)

        return missing

    def create_template_from_config(
        self,
        config_path: Path,
        format: ConfigFormat,
        output_path: Path,
        variable_mapping: Optional[Dict[str, str]] = None,
    ) -> Path:
        """从现有配置文件创建模板.

        Args:
            config_path: 配置文件路径
            format: 配置文件格式
            output_path: 输出模板路径
            variable_mapping: 字段到变量名的映射

        Returns:
            模板文件路径
        """
        data = ConfigManager.load_config_file(config_path, format)
        mapping = variable_mapping or {}

        def convert_to_template(value: Any, path: str = "") -> Any:
            if isinstance(value, str):
                var_name = mapping.get(path)
                if var_name:
                    return f"${{{var_name}}}"
                return value
            elif isinstance(value, dict):
                return {
                    k: convert_to_template(v, f"{path}.{k}" if path else k)
                    for k, v in value.items()
                }
            elif isinstance(value, list):
                return [convert_to_template(item, f"{path}[]") for item in value]
            else:
                return value

        template_data = convert_to_template(data)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        ConfigManager.save_config_file(output_path, format, template_data)

        return output_path
