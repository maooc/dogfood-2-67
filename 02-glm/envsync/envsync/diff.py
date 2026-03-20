"""Environment difference comparison module."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from deepdiff import DeepDiff


class DiffType(Enum):
    """Type of difference between configurations."""
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    TYPE_CHANGED = "type_changed"


@dataclass
class DiffItem:
    """Single difference item between configurations."""
    path: str
    diff_type: DiffType
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    old_type: Optional[str] = None
    new_type: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "path": self.path,
            "type": self.diff_type.value,
        }
        
        if self.diff_type == DiffType.CHANGED:
            result["old_value"] = self.old_value
            result["new_value"] = self.new_value
        elif self.diff_type == DiffType.ADDED:
            result["new_value"] = self.new_value
        elif self.diff_type == DiffType.REMOVED:
            result["old_value"] = self.old_value
        elif self.diff_type == DiffType.TYPE_CHANGED:
            result["old_type"] = self.old_type
            result["new_type"] = self.new_type
            result["old_value"] = self.old_value
            result["new_value"] = self.new_value
        
        return result


@dataclass
class DiffResult:
    """Result of comparing two configurations."""
    source_env: str
    target_env: str
    items: List[DiffItem] = field(default_factory=list)
    
    @property
    def added(self) -> List[DiffItem]:
        """Get all added items."""
        return [item for item in self.items if item.diff_type == DiffType.ADDED]
    
    @property
    def removed(self) -> List[DiffItem]:
        """Get all removed items."""
        return [item for item in self.items if item.diff_type == DiffType.REMOVED]
    
    @property
    def changed(self) -> List[DiffItem]:
        """Get all changed items."""
        return [item for item in self.items if item.diff_type == DiffType.CHANGED]
    
    @property
    def type_changed(self) -> List[DiffItem]:
        """Get all type-changed items."""
        return [item for item in self.items if item.diff_type == DiffType.TYPE_CHANGED]
    
    @property
    def has_differences(self) -> bool:
        """Check if there are any differences."""
        return len(self.items) > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "source_env": self.source_env,
            "target_env": self.target_env,
            "summary": {
                "total": len(self.items),
                "added": len(self.added),
                "removed": len(self.removed),
                "changed": len(self.changed),
                "type_changed": len(self.type_changed),
            },
            "items": [item.to_dict() for item in self.items],
        }


class ConfigDiffer:
    """Compare configurations between environments."""
    
    def __init__(
        self,
        ignore_fields: Optional[List[str]] = None,
        ignore_patterns: Optional[List[str]] = None,
        show_encrypted: bool = False
    ):
        self.ignore_fields = set(ignore_fields or [])
        self.ignore_patterns = ignore_patterns or []
        self.show_encrypted = show_encrypted
    
    def _should_ignore(self, path: str) -> bool:
        """Check if a path should be ignored."""
        import fnmatch
        
        if path in self.ignore_fields:
            return True
        
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        
        return False
    
    def _normalize_path(self, path: str) -> str:
        """Normalize DeepDiff path to dot notation."""
        path = path.replace("root", "")
        path = path.replace("['", ".")
        path = path.replace("']", "")
        path = path.replace("[", ".")
        path = path.replace("]", "")
        return path.strip(".")
    
    def compare(
        self,
        source: Dict[str, Any],
        target: Dict[str, Any],
        source_name: str = "source",
        target_name: str = "target"
    ) -> DiffResult:
        """Compare two configurations and return differences."""
        result = DiffResult(source_env=source_name, target_env=target_name)
        
        diff = DeepDiff(
            source,
            target,
            ignore_order=True,
            report_repetition=False,
        )
        
        if "dictionary_item_added" in diff:
            for path in diff["dictionary_item_added"]:
                normalized_path = self._normalize_path(str(path))
                if not self._should_ignore(normalized_path):
                    try:
                        new_value = self._get_value_by_path(target, normalized_path)
                    except (KeyError, TypeError):
                        new_value = "<unable to retrieve>"
                    
                    result.items.append(DiffItem(
                        path=normalized_path,
                        diff_type=DiffType.ADDED,
                        new_value=new_value,
                    ))
        
        if "dictionary_item_removed" in diff:
            for path in diff["dictionary_item_removed"]:
                normalized_path = self._normalize_path(str(path))
                if not self._should_ignore(normalized_path):
                    try:
                        old_value = self._get_value_by_path(source, normalized_path)
                    except (KeyError, TypeError):
                        old_value = "<unable to retrieve>"
                    
                    result.items.append(DiffItem(
                        path=normalized_path,
                        diff_type=DiffType.REMOVED,
                        old_value=old_value,
                    ))
        
        if "values_changed" in diff:
            for path, change in diff["values_changed"].items():
                normalized_path = self._normalize_path(str(path))
                if not self._should_ignore(normalized_path):
                    result.items.append(DiffItem(
                        path=normalized_path,
                        diff_type=DiffType.CHANGED,
                        old_value=change.get("old_value"),
                        new_value=change.get("new_value"),
                    ))
        
        if "type_changes" in diff:
            for path, change in diff["type_changes"].items():
                normalized_path = self._normalize_path(str(path))
                if not self._should_ignore(normalized_path):
                    result.items.append(DiffItem(
                        path=normalized_path,
                        diff_type=DiffType.TYPE_CHANGED,
                        old_type=type(change.get("old_value")).__name__,
                        new_type=type(change.get("new_value")).__name__,
                        old_value=change.get("old_value"),
                        new_value=change.get("new_value"),
                    ))
        
        result.items.sort(key=lambda x: x.path)
        
        return result
    
    def _get_value_by_path(self, data: Dict[str, Any], path: str) -> Any:
        """Get a value from nested dict by dot-separated path."""
        keys = path.split(".")
        current = data
        
        for key in keys:
            if isinstance(current, dict):
                current = current[key]
            elif isinstance(current, list):
                current = current[int(key)]
            else:
                raise KeyError(f"Cannot access key '{key}' on non-dict/list value")
        
        return current
    
    def find_missing_keys(
        self,
        source: Dict[str, Any],
        target: Dict[str, Any]
    ) -> Tuple[Set[str], Set[str]]:
        """Find keys missing between two configurations."""
        source_keys = self._get_all_keys(source)
        target_keys = self._get_all_keys(target)
        
        missing_in_target = source_keys - target_keys
        missing_in_source = target_keys - source_keys
        
        return missing_in_target, missing_in_source
    
    def _get_all_keys(
        self,
        data: Dict[str, Any],
        prefix: str = ""
    ) -> Set[str]:
        """Get all keys from nested dict as dot-separated paths."""
        keys = set()
        
        for key, value in data.items():
            current_path = f"{prefix}.{key}" if prefix else key
            keys.add(current_path)
            
            if isinstance(value, dict):
                keys.update(self._get_all_keys(value, current_path))
        
        return keys
    
    def generate_merge_suggestion(
        self,
        diff_result: DiffResult,
        strategy: str = "prefer_source"
    ) -> Dict[str, Any]:
        """Generate a merge suggestion based on diff result."""
        suggestion = {
            "strategy": strategy,
            "actions": [],
        }
        
        for item in diff_result.added:
            suggestion["actions"].append({
                "action": "add_to_source",
                "path": item.path,
                "value": item.new_value,
            })
        
        for item in diff_result.removed:
            suggestion["actions"].append({
                "action": "remove_from_source",
                "path": item.path,
                "value": item.old_value,
            })
        
        for item in diff_result.changed:
            if strategy == "prefer_source":
                suggestion["actions"].append({
                    "action": "update_target",
                    "path": item.path,
                    "old_value": item.old_value,
                    "new_value": item.old_value,
                })
            else:
                suggestion["actions"].append({
                    "action": "update_source",
                    "path": item.path,
                    "old_value": item.old_value,
                    "new_value": item.new_value,
                })
        
        return suggestion


class DiffFormatter:
    """Format diff results for display."""
    
    @staticmethod
    def format_table(diff_result: DiffResult) -> str:
        """Format diff result as a table."""
        lines = []
        lines.append(f"\nComparing {diff_result.source_env} -> {diff_result.target_env}")
        lines.append("=" * 60)
        
        if not diff_result.has_differences:
            lines.append("\nNo differences found.")
            return "\n".join(lines)
        
        summary = diff_result.to_dict()["summary"]
        lines.append(f"\nSummary: {summary['total']} differences")
        lines.append(f"  Added: {summary['added']}")
        lines.append(f"  Removed: {summary['removed']}")
        lines.append(f"  Changed: {summary['changed']}")
        lines.append(f"  Type Changed: {summary['type_changed']}")
        
        if diff_result.added:
            lines.append("\n--- Added Fields ---")
            for item in diff_result.added:
                lines.append(f"  + {item.path}: {item.new_value}")
        
        if diff_result.removed:
            lines.append("\n--- Removed Fields ---")
            for item in diff_result.removed:
                lines.append(f"  - {item.path}: {item.old_value}")
        
        if diff_result.changed:
            lines.append("\n--- Changed Fields ---")
            for item in diff_result.changed:
                lines.append(f"  ~ {item.path}:")
                lines.append(f"      - {item.old_value}")
                lines.append(f"      + {item.new_value}")
        
        if diff_result.type_changed:
            lines.append("\n--- Type Changed ---")
            for item in diff_result.type_changed:
                lines.append(f"  ! {item.path}: {item.old_type} -> {item.new_type}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_unified(diff_result: DiffResult, context_lines: int = 3) -> str:
        """Format diff result in unified diff style."""
        lines = []
        lines.append(f"--- {diff_result.source_env}")
        lines.append(f"+++ {diff_result.target_env}")
        
        for item in sorted(diff_result.items, key=lambda x: x.path):
            if item.diff_type == DiffType.ADDED:
                lines.append(f"+{item.path}={item.new_value}")
            elif item.diff_type == DiffType.REMOVED:
                lines.append(f"-{item.path}={item.old_value}")
            elif item.diff_type == DiffType.CHANGED:
                lines.append(f"-{item.path}={item.old_value}")
                lines.append(f"+{item.path}={item.new_value}")
            elif item.diff_type == DiffType.TYPE_CHANGED:
                lines.append(f"!{item.path} [{item.old_type} -> {item.new_type}]")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_json(diff_result: DiffResult) -> str:
        """Format diff result as JSON."""
        import json
        return json.dumps(diff_result.to_dict(), indent=2)
