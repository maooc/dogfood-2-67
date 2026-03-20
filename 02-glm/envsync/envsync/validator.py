"""Configuration validation module."""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

import jsonschema
from jsonschema import ValidationError as JsonSchemaValidationError
from pydantic import BaseModel, Field, ValidationError as PydanticValidationError


class ValidationSeverity(Enum):
    """Severity level of validation issues."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Single validation issue."""
    path: str
    message: str
    severity: ValidationSeverity
    validator: str
    value: Optional[Any] = None
    expected: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "path": self.path,
            "message": self.message,
            "severity": self.severity.value,
            "validator": self.validator,
            "value": self.value,
            "expected": self.expected,
        }


@dataclass
class ValidationResult:
    """Result of configuration validation."""
    valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    
    @property
    def errors(self) -> List[ValidationIssue]:
        """Get all error-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]
    
    @property
    def warnings(self) -> List[ValidationIssue]:
        """Get all warning-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]
    
    @property
    def info(self) -> List[ValidationIssue]:
        """Get all info-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.INFO]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "valid": self.valid,
            "summary": {
                "total": len(self.issues),
                "errors": len(self.errors),
                "warnings": len(self.warnings),
                "info": len(self.info),
            },
            "issues": [i.to_dict() for i in self.issues],
        }


class BaseValidator:
    """Base class for validators."""
    
    name: str = "base"
    
    def validate(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate configuration data."""
        raise NotImplementedError


class JsonSchemaValidator(BaseValidator):
    """Validate configuration against JSON Schema."""
    
    name = "json_schema"
    
    def __init__(self, schema: Dict[str, Any]):
        self.schema = schema
    
    @classmethod
    def from_file(cls, schema_path: Path) -> "JsonSchemaValidator":
        """Create validator from schema file."""
        import json
        import yaml
        
        content = schema_path.read_text(encoding="utf-8")
        
        if schema_path.suffix == ".json":
            schema = json.loads(content)
        else:
            schema = yaml.safe_load(content)
        
        return cls(schema)
    
    def validate(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate data against JSON schema."""
        issues = []
        
        try:
            jsonschema.validate(data, self.schema)
        except JsonSchemaValidationError as e:
            path = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
            issues.append(ValidationIssue(
                path=path,
                message=e.message,
                severity=ValidationSeverity.ERROR,
                validator=self.name,
                value=e.instance if len(str(e.instance)) < 100 else "<truncated>",
            ))
        
        return issues


class RequiredFieldsValidator(BaseValidator):
    """Validate that required fields are present."""
    
    name = "required_fields"
    
    def __init__(self, required_fields: List[str]):
        self.required_fields = required_fields
    
    def validate(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate required fields are present."""
        issues = []
        
        for field_path in self.required_fields:
            value = self._get_nested_value(data, field_path)
            if value is None:
                issues.append(ValidationIssue(
                    path=field_path,
                    message=f"Required field '{field_path}' is missing",
                    severity=ValidationSeverity.ERROR,
                    validator=self.name,
                    expected="present",
                ))
        
        return issues
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value by dot-separated path."""
        keys = path.split(".")
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


class TypeValidator(BaseValidator):
    """Validate field types."""
    
    name = "type"
    
    TYPE_MAP = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }
    
    def __init__(self, type_rules: Dict[str, str]):
        self.type_rules = type_rules
    
    def validate(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate field types."""
        issues = []
        
        for field_path, expected_type in self.type_rules.items():
            value = self._get_nested_value(data, field_path)
            
            if value is not None:
                python_type = self.TYPE_MAP.get(expected_type)
                if python_type and not isinstance(value, python_type):
                    issues.append(ValidationIssue(
                        path=field_path,
                        message=f"Field '{field_path}' has wrong type",
                        severity=ValidationSeverity.ERROR,
                        validator=self.name,
                        value=type(value).__name__,
                        expected=expected_type,
                    ))
        
        return issues
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value by dot-separated path."""
        keys = path.split(".")
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


class PatternValidator(BaseValidator):
    """Validate fields against regex patterns."""
    
    name = "pattern"
    
    def __init__(self, pattern_rules: Dict[str, str]):
        self.pattern_rules = {
            path: re.compile(pattern)
            for path, pattern in pattern_rules.items()
        }
    
    def validate(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate fields against patterns."""
        issues = []
        
        for field_path, pattern in self.pattern_rules.items():
            value = self._get_nested_value(data, field_path)
            
            if value is not None and isinstance(value, str):
                if not pattern.match(value):
                    issues.append(ValidationIssue(
                        path=field_path,
                        message=f"Field '{field_path}' does not match pattern",
                        severity=ValidationSeverity.ERROR,
                        validator=self.name,
                        value=value,
                        expected=pattern.pattern,
                    ))
        
        return issues
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value by dot-separated path."""
        keys = path.split(".")
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


class RangeValidator(BaseValidator):
    """Validate numeric field ranges."""
    
    name = "range"
    
    def __init__(
        self,
        range_rules: Dict[str, Dict[str, Union[int, float]]]
    ):
        self.range_rules = range_rules
    
    def validate(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate numeric ranges."""
        issues = []
        
        for field_path, constraints in self.range_rules.items():
            value = self._get_nested_value(data, field_path)
            
            if value is not None and isinstance(value, (int, float)):
                min_val = constraints.get("min")
                max_val = constraints.get("max")
                
                if min_val is not None and value < min_val:
                    issues.append(ValidationIssue(
                        path=field_path,
                        message=f"Field '{field_path}' is below minimum",
                        severity=ValidationSeverity.ERROR,
                        validator=self.name,
                        value=value,
                        expected=f">= {min_val}",
                    ))
                
                if max_val is not None and value > max_val:
                    issues.append(ValidationIssue(
                        path=field_path,
                        message=f"Field '{field_path}' exceeds maximum",
                        severity=ValidationSeverity.ERROR,
                        validator=self.name,
                        value=value,
                        expected=f"<= {max_val}",
                    ))
        
        return issues
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value by dot-separated path."""
        keys = path.split(".")
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


class EnumValidator(BaseValidator):
    """Validate fields against allowed values."""
    
    name = "enum"
    
    def __init__(self, enum_rules: Dict[str, List[Any]]):
        self.enum_rules = enum_rules
    
    def validate(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Validate fields against enum values."""
        issues = []
        
        for field_path, allowed_values in self.enum_rules.items():
            value = self._get_nested_value(data, field_path)
            
            if value is not None and value not in allowed_values:
                issues.append(ValidationIssue(
                    path=field_path,
                    message=f"Field '{field_path}' has invalid value",
                    severity=ValidationSeverity.ERROR,
                    validator=self.name,
                    value=value,
                    expected=f"one of {allowed_values}",
                ))
        
        return issues
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value by dot-separated path."""
        keys = path.split(".")
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


class CustomValidator(BaseValidator):
    """Custom validation using callable functions."""
    
    name = "custom"
    
    def __init__(
        self,
        validators: Dict[str, Callable[[Any], bool]],
        messages: Optional[Dict[str, str]] = None
    ):
        self.validators = validators
        self.messages = messages or {}
    
    def validate(self, data: Dict[str, Any]) -> List[ValidationIssue]:
        """Run custom validators."""
        issues = []
        
        for field_path, validator_func in self.validators.items():
            value = self._get_nested_value(data, field_path)
            
            if value is not None:
                try:
                    if not validator_func(value):
                        message = self.messages.get(
                            field_path,
                            f"Field '{field_path}' failed validation"
                        )
                        issues.append(ValidationIssue(
                            path=field_path,
                            message=message,
                            severity=ValidationSeverity.ERROR,
                            validator=self.name,
                            value=value,
                        ))
                except Exception as e:
                    issues.append(ValidationIssue(
                        path=field_path,
                        message=f"Validation error: {str(e)}",
                        severity=ValidationSeverity.ERROR,
                        validator=self.name,
                        value=value,
                    ))
        
        return issues
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value by dot-separated path."""
        keys = path.split(".")
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current


class ConfigValidator:
    """Main configuration validator combining multiple validators."""
    
    def __init__(self):
        self.validators: List[BaseValidator] = []
    
    def add_validator(self, validator: BaseValidator) -> None:
        """Add a validator."""
        self.validators.append(validator)
    
    def add_json_schema(self, schema: Dict[str, Any]) -> None:
        """Add JSON Schema validation."""
        self.validators.append(JsonSchemaValidator(schema))
    
    def add_json_schema_file(self, schema_path: Path) -> None:
        """Add JSON Schema validation from file."""
        self.validators.append(JsonSchemaValidator.from_file(schema_path))
    
    def add_required_fields(self, fields: List[str]) -> None:
        """Add required fields validation."""
        self.validators.append(RequiredFieldsValidator(fields))
    
    def add_type_rules(self, rules: Dict[str, str]) -> None:
        """Add type validation rules."""
        self.validators.append(TypeValidator(rules))
    
    def add_pattern_rules(self, rules: Dict[str, str]) -> None:
        """Add pattern validation rules."""
        self.validators.append(PatternValidator(rules))
    
    def add_range_rules(self, rules: Dict[str, Dict[str, Union[int, float]]]) -> None:
        """Add range validation rules."""
        self.validators.append(RangeValidator(rules))
    
    def add_enum_rules(self, rules: Dict[str, List[Any]]) -> None:
        """Add enum validation rules."""
        self.validators.append(EnumValidator(rules))
    
    def add_custom_validator(
        self,
        field_path: str,
        validator_func: Callable[[Any], bool],
        message: Optional[str] = None
    ) -> None:
        """Add a custom validator for a field."""
        validators = {field_path: validator_func}
        messages = {field_path: message} if message else None
        self.validators.append(CustomValidator(validators, messages))
    
    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Run all validators and return combined result."""
        all_issues: List[ValidationIssue] = []
        
        for validator in self.validators:
            issues = validator.validate(data)
            all_issues.extend(issues)
        
        valid = not any(i.severity == ValidationSeverity.ERROR for i in all_issues)
        
        return ValidationResult(valid=valid, issues=all_issues)
    
    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate a configuration file."""
        from .config import ConfigLoader
        
        data = ConfigLoader.load(file_path)
        return self.validate(data)


class ValidationRuleSet(BaseModel):
    """A set of validation rules that can be saved/loaded."""
    name: str
    description: Optional[str] = None
    json_schema: Optional[Dict[str, Any]] = None
    required_fields: List[str] = Field(default_factory=list)
    type_rules: Dict[str, str] = Field(default_factory=dict)
    pattern_rules: Dict[str, str] = Field(default_factory=dict)
    range_rules: Dict[str, Dict[str, Union[int, float]]] = Field(default_factory=dict)
    enum_rules: Dict[str, List[Any]] = Field(default_factory=dict)
    
    def create_validator(self) -> ConfigValidator:
        """Create a validator from this rule set."""
        validator = ConfigValidator()
        
        if self.json_schema:
            validator.add_json_schema(self.json_schema)
        
        if self.required_fields:
            validator.add_required_fields(self.required_fields)
        
        if self.type_rules:
            validator.add_type_rules(self.type_rules)
        
        if self.pattern_rules:
            validator.add_pattern_rules(self.pattern_rules)
        
        if self.range_rules:
            validator.add_range_rules(self.range_rules)
        
        if self.enum_rules:
            validator.add_enum_rules(self.enum_rules)
        
        return validator
    
    def save(self, path: Path) -> None:
        """Save rule set to file."""
        import json
        path.write_text(json.dumps(self.model_dump(), indent=2), encoding="utf-8")
    
    @classmethod
    def load(cls, path: Path) -> "ValidationRuleSet":
        """Load rule set from file."""
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)
