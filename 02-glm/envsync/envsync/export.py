"""Configuration export module."""

import csv
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import toml
import yaml


class ExportFormat:
    """Supported export formats."""
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    ENV = "env"
    CSV = "csv"
    DOTENV = "dotenv"


class ConfigExporter:
    """Export configurations to various formats."""
    
    def __init__(
        self,
        include_metadata: bool = True,
        flatten_nested: bool = False,
        mask_sensitive: bool = False,
        sensitive_fields: Optional[List[str]] = None
    ):
        self.include_metadata = include_metadata
        self.flatten_nested = flatten_nested
        self.mask_sensitive = mask_sensitive
        self.sensitive_fields = sensitive_fields or []
    
    def _flatten_dict(
        self,
        data: Dict[str, Any],
        parent_key: str = "",
        separator: str = "_"
    ) -> Dict[str, Any]:
        """Flatten nested dictionary."""
        items = []
        
        for key, value in data.items():
            new_key = f"{parent_key}{separator}{key}" if parent_key else key
            
            if isinstance(value, dict):
                items.extend(
                    self._flatten_dict(value, new_key, separator).items()
                )
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        items.extend(
                            self._flatten_dict(
                                item, f"{new_key}{separator}{i}", separator
                            ).items()
                        )
                    else:
                        items.append((f"{new_key}{separator}{i}", item))
            else:
                items.append((new_key, value))
        
        return dict(items)
    
    def _mask_sensitive_data(
        self,
        data: Dict[str, Any],
        mask: str = "******"
    ) -> Dict[str, Any]:
        """Mask sensitive fields in data."""
        import fnmatch
        
        result = data.copy()
        
        def mask_recursive(d: Dict[str, Any], path: str = "") -> None:
            for key, value in d.items():
                current_path = f"{path}.{key}" if path else key
                
                is_sensitive = False
                for pattern in self.sensitive_fields:
                    if fnmatch.fnmatch(key.lower(), pattern.lower()):
                        is_sensitive = True
                        break
                
                if is_sensitive and isinstance(value, str):
                    d[key] = mask
                elif isinstance(value, dict):
                    mask_recursive(value, current_path)
        
        mask_recursive(result)
        return result
    
    def _add_metadata(
        self,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add metadata to exported data."""
        if not self.include_metadata:
            return data
        
        result = {
            "_metadata": {
                "exported_at": datetime.now().isoformat(),
                "exporter": "envsync",
                "version": "0.1.0",
            }
        }
        
        if metadata:
            result["_metadata"].update(metadata)
        
        result.update(data)
        return result
    
    def export_to_json(
        self,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        indent: int = 2
    ) -> str:
        """Export configuration to JSON format."""
        if self.mask_sensitive:
            data = self._mask_sensitive_data(data)
        
        if self.flatten_nested:
            data = self._flatten_dict(data)
        
        data = self._add_metadata(data, metadata)
        
        return json.dumps(data, indent=indent, ensure_ascii=False)
    
    def export_to_yaml(
        self,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Export configuration to YAML format."""
        if self.mask_sensitive:
            data = self._mask_sensitive_data(data)
        
        if self.flatten_nested:
            data = self._flatten_dict(data)
        
        data = self._add_metadata(data, metadata)
        
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)
    
    def export_to_toml(
        self,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Export configuration to TOML format."""
        if self.mask_sensitive:
            data = self._mask_sensitive_data(data)
        
        if self.flatten_nested:
            data = self._flatten_dict(data)
        
        data = self._add_metadata(data, metadata)
        
        return toml.dumps(data)
    
    def export_to_env(
        self,
        data: Dict[str, Any],
        prefix: Optional[str] = None,
        uppercase_keys: bool = True
    ) -> str:
        """Export configuration to .env format."""
        if self.mask_sensitive:
            data = self._mask_sensitive_data(data)
        
        if self.flatten_nested:
            data = self._flatten_dict(data)
        
        lines = []
        
        for key, value in data.items():
            if key.startswith("_"):
                continue
            
            env_key = key.upper() if uppercase_keys else key
            
            if prefix:
                env_key = f"{prefix}_{env_key}"
            
            if isinstance(value, str):
                if " " in value or '"' in value or "'" in value:
                    value = f'"{value}"'
            elif isinstance(value, bool):
                value = "true" if value else "false"
            elif value is None:
                value = ""
            else:
                value = str(value)
            
            lines.append(f"{env_key}={value}")
        
        return "\n".join(lines)
    
    def export_to_csv(
        self,
        data: Dict[str, Any],
        include_headers: bool = True
    ) -> str:
        """Export configuration to CSV format."""
        if self.mask_sensitive:
            data = self._mask_sensitive_data(data)
        
        if not self.flatten_nested:
            data = self._flatten_dict(data)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        if include_headers:
            writer.writerow(["key", "value", "type"])
        
        for key, value in data.items():
            if key.startswith("_"):
                continue
            
            value_type = type(value).__name__
            
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            elif value is None:
                value = ""
            else:
                value = str(value)
            
            writer.writerow([key, value, value_type])
        
        return output.getvalue()
    
    def export(
        self,
        data: Dict[str, Any],
        format: str,
        metadata: Optional[Dict[str, Any]] = None,
        flatten: Optional[bool] = None,
        **kwargs
    ) -> str:
        """Export configuration to specified format."""
        if flatten is not None:
            self.flatten_nested = flatten
        
        format = format.lower()
        
        if format == ExportFormat.JSON:
            return self.export_to_json(data, metadata, **kwargs)
        elif format == ExportFormat.YAML:
            return self.export_to_yaml(data, metadata)
        elif format == ExportFormat.TOML:
            return self.export_to_toml(data, metadata)
        elif format in (ExportFormat.ENV, ExportFormat.DOTENV):
            return self.export_to_env(data, **kwargs)
        elif format == ExportFormat.CSV:
            return self.export_to_csv(data, **kwargs)
        else:
            raise ValueError(f"Unsupported export format: {format}")


class MultiEnvironmentExporter:
    """Export multiple environment configurations."""
    
    def __init__(
        self,
        include_metadata: bool = True,
        mask_sensitive: bool = False,
        sensitive_fields: Optional[List[str]] = None
    ):
        self.exporter = ConfigExporter(
            include_metadata=include_metadata,
            mask_sensitive=mask_sensitive,
            sensitive_fields=sensitive_fields
        )
    
    def export_to_directory(
        self,
        environments: Dict[str, Dict[str, Any]],
        output_dir: Path,
        format: str = "json",
        filename_pattern: str = "{environment}.{format}",
        flatten: bool = False
    ) -> List[Path]:
        """Export multiple environments to a directory."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        exported_files = []
        
        for env_name, env_data in environments.items():
            filename = filename_pattern.format(
                environment=env_name,
                format=format
            )
            
            file_path = output_dir / filename
            
            content = self.exporter.export(
                env_data,
                format,
                metadata={"environment": env_name},
                flatten=flatten
            )
            
            file_path.write_text(content, encoding="utf-8")
            exported_files.append(file_path)
        
        return exported_files
    
    def export_to_archive(
        self,
        environments: Dict[str, Dict[str, Any]],
        output_path: Path,
        format: str = "json",
        include_summary: bool = True
    ) -> Path:
        """Export multiple environments to a ZIP archive."""
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for env_name, env_data in environments.items():
                content = self.exporter.export(
                    env_data,
                    format,
                    metadata={"environment": env_name}
                )
                
                ext = format if format != "dotenv" else "env"
                zf.writestr(f"{env_name}.{ext}", content)
            
            if include_summary:
                summary = {
                    "exported_at": datetime.now().isoformat(),
                    "environments": list(environments.keys()),
                    "format": format,
                    "total_environments": len(environments),
                }
                zf.writestr(
                    "_summary.json",
                    json.dumps(summary, indent=2)
                )
        
        return output_path
    
    def export_combined(
        self,
        environments: Dict[str, Dict[str, Any]],
        format: str = "json"
    ) -> str:
        """Export all environments to a single file."""
        combined = {
            "_metadata": {
                "exported_at": datetime.now().isoformat(),
                "total_environments": len(environments),
            },
            "environments": environments,
        }
        
        if format == "json":
            return json.dumps(combined, indent=2, ensure_ascii=False)
        elif format == "yaml":
            return yaml.dump(combined, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"Unsupported format for combined export: {format}")
    
    def export_diff_report(
        self,
        diff_data: Dict[str, Any],
        format: str = "json"
    ) -> str:
        """Export diff report."""
        report = {
            "_metadata": {
                "exported_at": datetime.now().isoformat(),
                "report_type": "diff",
            },
            **diff_data,
        }
        
        if format == "json":
            return json.dumps(report, indent=2, ensure_ascii=False)
        elif format == "yaml":
            return yaml.dump(report, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"Unsupported format for diff report: {format}")


class ExportService:
    """High-level export service."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.exports_dir = project_root / ".envsync" / "exports"
        self.exports_dir.mkdir(parents=True, exist_ok=True)
    
    def export_environment(
        self,
        environment: str,
        data: Dict[str, Any],
        format: str,
        output_path: Optional[Path] = None,
        mask_sensitive: bool = False,
        sensitive_fields: Optional[List[str]] = None,
        flatten: bool = False
    ) -> Path:
        """Export a single environment configuration."""
        exporter = ConfigExporter(
            mask_sensitive=mask_sensitive,
            sensitive_fields=sensitive_fields,
            flatten_nested=flatten
        )
        
        content = exporter.export(
            data,
            format,
            metadata={"environment": environment}
        )
        
        if output_path is None:
            ext = format if format != "dotenv" else "env"
            output_path = self.exports_dir / f"{environment}.{ext}"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        
        return output_path
    
    def export_all_environments(
        self,
        environments: Dict[str, Dict[str, Any]],
        format: str = "json",
        output_dir: Optional[Path] = None,
        mask_sensitive: bool = False,
        sensitive_fields: Optional[List[str]] = None,
        flatten: bool = False
    ) -> List[Path]:
        """Export all environment configurations."""
        output_dir = output_dir or self.exports_dir
        
        exporter = MultiEnvironmentExporter(
            mask_sensitive=mask_sensitive,
            sensitive_fields=sensitive_fields
        )
        
        return exporter.export_to_directory(
            environments,
            output_dir,
            format,
            flatten=flatten
        )
    
    def export_to_archive(
        self,
        environments: Dict[str, Dict[str, Any]],
        archive_name: str = "configurations",
        format: str = "json",
        mask_sensitive: bool = False,
        sensitive_fields: Optional[List[str]] = None
    ) -> Path:
        """Export all environments to a ZIP archive."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = self.exports_dir / f"{archive_name}_{timestamp}.zip"
        
        exporter = MultiEnvironmentExporter(
            mask_sensitive=mask_sensitive,
            sensitive_fields=sensitive_fields
        )
        
        return exporter.export_to_archive(
            environments,
            archive_path,
            format
        )
    
    def export_combined(
        self,
        environments: Dict[str, Dict[str, Any]],
        format: str = "json",
        output_path: Optional[Path] = None
    ) -> Path:
        """Export all environments to a single combined file."""
        exporter = MultiEnvironmentExporter()
        
        content = exporter.export_combined(environments, format)
        
        if output_path is None:
            ext = format
            output_path = self.exports_dir / f"all_environments.{ext}"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        
        return output_path
    
    def list_exports(self) -> List[Dict[str, Any]]:
        """List all exported files."""
        exports = []
        
        for file in self.exports_dir.iterdir():
            if file.is_file():
                stat = file.stat()
                exports.append({
                    "name": file.name,
                    "path": str(file),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
        
        exports.sort(key=lambda x: x["modified"], reverse=True)
        return exports
    
    def cleanup_exports(self, keep_count: int = 10) -> List[str]:
        """Clean up old export files."""
        exports = self.list_exports()
        
        if len(exports) <= keep_count:
            return []
        
        to_delete = exports[keep_count:]
        deleted = []
        
        for export in to_delete:
            path = Path(export["path"])
            path.unlink()
            deleted.append(export["name"])
        
        return deleted
