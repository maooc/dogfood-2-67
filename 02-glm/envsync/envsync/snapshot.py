"""Version snapshot and rollback module."""

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class SnapshotMetadata(BaseModel):
    """Metadata for a configuration snapshot."""
    id: str
    environment: str
    timestamp: str
    message: Optional[str] = None
    checksum: str
    file_path: str
    parent_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class Snapshot:
    """A configuration snapshot."""
    
    def __init__(
        self,
        snapshot_id: str,
        environment: str,
        data: Dict[str, Any],
        timestamp: Optional[datetime] = None,
        message: Optional[str] = None,
        parent_id: Optional[str] = None,
        tags: Optional[List[str]] = None
    ):
        self.id = snapshot_id
        self.environment = environment
        self.data = data
        self.timestamp = timestamp or datetime.now()
        self.message = message
        self.parent_id = parent_id
        self.tags = tags or []
        self.checksum = self._compute_checksum(data)
    
    @staticmethod
    def _compute_checksum(data: Dict[str, Any]) -> str:
        """Compute checksum for configuration data."""
        content = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "environment": self.environment,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "checksum": self.checksum,
            "data": self.data,
            "parent_id": self.parent_id,
            "tags": self.tags,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Snapshot":
        """Create from dictionary representation."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        
        return cls(
            snapshot_id=data["id"],
            environment=data["environment"],
            data=data["data"],
            timestamp=timestamp,
            message=data.get("message"),
            parent_id=data.get("parent_id"),
            tags=data.get("tags", []),
        )
    
    def to_metadata(self, file_path: Path) -> SnapshotMetadata:
        """Convert to metadata model."""
        return SnapshotMetadata(
            id=self.id,
            environment=self.environment,
            timestamp=self.timestamp.isoformat(),
            message=self.message,
            checksum=self.checksum,
            file_path=str(file_path),
            parent_id=self.parent_id,
            tags=self.tags,
        )


class SnapshotManager:
    """Manage configuration snapshots."""
    
    def __init__(self, snapshots_dir: Path):
        self.snapshots_dir = snapshots_dir
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.snapshots_dir / "metadata.json"
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self._load_metadata()
    
    def _load_metadata(self) -> None:
        """Load snapshot metadata from disk."""
        if self.metadata_file.exists():
            content = self.metadata_file.read_text(encoding="utf-8")
            self._metadata = json.loads(content)
    
    def _save_metadata(self) -> None:
        """Save snapshot metadata to disk."""
        content = json.dumps(self._metadata, indent=2, ensure_ascii=False)
        self.metadata_file.write_text(content, encoding="utf-8")
    
    def _generate_id(self) -> str:
        """Generate a unique snapshot ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        import uuid
        short_uuid = uuid.uuid4().hex[:8]
        return f"snapshot_{timestamp}_{short_uuid}"
    
    def create_snapshot(
        self,
        environment: str,
        data: Dict[str, Any],
        message: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Snapshot:
        """Create a new snapshot."""
        snapshot_id = self._generate_id()
        
        latest = self.get_latest_snapshot(environment)
        parent_id = latest.id if latest else None
        
        snapshot = Snapshot(
            snapshot_id=snapshot_id,
            environment=environment,
            data=data,
            message=message,
            parent_id=parent_id,
            tags=tags,
        )
        
        snapshot_file = self.snapshots_dir / f"{snapshot_id}.json"
        snapshot_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        
        if environment not in self._metadata:
            self._metadata[environment] = {}
        
        self._metadata[environment][snapshot_id] = snapshot.to_metadata(snapshot_file).model_dump()
        self._save_metadata()
        
        return snapshot
    
    def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        """Get a snapshot by ID."""
        for env_snapshots in self._metadata.values():
            if snapshot_id in env_snapshots:
                meta = env_snapshots[snapshot_id]
                snapshot_file = Path(meta["file_path"])
                
                if snapshot_file.exists():
                    data = json.loads(snapshot_file.read_text(encoding="utf-8"))
                    return Snapshot(
                        snapshot_id=meta["id"],
                        environment=meta["environment"],
                        data=data,
                        timestamp=datetime.fromisoformat(meta["timestamp"]),
                        message=meta.get("message"),
                        parent_id=meta.get("parent_id"),
                        tags=meta.get("tags", []),
                    )
        
        return None
    
    def get_latest_snapshot(self, environment: str) -> Optional[Snapshot]:
        """Get the latest snapshot for an environment."""
        if environment not in self._metadata:
            return None
        
        snapshots = self._metadata[environment]
        if not snapshots:
            return None
        
        sorted_ids = sorted(
            snapshots.keys(),
            key=lambda x: snapshots[x]["timestamp"],
            reverse=True
        )
        
        return self.get_snapshot(sorted_ids[0])
    
    def list_snapshots(
        self,
        environment: Optional[str] = None,
        limit: int = 20,
        tags: Optional[List[str]] = None
    ) -> List[SnapshotMetadata]:
        """List snapshots with optional filtering."""
        all_snapshots: List[SnapshotMetadata] = []
        
        envs_to_check = [environment] if environment else list(self._metadata.keys())
        
        for env in envs_to_check:
            if env not in self._metadata:
                continue
            
            for snapshot_id, meta in self._metadata[env].items():
                if tags:
                    snapshot_tags = set(meta.get("tags", []))
                    if not any(t in snapshot_tags for t in tags):
                        continue
                
                all_snapshots.append(SnapshotMetadata(**meta))
        
        all_snapshots.sort(key=lambda x: x.timestamp, reverse=True)
        
        return all_snapshots[:limit]
    
    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot."""
        for env_name, env_snapshots in self._metadata.items():
            if snapshot_id in env_snapshots:
                meta = env_snapshots[snapshot_id]
                snapshot_file = Path(meta["file_path"])
                
                if snapshot_file.exists():
                    snapshot_file.unlink()
                
                del env_snapshots[snapshot_id]
                self._save_metadata()
                return True
        
        return False
    
    def cleanup_old_snapshots(
        self,
        environment: str,
        keep_count: int = 10
    ) -> List[str]:
        """Clean up old snapshots, keeping only the most recent ones."""
        if environment not in self._metadata:
            return []
        
        snapshots = self._metadata[environment]
        if len(snapshots) <= keep_count:
            return []
        
        sorted_ids = sorted(
            snapshots.keys(),
            key=lambda x: snapshots[x]["timestamp"],
            reverse=True
        )
        
        to_delete = sorted_ids[keep_count:]
        deleted = []
        
        for snapshot_id in to_delete:
            if self.delete_snapshot(snapshot_id):
                deleted.append(snapshot_id)
        
        return deleted
    
    def get_snapshot_history(
        self,
        environment: str,
        limit: int = 10
    ) -> List[SnapshotMetadata]:
        """Get snapshot history for an environment."""
        if environment not in self._metadata:
            return []
        
        snapshots = [
            SnapshotMetadata(**meta)
            for meta in self._metadata[environment].values()
        ]
        
        snapshots.sort(key=lambda x: x.timestamp, reverse=True)
        return snapshots[:limit]


class RollbackManager:
    """Manage configuration rollback operations."""
    
    def __init__(self, snapshot_manager: SnapshotManager):
        self.snapshot_manager = snapshot_manager
    
    def rollback_to_snapshot(
        self,
        snapshot_id: str,
        target_path: Optional[Path] = None
    ) -> Tuple[Dict[str, Any], str]:
        """Rollback configuration to a specific snapshot."""
        snapshot = self.snapshot_manager.get_snapshot(snapshot_id)
        
        if snapshot is None:
            raise ValueError(f"Snapshot not found: {snapshot_id}")
        
        if target_path:
            from .config import ConfigLoader, ConfigFormat
            config_format = ConfigFormat.detect(target_path)
            ConfigLoader.save(target_path, snapshot.data, config_format)
        
        return snapshot.data, snapshot.environment
    
    def rollback_to_previous(
        self,
        environment: str,
        target_path: Optional[Path] = None
    ) -> Tuple[Dict[str, Any], str]:
        """Rollback to the previous snapshot for an environment."""
        history = self.snapshot_manager.get_snapshot_history(environment, limit=2)
        
        if len(history) < 2:
            raise ValueError(f"No previous snapshot found for environment: {environment}")
        
        previous_snapshot = history[1]
        return self.rollback_to_snapshot(previous_snapshot.id, target_path)
    
    def rollback_to_timestamp(
        self,
        environment: str,
        timestamp: datetime,
        target_path: Optional[Path] = None
    ) -> Tuple[Dict[str, Any], str]:
        """Rollback to the snapshot closest to a timestamp."""
        history = self.snapshot_manager.get_snapshot_history(environment, limit=100)
        
        if not history:
            raise ValueError(f"No snapshots found for environment: {environment}")
        
        closest = None
        min_diff = None
        
        for snapshot in history:
            snapshot_time = datetime.fromisoformat(snapshot.timestamp)
            diff = abs((snapshot_time - timestamp).total_seconds())
            if min_diff is None or diff < min_diff:
                min_diff = diff
                closest = snapshot
        
        if closest is None:
            raise ValueError("Could not find a snapshot near the specified timestamp")
        
        return self.rollback_to_snapshot(closest.id, target_path)
    
    def rollback_to_tag(
        self,
        environment: str,
        tag: str,
        target_path: Optional[Path] = None
    ) -> Tuple[Dict[str, Any], str]:
        """Rollback to a snapshot with a specific tag."""
        snapshots = self.snapshot_manager.list_snapshots(
            environment=environment,
            tags=[tag],
            limit=1
        )
        
        if not snapshots:
            raise ValueError(f"No snapshot found with tag '{tag}' for environment: {environment}")
        
        return self.rollback_to_snapshot(snapshots[0].id, target_path)
    
    def preview_rollback(
        self,
        snapshot_id: str
    ) -> Dict[str, Any]:
        """Preview a rollback without applying it."""
        snapshot = self.snapshot_manager.get_snapshot(snapshot_id)
        
        if snapshot is None:
            raise ValueError(f"Snapshot not found: {snapshot_id}")
        
        return {
            "snapshot_id": snapshot.id,
            "environment": snapshot.environment,
            "timestamp": snapshot.timestamp.isoformat(),
            "message": snapshot.message,
            "data": snapshot.data,
        }
    
    def compare_with_current(
        self,
        snapshot_id: str,
        current_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare a snapshot with current configuration."""
        from .diff import ConfigDiffer, DiffFormatter
        
        snapshot = self.snapshot_manager.get_snapshot(snapshot_id)
        
        if snapshot is None:
            raise ValueError(f"Snapshot not found: {snapshot_id}")
        
        differ = ConfigDiffer()
        diff_result = differ.compare(
            current_data,
            snapshot.data,
            "current",
            f"snapshot_{snapshot_id}"
        )
        
        return {
            "snapshot_id": snapshot.id,
            "environment": snapshot.environment,
            "diff": diff_result.to_dict(),
        }


class SnapshotService:
    """High-level service for snapshot operations."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.snapshots_dir = project_root / ".envsync" / "snapshots"
        self.snapshot_manager = SnapshotManager(self.snapshots_dir)
        self.rollback_manager = RollbackManager(self.snapshot_manager)
    
    def create_snapshot(
        self,
        environment: str,
        data: Dict[str, Any],
        message: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Snapshot:
        """Create a snapshot for an environment."""
        return self.snapshot_manager.create_snapshot(
            environment=environment,
            data=data,
            message=message,
            tags=tags,
        )
    
    def create_snapshot_from_file(
        self,
        environment: str,
        file_path: Path,
        message: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Snapshot:
        """Create a snapshot from a configuration file."""
        from .config import ConfigLoader
        
        data = ConfigLoader.load(file_path)
        return self.create_snapshot(environment, data, message, tags)
    
    def auto_snapshot(
        self,
        environment: str,
        data: Dict[str, Any],
        operation: str = "auto"
    ) -> Optional[Snapshot]:
        """Create an automatic snapshot before operations."""
        latest = self.snapshot_manager.get_latest_snapshot(environment)
        
        if latest:
            current_checksum = Snapshot._compute_checksum(data)
            if current_checksum == latest.checksum:
                return None
        
        message = f"Auto snapshot before {operation}"
        return self.create_snapshot(
            environment=environment,
            data=data,
            message=message,
            tags=["auto"],
        )
    
    def rollback(
        self,
        environment: str,
        snapshot_id: Optional[str] = None,
        target_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Rollback an environment to a snapshot."""
        if snapshot_id:
            data, env = self.rollback_manager.rollback_to_snapshot(
                snapshot_id, target_path
            )
        else:
            data, env = self.rollback_manager.rollback_to_previous(
                environment, target_path
            )
        
        return {
            "environment": env,
            "snapshot_id": snapshot_id,
            "data": data,
        }
    
    def list_snapshots(
        self,
        environment: Optional[str] = None,
        limit: int = 20,
        tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """List snapshots."""
        snapshots = self.snapshot_manager.list_snapshots(
            environment=environment,
            limit=limit,
            tags=tags,
        )
        
        return [
            {
                "id": s.id,
                "environment": s.environment,
                "timestamp": s.timestamp,
                "message": s.message,
                "tags": s.tags,
            }
            for s in snapshots
        ]
    
    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Get a snapshot by ID."""
        snapshot = self.snapshot_manager.get_snapshot(snapshot_id)
        
        if snapshot:
            return {
                "id": snapshot.id,
                "environment": snapshot.environment,
                "timestamp": snapshot.timestamp.isoformat(),
                "message": snapshot.message,
                "data": snapshot.data,
                "tags": snapshot.tags,
            }
        
        return None
    
    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot."""
        return self.snapshot_manager.delete_snapshot(snapshot_id)
    
    def cleanup(self, environment: str, keep_count: int = 10) -> List[str]:
        """Clean up old snapshots."""
        return self.snapshot_manager.cleanup_old_snapshots(
            environment, keep_count
        )
