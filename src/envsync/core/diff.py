"""Environment comparison and diff utilities."""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from .config import Environment


class ChangeType(Enum):
    """Type of change between two values."""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class VariableDiff:
    """Represents the difference for a single variable."""
    name: str
    change_type: ChangeType
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    old_encrypted: bool = False
    new_encrypted: bool = False


@dataclass
class EnvironmentDiff:
    """Represents the complete difference between two environments."""
    env1_name: str
    env2_name: str
    variables: List[VariableDiff]

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return any(v.change_type != ChangeType.UNCHANGED for v in self.variables)

    @property
    def added_count(self) -> int:
        """Count of added variables."""
        return sum(1 for v in self.variables if v.change_type == ChangeType.ADDED)

    @property
    def removed_count(self) -> int:
        """Count of removed variables."""
        return sum(1 for v in self.variables if v.change_type == ChangeType.REMOVED)

    @property
    def modified_count(self) -> int:
        """Count of modified variables."""
        return sum(1 for v in self.variables if v.change_type == ChangeType.MODIFIED)

    @property
    def unchanged_count(self) -> int:
        """Count of unchanged variables."""
        return sum(1 for v in self.variables if v.change_type == ChangeType.UNCHANGED)


class EnvironmentDiffer:
    """Compares two environments and finds differences."""

    def __init__(self, encryption_manager=None):
        """Initialize the differ.

        Args:
            encryption_manager: Optional encryption manager for decrypting values.
        """
        self.encryption_manager = encryption_manager

    def compare(
        self,
        env1: Environment,
        env2: Environment,
        decrypt: bool = False,
        show_unchanged: bool = False,
    ) -> EnvironmentDiff:
        """Compare two environments.

        Args:
            env1: First environment (old)
            env2: Second environment (new)
            decrypt: Whether to decrypt values for comparison
            show_unchanged: Whether to include unchanged variables

        Returns:
            EnvironmentDiff object containing the differences
        """
        variables: List[VariableDiff] = []

        # Get all variable names from both environments
        env1_vars = {v.name: v for v in env1.variables.values()}
        env2_vars = {v.name: v for v in env2.variables.values()}
        all_vars = set(env1_vars.keys()).union(set(env2_vars.keys()))

        for var_name in all_vars:
            var1 = env1_vars.get(var_name)
            var2 = env2_vars.get(var_name)

            # Get values (decrypt if needed)
            val1 = self._get_value(var1, decrypt) if var1 else None
            val2 = self._get_value(var2, decrypt) if var2 else None

            # Determine change type
            if var1 is None:
                change_type = ChangeType.ADDED
            elif var2 is None:
                change_type = ChangeType.REMOVED
            elif val1 != val2:
                change_type = ChangeType.MODIFIED
            else:
                change_type = ChangeType.UNCHANGED

            # Skip unchanged if not requested
            if change_type == ChangeType.UNCHANGED and not show_unchanged:
                continue

            variables.append(
                VariableDiff(
                    name=var_name,
                    change_type=change_type,
                    old_value=val1,
                    new_value=val2,
                    old_encrypted=var1.encrypted if var1 else False,
                    new_encrypted=var2.encrypted if var2 else False,
                )
            )

        # Sort variables by name
        variables.sort(key=lambda x: x.name)

        return EnvironmentDiff(
            env1_name=env1.name,
            env2_name=env2.name,
            variables=variables,
        )

    def _get_value(self, variable, decrypt: bool) -> str:
        """Get the variable value, decrypting if needed."""
        value = variable.value
        if decrypt and variable.encrypted and self.encryption_manager:
            value = self.encryption_manager.decrypt(value)
        return value

    def compare_to_template(
        self,
        environment: Environment,
        template,  # Template type
    ) -> Tuple[List[str], List[str], List[str]]:
        """Compare an environment to a template.

        Returns:
            Tuple of (missing_required, extra, missing_optional)
        """
        env_vars = {v.name for v in environment.variables.values()}
        template_vars = set(template.variables.keys())
        required_vars = set(template.required)

        missing_required = list(required_vars - env_vars)
        extra = list(env_vars - template_vars)
        missing_optional = list(template_vars - env_vars - required_vars)

        return (
            sorted(missing_required),
            sorted(extra),
            sorted(missing_optional),
        )


class UnifiedDiffGenerator:
    """Generates unified diff format output."""

    @staticmethod
    def generate(diff: EnvironmentDiff) -> str:
        """Generate a unified diff string from an EnvironmentDiff."""
        lines = []

        # Header
        lines.append(f"--- {diff.env1_name}")
        lines.append(f"+++ {diff.env2_name}")

        # Group variables by change type
        added = [v for v in diff.variables if v.change_type == ChangeType.ADDED]
        removed = [v for v in diff.variables if v.change_type == ChangeType.REMOVED]
        modified = [v for v in diff.variables if v.change_type == ChangeType.MODIFIED]

        # Generate hunks
        if removed:
            lines.append("@@ -1,{} +1,{} @@".format(len(removed), 0))
            for var in removed:
                old_val = UnifiedDiffGenerator._format_value(var.old_value, var.old_encrypted)
                lines.append(f"-{var.name}={old_val}")

        if added:
            lines.append("@@ -1,{} +1,{} @@".format(0, len(added)))
            for var in added:
                new_val = UnifiedDiffGenerator._format_value(var.new_value, var.new_encrypted)
                lines.append(f"+{var.name}={new_val}")

        if modified:
            lines.append("@@ -1,{} +1,{} @@".format(len(modified), len(modified)))
            for var in modified:
                old_val = UnifiedDiffGenerator._format_value(var.old_value, var.old_encrypted)
                new_val = UnifiedDiffGenerator._format_value(var.new_value, var.new_encrypted)
                lines.append(f"-{var.name}={old_val}")
                lines.append(f"+{var.name}={new_val}")

        return "\n".join(lines)

    @staticmethod
    def _format_value(value: Optional[str], encrypted: bool) -> str:
        """Format a value for diff output."""
        if value is None:
            return ""
        if encrypted:
            return "[ENCRYPTED]"
        # Escape newlines
        return value.replace("\n", "\\n").replace("\r", "\\r")


class DiffFormatter:
    """Formats diff results for display."""

    @staticmethod
    def format_summary(diff: EnvironmentDiff) -> str:
        """Format a summary of the differences."""
        parts = []
        if diff.added_count > 0:
            parts.append(f"{diff.added_count} added")
        if diff.removed_count > 0:
            parts.append(f"{diff.removed_count} removed")
        if diff.modified_count > 0:
            parts.append(f"{diff.modified_count} modified")
        if diff.unchanged_count > 0:
            parts.append(f"{diff.unchanged_count} unchanged")

        if not parts:
            return "No differences"
        return ", ".join(parts)

    @staticmethod
    def format_detailed(diff: EnvironmentDiff, use_colors: bool = True) -> str:
        """Format detailed differences.

        Args:
            diff: The EnvironmentDiff to format
            use_colors: Whether to use ANSI colors

        Returns:
            Formatted string representation
        """
        lines = []
        lines.append(f"Comparing {diff.env1_name} to {diff.env2_name}:")
        lines.append("")

        for var in diff.variables:
            if var.change_type == ChangeType.ADDED:
                prefix = "+" if use_colors else "ADDED"
                color_start = "\033[32m" if use_colors else ""
                color_end = "\033[0m" if use_colors else ""
                val = var.new_value or ""
                if var.new_encrypted:
                    val = "[ENCRYPTED]"
                lines.append(f"{color_start}{prefix} {var.name}={val}{color_end}")

            elif var.change_type == ChangeType.REMOVED:
                prefix = "-" if use_colors else "REMOVED"
                color_start = "\033[31m" if use_colors else ""
                color_end = "\033[0m" if use_colors else ""
                val = var.old_value or ""
                if var.old_encrypted:
                    val = "[ENCRYPTED]"
                lines.append(f"{color_start}{prefix} {var.name}={val}{color_end}")

            elif var.change_type == ChangeType.MODIFIED:
                prefix = "~" if use_colors else "MODIFIED"
                color_start = "\033[33m" if use_colors else ""
                color_end = "\033[0m" if use_colors else ""
                old_val = var.old_value or ""
                new_val = var.new_value or ""
                if var.old_encrypted:
                    old_val = "[ENCRYPTED]"
                if var.new_encrypted:
                    new_val = "[ENCRYPTED]"
                lines.append(f"{color_start}{prefix} {var.name}: {old_val} -> {new_val}{color_end}")

            elif var.change_type == ChangeType.UNCHANGED:
                prefix = " " if use_colors else "UNCHANGED"
                val = var.old_value or ""
                if var.old_encrypted:
                    val = "[ENCRYPTED]"
                lines.append(f"{prefix} {var.name}={val}")

        return "\n".join(lines)
