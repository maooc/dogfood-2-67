"""Tests for snapshot module."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from envsync.snapshot import (
    Snapshot,
    SnapshotManager,
    SnapshotService,
    SnapshotMetadata,
)


class TestSnapshot:
    def test_create_snapshot(self):
        data = {"key": "value"}
        snapshot = Snapshot("test-id", "production", data)
        
        assert snapshot.environment == "production"
        assert snapshot.data == data
        assert snapshot.id == "test-id"
        assert snapshot.timestamp is not None

    def test_snapshot_with_message(self):
        data = {"key": "value"}
        snapshot = Snapshot("test-id", "production", data, message="Initial snapshot")
        
        assert snapshot.message == "Initial snapshot"

    def test_snapshot_checksum(self):
        data = {"key": "value"}
        snapshot1 = Snapshot("id1", "production", data)
        snapshot2 = Snapshot("id2", "production", data)
        
        assert snapshot1.checksum == snapshot2.checksum

    def test_snapshot_different_checksum(self):
        snapshot1 = Snapshot("id1", "production", {"key": "value1"})
        snapshot2 = Snapshot("id2", "production", {"key": "value2"})
        
        assert snapshot1.checksum != snapshot2.checksum

    def test_to_dict(self):
        data = {"key": "value"}
        snapshot = Snapshot("test-id", "production", data, message="test")
        
        result = snapshot.to_dict()
        
        assert result["environment"] == "production"
        assert result["data"] == data
        assert result["message"] == "test"

    def test_from_dict(self):
        data = {
            "id": "test-id",
            "environment": "production",
            "timestamp": "2024-01-01T00:00:00",
            "message": "test",
            "checksum": "abc123",
            "data": {"key": "value"},
            "parent_id": None,
            "tags": []
        }
        
        snapshot = Snapshot.from_dict(data)
        
        assert snapshot.id == "test-id"
        assert snapshot.environment == "production"
        assert snapshot.message == "test"

    def test_to_metadata(self, tmp_path):
        data = {"key": "value"}
        snapshot = Snapshot("test-id", "production", data)
        
        file_path = tmp_path / "snapshot.json"
        metadata = snapshot.to_metadata(file_path)
        
        assert metadata.environment == "production"
        assert metadata.file_path == str(file_path)


class TestSnapshotManager:
    def test_create_snapshot(self, tmp_path):
        manager = SnapshotManager(tmp_path)
        
        data = {"key": "value"}
        snapshot = manager.create_snapshot("production", data)
        
        assert snapshot is not None
        assert snapshot.environment == "production"

    def test_get_snapshot(self, tmp_path):
        manager = SnapshotManager(tmp_path)
        
        data = {"key": "value"}
        created = manager.create_snapshot("production", data)
        
        loaded = manager.get_snapshot(created.id)
        
        assert loaded is not None
        assert loaded.data == data
        assert loaded.environment == "production"

    def test_get_snapshot_not_found(self, tmp_path):
        manager = SnapshotManager(tmp_path)
        
        result = manager.get_snapshot("nonexistent")
        assert result is None

    def test_list_snapshots(self, tmp_path):
        manager = SnapshotManager(tmp_path)
        
        manager.create_snapshot("production", {"v": 1})
        manager.create_snapshot("production", {"v": 2})
        manager.create_snapshot("development", {"v": 3})
        
        all_snapshots = manager.list_snapshots()
        assert len(all_snapshots) == 3
        
        prod_snapshots = manager.list_snapshots(environment="production")
        assert len(prod_snapshots) == 2
        
        dev_snapshots = manager.list_snapshots(environment="development")
        assert len(dev_snapshots) == 1

    def test_delete_snapshot(self, tmp_path):
        manager = SnapshotManager(tmp_path)
        
        snapshot = manager.create_snapshot("production", {"key": "value"})
        
        result = manager.delete_snapshot(snapshot.id)
        assert result is True
        
        loaded = manager.get_snapshot(snapshot.id)
        assert loaded is None

    def test_delete_snapshot_not_found(self, tmp_path):
        manager = SnapshotManager(tmp_path)
        
        result = manager.delete_snapshot("nonexistent")
        assert result is False

    def test_get_latest_snapshot(self, tmp_path):
        manager = SnapshotManager(tmp_path)
        
        manager.create_snapshot("production", {"v": 1})
        import time
        time.sleep(0.01)
        manager.create_snapshot("production", {"v": 2})
        
        latest = manager.get_latest_snapshot("production")
        
        assert latest is not None
        assert latest.data["v"] == 2

    def test_get_latest_snapshot_no_environment(self, tmp_path):
        manager = SnapshotManager(tmp_path)
        
        snapshot = manager.create_snapshot("production", {"v": 1})
        
        latest = manager.get_latest_snapshot("development")
        
        assert latest is None


class TestSnapshotService:
    def test_create_snapshot(self, tmp_path):
        service = SnapshotService(tmp_path)
        
        data = {"key": "value"}
        snapshot = service.create_snapshot("production", data, message="test")
        
        assert snapshot is not None
        assert snapshot.message == "test"

    def test_get_snapshot(self, tmp_path):
        service = SnapshotService(tmp_path)
        
        data = {"key": "value"}
        snapshot = service.create_snapshot("production", data)
        
        loaded = service.get_snapshot(snapshot.id)
        
        assert loaded is not None
        assert loaded["data"] == data

    def test_list_snapshots(self, tmp_path):
        service = SnapshotService(tmp_path)
        
        service.create_snapshot("production", {"v": 1})
        service.create_snapshot("production", {"v": 2})
        
        snapshots = service.list_snapshots("production")
        
        assert len(snapshots) == 2

    def test_restore_snapshot(self, tmp_path):
        service = SnapshotService(tmp_path)
        
        data = {"key": "value"}
        snapshot = service.create_snapshot("production", data)
        
        restored = service.get_snapshot(snapshot.id)
        
        assert restored is not None
        assert restored["data"] == data
        assert restored["environment"] == "production"

    def test_restore_snapshot_not_found(self, tmp_path):
        service = SnapshotService(tmp_path)
        
        result = service.get_snapshot("nonexistent")
        assert result is None

    def test_delete_snapshot(self, tmp_path):
        service = SnapshotService(tmp_path)
        
        snapshot = service.create_snapshot("production", {"key": "value"})
        
        result = service.delete_snapshot(snapshot.id)
        assert result is True
        
        loaded = service.get_snapshot(snapshot.id)
        assert loaded is None


class TestSnapshotMetadata:
    def test_from_snapshot(self, tmp_path):
        data = {"key": "value"}
        snapshot = Snapshot("test-id", "production", data, message="test")
        
        file_path = tmp_path / "snapshot.json"
        metadata = snapshot.to_metadata(file_path)
        
        assert metadata.id == snapshot.id
        assert metadata.environment == "production"
        assert metadata.message == "test"

    def test_to_dict(self):
        metadata = SnapshotMetadata(
            id="test-id",
            environment="production",
            timestamp="2024-01-01T00:00:00",
            message="test",
            checksum="abc123",
            file_path="/path/to/snapshot.json",
            parent_id=None,
            tags=["tag1"]
        )
        
        result = metadata.model_dump()
        
        assert result["id"] == "test-id"
        assert result["environment"] == "production"
        assert result["tags"] == ["tag1"]
