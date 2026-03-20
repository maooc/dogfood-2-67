"""版本快照和回滚功能."""

from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from envsync.config import ConfigManager
from envsync.models import ConfigFile, ConfigFormat, Snapshot


class SnapshotManager:
    """快照管理器."""

    SNAPSHOT_INDEX = "index.yaml"

    def __init__(self, config_manager: ConfigManager) -> None:
        """初始化快照管理器.

        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.snapshots_dir = config_manager.config.snapshots_dir
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        environment: str,
        description: Optional[str] = None,
        include_files: bool = True,
    ) -> Snapshot:
        """创建快照.

        Args:
            environment: 环境名称
            description: 快照描述
            include_files: 是否包含配置文件内容

        Returns:
            快照对象
        """
        snapshot_id = self._generate_id()
        snapshot_dir = self.snapshots_dir / snapshot_id
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        env = self.config_manager.get_environment(environment)
        if not env:
            raise ValueError(f"环境不存在: {environment}")

        variables = {
            name: var.value
            for name, var in env.variables.items()
        }

        files: Dict[str, str] = {}

        if include_files:
            config_files = self.config_manager.get_environment_files(environment)
            for cf in config_files:
                if cf.path.exists():
                    content = ConfigManager.load_config_file(cf.path, cf.format)
                    files[cf.name] = json.dumps(content, ensure_ascii=False)

                    target_path = snapshot_dir / f"{cf.name}.{cf.format.value}"
                    shutil.copy2(cf.path, target_path)

        snapshot = Snapshot(
            id=snapshot_id,
            environment=environment,
            description=description,
            files=files,
            variables=variables,
        )

        snapshot_file = snapshot_dir / "snapshot.yaml"
        with open(snapshot_file, "w", encoding="utf-8") as f:
            yaml.dump(snapshot.model_dump(), f, allow_unicode=True)

        self._add_to_index(snapshot)

        return snapshot

    def list(self, environment: Optional[str] = None) -> List[Snapshot]:
        """列出快照.

        Args:
            environment: 可选的环境过滤

        Returns:
            快照列表
        """
        index = self._load_index()
        snapshots = []

        for snapshot_data in index.get("snapshots", []):
            snapshot = Snapshot(**snapshot_data)
            if environment is None or snapshot.environment == environment:
                snapshots.append(snapshot)

        return sorted(snapshots, key=lambda s: s.created_at, reverse=True)

    def get(self, snapshot_id: str) -> Optional[Snapshot]:
        """获取快照.

        Args:
            snapshot_id: 快照 ID

        Returns:
            快照对象，不存在则返回 None
        """
        snapshot_file = self.snapshots_dir / snapshot_id / "snapshot.yaml"
        if not snapshot_file.exists():
            return None

        with open(snapshot_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return Snapshot(**data)

    def restore(
        self,
        snapshot_id: str,
        target_environment: Optional[str] = None,
        force: bool = False,
    ) -> None:
        """恢复快照.

        Args:
            snapshot_id: 快照 ID
            target_environment: 目标环境，默认使用快照原环境
            force: 是否强制恢复，覆盖现有配置
        """
        snapshot = self.get(snapshot_id)
        if not snapshot:
            raise ValueError(f"快照不存在: {snapshot_id}")

        environment = target_environment or snapshot.environment

        env = self.config_manager.get_environment(environment)
        if not env:
            raise ValueError(f"环境不存在: {environment}")

        for name, value in snapshot.variables.items():
            self.config_manager.set_variable(environment, name, value)

        snapshot_dir = self.snapshots_dir / snapshot_id

        for file_name, content_json in snapshot.files.items():
            config_file = self.config_manager.get_config_file(file_name)
            if config_file and config_file.environment == environment:
                if config_file.path.exists() and not force:
                    raise ValueError(f"文件已存在，使用 --force 覆盖: {config_file.path}")

                snapshot_file = snapshot_dir / f"{file_name}.{config_file.format.value}"
                if snapshot_file.exists():
                    shutil.copy2(snapshot_file, config_file.path)
                else:
                    content = json.loads(content_json)
                    ConfigManager.save_config_file(
                        config_file.path,
                        config_file.format,
                        content,
                    )

    def delete(self, snapshot_id: str) -> None:
        """删除快照.

        Args:
            snapshot_id: 快照 ID
        """
        snapshot_dir = self.snapshots_dir / snapshot_id
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir)

        self._remove_from_index(snapshot_id)

    def export(
        self,
        snapshot_id: str,
        output_path: Path,
        format: str = "zip",
    ) -> Path:
        """导出快照.

        Args:
            snapshot_id: 快照 ID
            output_path: 输出路径
            format: 导出格式（zip 或 tar.gz）

        Returns:
            导出文件路径
        """
        snapshot = self.get(snapshot_id)
        if not snapshot:
            raise ValueError(f"快照不存在: {snapshot_id}")

        snapshot_dir = self.snapshots_dir / snapshot_id

        if format == "zip":
            if not output_path.suffix == ".zip":
                output_path = output_path.with_suffix(".zip")
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in snapshot_dir.rglob("*"):
                    if file_path.is_file():
                        zf.write(file_path, file_path.relative_to(snapshot_dir))
        elif format in ("tar", "tar.gz", "tgz"):
            if not output_path.suffix in (".tar", ".gz"):
                output_path = output_path.with_suffix(".tar.gz")
            with tarfile.open(output_path, "w:gz") as tf:
                tf.add(snapshot_dir, arcname=snapshot_id)
        else:
            raise ValueError(f"不支持的导出格式: {format}")

        return output_path

    def import_snapshot(self, archive_path: Path) -> Snapshot:
        """导入快照.

        Args:
            archive_path: 归档文件路径

        Returns:
            导入的快照对象
        """
        snapshot_id = self._generate_id()
        snapshot_dir = self.snapshots_dir / snapshot_id
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        if archive_path.suffix == ".zip":
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(snapshot_dir)
        elif archive_path.suffix in (".tar", ".gz", ".tgz"):
            with tarfile.open(archive_path, "r:*") as tf:
                tf.extractall(snapshot_dir)
        else:
            raise ValueError(f"不支持的归档格式: {archive_path.suffix}")

        snapshot_file = snapshot_dir / "snapshot.yaml"
        if not snapshot_file.exists():
            raise ValueError("无效的快照归档：缺少 snapshot.yaml")

        with open(snapshot_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        data["id"] = snapshot_id
        data["created_at"] = datetime.now()

        snapshot = Snapshot(**data)

        new_snapshot_file = snapshot_dir / "snapshot.yaml"
        with open(new_snapshot_file, "w", encoding="utf-8") as f:
            yaml.dump(snapshot.model_dump(), f, allow_unicode=True)

        self._add_to_index(snapshot)

        return snapshot

    def compare(
        self,
        snapshot_id1: str,
        snapshot_id2: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """对比两个快照.

        Args:
            snapshot_id1: 第一个快照 ID
            snapshot_id2: 第二个快照 ID

        Returns:
            差异字典
        """
        snapshot1 = self.get(snapshot_id1)
        snapshot2 = self.get(snapshot_id2)

        if not snapshot1 or not snapshot2:
            raise ValueError("快照不存在")

        differences: Dict[str, List[Dict[str, Any]]] = {
            "variables": [],
            "files": [],
        }

        all_vars = set(snapshot1.variables.keys()) | set(snapshot2.variables.keys())
        for var in all_vars:
            val1 = snapshot1.variables.get(var)
            val2 = snapshot2.variables.get(var)
            if val1 != val2:
                differences["variables"].append({
                    "name": var,
                    "old": val1,
                    "new": val2,
                })

        all_files = set(snapshot1.files.keys()) | set(snapshot2.files.keys())
        for file_name in all_files:
            content1 = snapshot1.files.get(file_name)
            content2 = snapshot2.files.get(file_name)
            if content1 != content2:
                differences["files"].append({
                    "name": file_name,
                    "changed": content1 is not None and content2 is not None,
                    "added": content1 is None,
                    "removed": content2 is None,
                })

        return differences

    def cleanup(self, keep_count: int = 10, environment: Optional[str] = None) -> int:
        """清理旧快照.

        Args:
            keep_count: 保留的快照数量
            environment: 可选的环境过滤

        Returns:
            删除的快照数量
        """
        snapshots = self.list(environment)
        to_delete = snapshots[keep_count:]

        for snapshot in to_delete:
            self.delete(snapshot.id)

        return len(to_delete)

    def _generate_id(self) -> str:
        """生成唯一 ID."""
        return uuid.uuid4().hex[:12]

    def _load_index(self) -> Dict[str, Any]:
        """加载索引文件."""
        index_file = self.snapshots_dir / self.SNAPSHOT_INDEX
        if index_file.exists():
            with open(index_file, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {"snapshots": []}

    def _save_index(self, index: Dict[str, Any]) -> None:
        """保存索引文件."""
        index_file = self.snapshots_dir / self.SNAPSHOT_INDEX
        with open(index_file, "w", encoding="utf-8") as f:
            yaml.dump(index, f, allow_unicode=True)

    def _add_to_index(self, snapshot: Snapshot) -> None:
        """添加快照到索引."""
        index = self._load_index()

        snapshot_data = snapshot.model_dump()
        snapshot_data["created_at"] = snapshot.created_at.isoformat()

        existing = next(
            (s for s in index["snapshots"] if s["id"] == snapshot.id),
            None,
        )
        if existing:
            existing.update(snapshot_data)
        else:
            index["snapshots"].append(snapshot_data)

        self._save_index(index)

    def _remove_from_index(self, snapshot_id: str) -> None:
        """从索引中移除快照."""
        index = self._load_index()
        index["snapshots"] = [s for s in index["snapshots"] if s["id"] != snapshot_id]
        self._save_index(index)
