"""配置校验功能."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from envsync.config import ConfigManager
from envsync.models import ConfigFile, ValidationResult, ValidationRule


class ConfigValidator:
    """配置校验器."""

    def __init__(self, config_manager: ConfigManager) -> None:
        """初始化校验器.

        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager

    def validate(
        self,
        data: Dict[str, Any],
        rules: Optional[List[ValidationRule]] = None,
    ) -> ValidationResult:
        """校验配置数据.

        Args:
            data: 配置数据
            rules: 校验规则列表，默认使用项目配置的规则

        Returns:
            校验结果
        """
        if rules is None:
            rules = self.config_manager.config.validation_rules

        errors: List[str] = []
        warnings: List[str] = []

        for rule in rules:
            result = self._validate_rule(data, rule)
            if not result.valid:
                if rule.required:
                    errors.extend(result.errors)
                else:
                    warnings.extend(result.errors)
            warnings.extend(result.warnings)

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def validate_config_file(
        self,
        config_file: ConfigFile,
        environment: Optional[str] = None,
    ) -> ValidationResult:
        """校验配置文件.

        Args:
            config_file: 配置文件对象
            environment: 环境名称，用于应用模板变量

        Returns:
            校验结果
        """
        if environment:
            from envsync.template import TemplateEngine

            template_engine = TemplateEngine(self.config_manager)
            data = template_engine.render_config(
                ConfigManager.load_config_file(config_file.path, config_file.format),
                self.config_manager.get_merged_variables(environment),
                strict=False,
            )
        else:
            data = ConfigManager.load_config_file(config_file.path, config_file.format)

        rules = self.config_manager.config.validation_rules

        if config_file.schema_path and config_file.schema_path.exists():
            schema_rules = self._load_schema_rules(config_file.schema_path)
            rules = rules + schema_rules

        return self.validate(data, rules)

    def validate_environment(self, environment: str) -> Dict[str, ValidationResult]:
        """校验环境的所有配置文件.

        Args:
            environment: 环境名称

        Returns:
            校验结果字典，键为文件名
        """
        results = {}

        files = self.config_manager.get_environment_files(environment)
        for config_file in files:
            results[config_file.name] = self.validate_config_file(config_file, environment)

        return results

    def _validate_rule(
        self,
        data: Dict[str, Any],
        rule: ValidationRule,
    ) -> ValidationResult:
        """校验单个规则.

        Args:
            data: 配置数据
            rule: 校验规则

        Returns:
            校验结果
        """
        errors: List[str] = []
        warnings: List[str] = []

        value = self._get_nested_value(data, rule.field)

        if value is None:
            if rule.required:
                msg = rule.custom_message or f"必填字段缺失: {rule.field}"
                errors.append(msg)
            return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

        if rule.type:
            type_valid = self._check_type(value, rule.type)
            if not type_valid:
                errors.append(f"字段 {rule.field} 类型错误，期望: {rule.type}")

        if rule.pattern and isinstance(value, str):
            if not re.match(rule.pattern, value):
                msg = rule.custom_message or f"字段 {rule.field} 格式不匹配: {rule.pattern}"
                errors.append(msg)

        if rule.min_value is not None:
            if isinstance(value, (int, float)) and value < rule.min_value:
                errors.append(f"字段 {rule.field} 值过小，最小值: {rule.min_value}")

        if rule.max_value is not None:
            if isinstance(value, (int, float)) and value > rule.max_value:
                errors.append(f"字段 {rule.field} 值过大，最大值: {rule.max_value}")

        if rule.allowed_values is not None:
            if value not in rule.allowed_values:
                allowed = ", ".join(str(v) for v in rule.allowed_values)
                errors.append(f"字段 {rule.field} 值不允许，可选值: {allowed}")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def _get_nested_value(
        self,
        data: Dict[str, Any],
        path: str,
    ) -> Any:
        """获取嵌套字典中的值.

        Args:
            data: 数据字典
            path: 字段路径（如 "database.host"）

        Returns:
            字段值，不存在则返回 None
        """
        keys = path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        return current

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """检查值类型.

        Args:
            value: 值
            expected_type: 期望类型

        Returns:
            类型是否匹配
        """
        type_map = {
            "string": str,
            "int": int,
            "integer": int,
            "float": float,
            "number": (int, float),
            "bool": bool,
            "boolean": bool,
            "list": list,
            "array": list,
            "dict": dict,
            "object": dict,
        }

        expected = type_map.get(expected_type.lower())
        if expected is None:
            return True

        return isinstance(value, expected)

    def _load_schema_rules(self, schema_path: Any) -> List[ValidationRule]:
        """从模式文件加载校验规则.

        Args:
            schema_path: 模式文件路径

        Returns:
            校验规则列表
        """
        import json

        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        rules = []
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        for field, prop in properties.items():
            rule = ValidationRule(
                field=field,
                required=field in required,
                type=prop.get("type"),
                pattern=prop.get("pattern"),
            )

            if "minimum" in prop:
                rule.min_value = prop["minimum"]
            if "maximum" in prop:
                rule.max_value = prop["maximum"]
            if "enum" in prop:
                rule.allowed_values = prop["enum"]

            rules.append(rule)

        return rules

    def add_builtin_rules(self) -> None:
        """添加内置校验规则."""
        builtin_rules = [
            ValidationRule(
                field="port",
                required=False,
                type="integer",
                min_value=1,
                max_value=65535,
            ),
            ValidationRule(
                field="host",
                required=False,
                type="string",
                pattern=r"^[\w\-\.]+$",
            ),
            ValidationRule(
                field="url",
                required=False,
                type="string",
                pattern=r"^https?://",
            ),
            ValidationRule(
                field="email",
                required=False,
                type="string",
                pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$",
            ),
        ]

        for rule in builtin_rules:
            self.config_manager.add_validation_rule(rule)

    def validate_syntax(
        self,
        config_file: ConfigFile,
    ) -> ValidationResult:
        """校验配置文件语法.

        Args:
            config_file: 配置文件对象

        Returns:
            校验结果
        """
        errors = []

        try:
            ConfigManager.load_config_file(config_file.path, config_file.format)
        except Exception as e:
            errors.append(f"语法错误: {e}")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=[])
