"""Tests for diff module."""

import tempfile
from pathlib import Path

import pytest

from envsync.diff import (
    ConfigDiffer,
    DiffFormatter,
    DiffResult,
    DiffType,
    DiffItem,
)


class TestConfigDiffer:
    def test_diff_added(self):
        differ = ConfigDiffer()
        
        result = differ.compare({}, {"new_key": "value"})
        
        assert len(result.added) == 1
        assert result.added[0].path == "new_key"
        assert result.added[0].new_value == "value"

    def test_diff_removed(self):
        differ = ConfigDiffer()
        
        result = differ.compare({"old_key": "value"}, {})
        
        assert len(result.removed) == 1
        assert result.removed[0].path == "old_key"
        assert result.removed[0].old_value == "value"

    def test_diff_changed(self):
        differ = ConfigDiffer()
        
        result = differ.compare({"key": "old"}, {"key": "new"})
        
        assert len(result.changed) == 1
        assert result.changed[0].path == "key"
        assert result.changed[0].old_value == "old"
        assert result.changed[0].new_value == "new"

    def test_diff_nested(self):
        differ = ConfigDiffer()
        
        old = {"db": {"host": "localhost", "port": 5432}}
        new = {"db": {"host": "remote", "port": 5432}}
        
        result = differ.compare(old, new)
        
        assert len(result.changed) == 1
        assert result.changed[0].path == "db.host"
        assert result.changed[0].old_value == "localhost"
        assert result.changed[0].new_value == "remote"

    def test_diff_nested_added(self):
        differ = ConfigDiffer()
        
        old = {"db": {"host": "localhost"}}
        new = {"db": {"host": "localhost", "port": 5432}}
        
        result = differ.compare(old, new)
        
        assert len(result.added) == 1
        assert result.added[0].path == "db.port"

    def test_diff_nested_removed(self):
        differ = ConfigDiffer()
        
        old = {"db": {"host": "localhost", "port": 5432}}
        new = {"db": {"host": "localhost"}}
        
        result = differ.compare(old, new)
        
        assert len(result.removed) == 1
        assert result.removed[0].path == "db.port"

    def test_diff_type_change(self):
        differ = ConfigDiffer()
        
        result = differ.compare({"key": "123"}, {"key": 123})
        
        assert len(result.type_changed) == 1

    def test_diff_ignore_keys(self):
        differ = ConfigDiffer(ignore_fields=["timestamp"])
        
        old = {"key": "value", "timestamp": "old"}
        new = {"key": "value", "timestamp": "new"}
        
        result = differ.compare(old, new)
        
        assert len(result.changed) == 0

    def test_diff_identical(self):
        differ = ConfigDiffer()
        
        data = {"key": "value", "nested": {"a": 1}}
        result = differ.compare(data, data)
        
        assert len(result.added) == 0
        assert len(result.removed) == 0
        assert len(result.changed) == 0

    def test_diff_list(self):
        differ = ConfigDiffer()
        
        old = {"items": ["a", "b"]}
        new = {"items": ["a", "c"]}
        
        result = differ.compare(old, new)
        
        assert result.has_differences

    def test_diff_deep_list(self):
        differ = ConfigDiffer()
        
        old = {"items": [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]}
        new = {"items": [{"id": 1, "name": "a"}, {"id": 2, "name": "c"}]}
        
        result = differ.compare(old, new)
        
        assert result.has_differences


class TestDiffFormatter:
    def test_format_summary(self):
        result = DiffResult(source_env="source", target_env="target")
        result.items.append(DiffItem(path="new", diff_type=DiffType.ADDED, new_value="value"))
        result.items.append(DiffItem(path="old", diff_type=DiffType.REMOVED, old_value="value"))
        result.items.append(DiffItem(
            path="changed",
            diff_type=DiffType.CHANGED,
            old_value="old",
            new_value="new"
        ))
        
        formatter = DiffFormatter()
        output = formatter.format_table(result)
        
        assert "Added: 1" in output
        assert "Removed: 1" in output
        assert "Changed: 1" in output

    def test_format_detailed(self):
        result = DiffResult(source_env="source", target_env="target")
        result.items.append(DiffItem(
            path="db.host",
            diff_type=DiffType.CHANGED,
            old_value="localhost",
            new_value="remote"
        ))
        
        formatter = DiffFormatter()
        output = formatter.format_table(result)
        
        assert "db.host" in output
        assert "localhost" in output
        assert "remote" in output

    def test_format_json(self):
        result = DiffResult(source_env="source", target_env="target")
        result.items.append(DiffItem(path="new", diff_type=DiffType.ADDED, new_value="value"))
        
        formatter = DiffFormatter()
        json_str = formatter.format_json(result)
        
        import json
        data = json.loads(json_str)
        
        assert "items" in data
        assert len(data["items"]) == 1

    def test_format_unified(self):
        result = DiffResult(source_env="source", target_env="target")
        result.items.append(DiffItem(path="new", diff_type=DiffType.ADDED, new_value="value"))
        
        formatter = DiffFormatter()
        output = formatter.format_unified(result)
        
        assert "+new=value" in output


class TestDiffResult:
    def test_has_changes(self):
        result = DiffResult(source_env="source", target_env="target")
        assert result.has_differences is False
        
        result.items.append(DiffItem(path="key", diff_type=DiffType.ADDED, new_value="value"))
        assert result.has_differences is True

    def test_total_changes(self):
        result = DiffResult(source_env="source", target_env="target")
        result.items.append(DiffItem(path="a", diff_type=DiffType.ADDED, new_value="1"))
        result.items.append(DiffItem(path="b", diff_type=DiffType.REMOVED, old_value="2"))
        result.items.append(DiffItem(path="c", diff_type=DiffType.CHANGED, old_value="3", new_value="4"))
        
        assert len(result.items) == 3

    def test_to_dict(self):
        result = DiffResult(source_env="source", target_env="target")
        result.items.append(DiffItem(path="new", diff_type=DiffType.ADDED, new_value="value"))
        
        data = result.to_dict()
        
        assert "items" in data
        assert "summary" in data
        assert len(data["items"]) == 1


class TestDiffType:
    def test_diff_type_values(self):
        assert DiffType.ADDED.value == "added"
        assert DiffType.REMOVED.value == "removed"
        assert DiffType.CHANGED.value == "changed"
        assert DiffType.TYPE_CHANGED.value == "type_changed"
