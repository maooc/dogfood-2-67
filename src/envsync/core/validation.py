"""Configuration validation for envsync."""

import re
from typing import Any, Dict, List, Optional, Union
from jsonschema import validate, ValidationError as JSONSchemaValidationError
from .config import Environment, Template, ConfigVariable


class ValidationResult:
    """Represents the result of a validation operation."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    @property
    def is_valid(self) -> bool:
        """Check if the validation passed (no errors)."""
        return len(self.errors) == 0

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)

    def merge(self, other: "ValidationResult") -> None:
        """Merge another validation result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

    def __str__(self) -> str:
        """Convert to string representation."""
        lines = []
        if self.errors:
            lines.append("Errors:")
            lines.extend(f"  - {e}" for e in self.errors)
        if self.warnings:
            lines.append("Warnings:")
            lines.extend(f"  - {w}" for w in self.warnings)
        if not lines:
            return "Valid"
        return "\n".join(lines)


class ConfigValidator:
    """Validates configuration against templates and rules."""

    # JSON Schema for environment configuration
    ENVIRONMENT_SCHEMA = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "variables": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "value": {"type": ["string", "number", "boolean"]},
                        "description": {"type": ["string", "null"]},
                        "encrypted": {"type": "boolean"},
                        "required": {"type": "boolean"},
                        "type": {"type": "string"},
                        "pattern": {"type": ["string", "null"]},
                    },
                    "required": ["name", "value"],
                },
            },
        },
        "required": ["name", "variables"],
    }

    # JSON Schema for templates
    TEMPLATE_SCHEMA = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "variables": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "description": {"type": ["string", "null"]},
                        "pattern": {"type": ["string", "null"]},
                        "default": {"type": ["string", "number", "boolean", "null"]},
                    },
                },
            },
            "required": {"type": "array", "items": {"type": "string"}},
            "sensitive": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["name", "variables", "required", "sensitive"],
    }

    def __init__(self, encryption_manager=None):
        """Initialize the validator."""
        self.encryption_manager = encryption_manager

    def validate_environment_schema(self, env_data: Dict[str, Any]) -> ValidationResult:
        """Validate environment data against JSON Schema."""
        result = ValidationResult()
        try:
            validate(instance=env_data, schema=self.ENVIRONMENT_SCHEMA)
        except JSONSchemaValidationError as e:
            result.add_error(f"Schema validation failed: {e.message}")
        return result

    def validate_template_schema(self, template_data: Dict[str, Any]) -> ValidationResult:
        """Validate template data against JSON Schema."""
        result = ValidationResult()
        try:
            validate(instance=template_data, schema=self.TEMPLATE_SCHEMA)
        except JSONSchemaValidationError as e:
            result.add_error(f"Schema validation failed: {e.message}")
        return result

    def validate_environment_against_template(
        self, environment: Environment, template: Template
    ) -> ValidationResult:
        """Validate an environment against a template."""
        result = ValidationResult()

        # Get all variable names
        env_vars = {v.name: v for v in environment.variables.values()}
        template_vars = template.variables
        required_vars = set(template.required)

        # Check required variables
        for var_name in required_vars:
            if var_name not in env_vars:
                result.add_error(f"Missing required variable: {var_name}")
            elif not env_vars[var_name].value:
                result.add_error(f"Required variable has empty value: {var_name}")

        # Validate variable types and patterns
        for var_name, var in env_vars.items():
            # Skip if variable not defined in template (warning instead of error)
            if var_name not in template_vars:
                result.add_warning(f"Variable not defined in template: {var_name}")
                continue

            var_schema = template_vars.get(var_name, {})
            expected_type = var_schema.get("type", "string")
            pattern = var_schema.get("pattern")

            # Get the actual value (decrypt if needed)
            value = var.value
            if self.encryption_manager and var.encrypted:
                value = self.encryption_manager.decrypt(value)

            # Validate type
            type_result = self._validate_type(value, expected_type)
            result.merge(type_result)

            # Validate pattern
            if pattern:
                pattern_result = self._validate_pattern(value, pattern, var_name)
                result.merge(pattern_result)

        return result

    def _validate_type(self, value: str, expected_type: str) -> ValidationResult:
        """Validate that a value matches the expected type."""
        result = ValidationResult()

        if expected_type == "string":
            # All values are stored as strings initially
            pass
        elif expected_type == "int":
            try:
                int(value)
            except ValueError:
                result.add_error(f"Value '{value}' is not a valid integer")
        elif expected_type == "float":
            try:
                float(value)
            except ValueError:
                result.add_error(f"Value '{value}' is not a valid float")
        elif expected_type == "bool":
            if value.lower() not in ("true", "false", "1", "0", "yes", "no"):
                result.add_error(f"Value '{value}' is not a valid boolean")
        elif expected_type == "url":
            if not self._is_valid_url(value):
                result.add_error(f"Value '{value}' is not a valid URL")
        elif expected_type == "email":
            if not self._is_valid_email(value):
                result.add_error(f"Value '{value}' is not a valid email address")

        return result

    def _validate_pattern(self, value: str, pattern: str, var_name: str) -> ValidationResult:
        """Validate that a value matches a regex pattern."""
        result = ValidationResult()
        try:
            if not re.match(pattern, value):
                result.add_error(
                    f"Value '{value}' for variable '{var_name}' does not match pattern: {pattern}"
                )
        except re.error as e:
            result.add_error(f"Invalid pattern '{pattern}' for variable '{var_name}': {e}")
        return result

    @staticmethod
    def _is_valid_url(value: str) -> bool:
        """Check if a value is a valid URL."""
        url_pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain
            r"localhost|"  # localhost
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # or ip
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )
        return bool(url_pattern.match(value))

    @staticmethod
    def _is_valid_email(value: str) -> bool:
        """Check if a value is a valid email address."""
        email_pattern = re.compile(
            r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        )
        return bool(email_pattern.match(value))

    def validate_custom_rules(
        self, environment: Environment, rules: List[Dict[str, Any]]
    ) -> ValidationResult:
        """Validate against custom validation rules.

        Rules format:
        [
            {
                "field": "variable_name",
                "rule": "min_length",
                "value": 5,
                "message": "Must be at least 5 characters"
            },
            ...
        ]
        """
        result = ValidationResult()
        env_vars = {v.name: v for v in environment.variables.values()}

        for rule in rules:
            field = rule.get("field")
            rule_type = rule.get("rule")
            expected_value = rule.get("value")
            message = rule.get("message")

            if field not in env_vars:
                result.add_error(f"Rule references unknown field: {field}")
                continue

            var = env_vars[field]
            actual_value = var.value

            # Decrypt if needed
            if self.encryption_manager and var.encrypted:
                actual_value = self.encryption_manager.decrypt(actual_value)

            # Apply rule
            rule_result = self._apply_rule(
                field, actual_value, rule_type, expected_value, message
            )
            result.merge(rule_result)

        return result

    def _apply_rule(
        self,
        field: str,
        value: str,
        rule_type: str,
        expected_value: Any,
        message: Optional[str] = None,
    ) -> ValidationResult:
        """Apply a single validation rule."""
        result = ValidationResult()

        if rule_type == "min_length":
            if len(value) < int(expected_value):
                msg = message or f"Field '{field}' must be at least {expected_value} characters"
                result.add_error(msg)

        elif rule_type == "max_length":
            if len(value) > int(expected_value):
                msg = message or f"Field '{field}' must be at most {expected_value} characters"
                result.add_error(msg)

        elif rule_type == "min":
            try:
                if float(value) < float(expected_value):
                    msg = message or f"Field '{field}' must be at least {expected_value}"
                    result.add_error(msg)
            except ValueError:
                result.add_error(f"Field '{field}' must be a number for min rule")

        elif rule_type == "max":
            try:
                if float(value) > float(expected_value):
                    msg = message or f"Field '{field}' must be at most {expected_value}"
                    result.add_error(msg)
            except ValueError:
                result.add_error(f"Field '{field}' must be a number for max rule")

        elif rule_type == "equals":
            if value != str(expected_value):
                msg = message or f"Field '{field}' must equal '{expected_value}'"
                result.add_error(msg)

        elif rule_type == "contains":
            if str(expected_value) not in value:
                msg = message or f"Field '{field}' must contain '{expected_value}'"
                result.add_error(msg)

        elif rule_type == "not_contains":
            if str(expected_value) in value:
                msg = message or f"Field '{field}' must not contain '{expected_value}'"
                result.add_error(msg)

        elif rule_type == "one_of":
            if isinstance(expected_value, list):
                if value not in expected_value:
                    msg = message or f"Field '{field}' must be one of: {expected_value}"
                    result.add_error(msg)
            else:
                result.add_error(f"Rule 'one_of' expects a list for field '{field}'")

        elif rule_type == "regex":
            try:
                if not re.match(str(expected_value), value):
                    msg = (
                        message
                        or f"Field '{field}' must match pattern: {expected_value}"
                    )
                    result.add_error(msg)
            except re.error as e:
                result.add_error(f"Invalid regex pattern for field '{field}': {e}")

        else:
            result.add_error(f"Unknown rule type: {rule_type}")

        return result
