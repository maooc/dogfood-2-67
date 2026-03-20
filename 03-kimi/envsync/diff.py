"""环境差异对比功能."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from rich.console import Console
from rich.table import Table

from envsync.config import ConfigManager
from envsync.models import ConfigFile, ConfigFormat


class DiffType(str, Enum):
    """差异类型."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class DiffResult:
    """差异结果."""

    path: str
    diff_type: DiffType
    old_value: Any = None
    new_value: Any = None


class DiffEngine:
    """差异对比引擎."""

    def __init__(self, config_manager: ConfigManager) -> None:
        """初始化差异引擎.

        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager

    def compare_variables(
        self,
        env1: str,
        env2: str,
    ) -> List[DiffResult]:
        """对比两个环境的变量差异.

        Args:
            env1: 第一个环境名称
            env2: 第二个环境名称

        Returns:
            差异结果列表
        """
        vars1 = self.config_manager.get_merged_variables(env1)
        vars2 = self.config_manager.get_merged_variables(env2)

        return self._compare_dicts(vars1, vars2)

    def compare_configs(
        self,
        config_file: ConfigFile,
        env1: str,
        env2: str,
    ) -> List[DiffResult]:
        """对比配置文件在两个环境中的差异.

        Args:
            config_file: 配置文件对象
            env1: 第一个环境名称
            env2: 第二个环境名称

        Returns:
            差异结果列表
        """
        from envsync.template import TemplateEngine

        template_engine = TemplateEngine(self.config_manager)

        preview1 = template_engine.preview(config_file, env1)
        preview2 = template_engine.preview(config_file, env2)

        data1 = self._parse_preview(preview1, config_file.format)
        data2 = self._parse_preview(preview2, config_file.format)

        return self._compare_dicts(data1, data2, path_prefix="")

    def compare_environments(
        self,
        env1: str,
        env2: str,
        include_files: bool = True,
    ) -> Dict[str, List[DiffResult]]:
        """全面对比两个环境.

        Args:
            env1: 第一个环境名称
            env2: 第二个环境名称
            include_files: 是否包含配置文件对比

        Returns:
            差异结果字典
        """
        results: Dict[str, List[DiffResult]] = {}

        results["variables"] = self.compare_variables(env1, env2)

        if include_files:
            files1 = self.config_manager.get_environment_files(env1)
            files2 = self.config_manager.get_environment_files(env2)

            file_names1 = {f.name for f in files1}
            file_names2 = {f.name for f in files2}

            all_files = file_names1 | file_names2

            for file_name in all_files:
                file1 = next((f for f in files1 if f.name == file_name), None)
                file2 = next((f for f in files2 if f.name == file_name), None)

                if file1 and file2:
                    results[f"file:{file_name}"] = self.compare_configs(file1, env1, env2)
                elif file1:
                    results[f"file:{file_name}"] = [
                        DiffResult(path="", diff_type=DiffType.REMOVED)
                    ]
                else:
                    results[f"file:{file_name}"] = [
                        DiffResult(path="", diff_type=DiffType.ADDED)
                    ]

        return results

    def _compare_dicts(
        self,
        dict1: Dict[str, Any],
        dict2: Dict[str, Any],
        path_prefix: str = "",
    ) -> List[DiffResult]:
        """递归对比两个字典.

        Args:
            dict1: 第一个字典
            dict2: 第二个字典
            path_prefix: 路径前缀

        Returns:
            差异结果列表
        """
        results: List[DiffResult] = []

        all_keys = set(dict1.keys()) | set(dict2.keys())

        for key in all_keys:
            path = f"{path_prefix}.{key}" if path_prefix else key

            if key not in dict1:
                results.append(DiffResult(
                    path=path,
                    diff_type=DiffType.ADDED,
                    new_value=dict2[key],
                ))
            elif key not in dict2:
                results.append(DiffResult(
                    path=path,
                    diff_type=DiffType.REMOVED,
                    old_value=dict1[key],
                ))
            else:
                val1, val2 = dict1[key], dict2[key]

                if type(val1) != type(val2):
                    results.append(DiffResult(
                        path=path,
                        diff_type=DiffType.MODIFIED,
                        old_value=val1,
                        new_value=val2,
                    ))
                elif isinstance(val1, dict):
                    results.extend(self._compare_dicts(val1, val2, path))
                elif isinstance(val1, list):
                    results.extend(self._compare_lists(val1, val2, path))
                elif val1 != val2:
                    results.append(DiffResult(
                        path=path,
                        diff_type=DiffType.MODIFIED,
                        old_value=val1,
                        new_value=val2,
                    ))

        return results

    def _compare_lists(
        self,
        list1: List[Any],
        list2: List[Any],
        path: str,
    ) -> List[DiffResult]:
        """对比两个列表.

        Args:
            list1: 第一个列表
            list2: 第二个列表
            path: 当前路径

        Returns:
            差异结果列表
        """
        results: List[DiffResult] = []

        if len(list1) != len(list2):
            results.append(DiffResult(
                path=path,
                diff_type=DiffType.MODIFIED,
                old_value=f"[list with {len(list1)} items]",
                new_value=f"[list with {len(list2)} items]",
            ))
        else:
            for i, (val1, val2) in enumerate(zip(list1, list2)):
                item_path = f"{path}[{i}]"

                if isinstance(val1, dict) and isinstance(val2, dict):
                    results.extend(self._compare_dicts(val1, val2, item_path))
                elif val1 != val2:
                    results.append(DiffResult(
                        path=item_path,
                        diff_type=DiffType.MODIFIED,
                        old_value=val1,
                        new_value=val2,
                    ))

        return results

    def _parse_preview(self, preview: str, format: ConfigFormat) -> Dict[str, Any]:
        """解析预览内容为字典.

        Args:
            preview: 预览内容
            format: 文件格式

        Returns:
            解析后的字典
        """
        import json
        import yaml

        if format == ConfigFormat.JSON:
            return json.loads(preview)
        elif format == ConfigFormat.YAML:
            return yaml.safe_load(preview) or {}
        elif format == ConfigFormat.ENV:
            result = {}
            for line in preview.strip().split("\n"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    result[key] = value
            return result
        else:
            return {"content": preview}

    def format_diff_table(
        self,
        results: List[DiffResult],
        title: str = "差异对比",
    ) -> Table:
        """格式化差异结果为表格.

        Args:
            results: 差异结果列表
            title: 表格标题

        Returns:
            Rich 表格对象
        """
        table = Table(title=title)
        table.add_column("路径", style="cyan")
        table.add_column("类型", style="magenta")
        table.add_column("原值", style="red")
        table.add_column("新值", style="green")

        type_styles = {
            DiffType.ADDED: "[green]新增[/green]",
            DiffType.REMOVED: "[red]删除[/red]",
            DiffType.MODIFIED: "[yellow]修改[/yellow]",
        }

        for result in results:
            old_val = str(result.old_value) if result.old_value is not None else ""
            new_val = str(result.new_value) if result.new_value is not None else ""

            if len(old_val) > 50:
                old_val = old_val[:47] + "..."
            if len(new_val) > 50:
                new_val = new_val[:47] + "..."

            table.add_row(
                result.path,
                type_styles.get(result.diff_type, result.diff_type.value),
                old_val,
                new_val,
            )

        return table

    def format_diff_summary(
        self,
        results: Dict[str, List[DiffResult]],
    ) -> Table:
        """格式化差异摘要.

        Args:
            results: 差异结果字典

        Returns:
            Rich 表格对象
        """
        table = Table(title="环境差异摘要")
        table.add_column("类别", style="cyan")
        table.add_column("新增", style="green")
        table.add_column("删除", style="red")
        table.add_column("修改", style="yellow")
        table.add_column("总计", style="white")

        for category, diffs in results.items():
            added = sum(1 for d in diffs if d.diff_type == DiffType.ADDED)
            removed = sum(1 for d in diffs if d.diff_type == DiffType.REMOVED)
            modified = sum(1 for d in diffs if d.diff_type == DiffType.MODIFIED)
            total = len(diffs)

            table.add_row(
                category,
                str(added),
                str(removed),
                str(modified),
                str(total),
            )

        return table
