"""Main CLI entry point for envsync."""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from .config import ConfigManager, ConfigLoader, ConfigFormat
from .crypto import EncryptionService, SensitiveFieldManager, CryptoManager
from .diff import ConfigDiffer, DiffFormatter
from .export import ExportService, ExportFormat
from .snapshot import SnapshotService
from .template import TemplateManager, TemplateEngine
from .validator import ConfigValidator, ValidationRuleSet

app = typer.Typer(
    name="envsync",
    help="Multi-environment configuration file management CLI tool",
    add_completion=False,
)

console = Console()

project_app = typer.Typer(help="Project management commands")
app.add_typer(project_app, name="project")

env_app = typer.Typer(help="Environment management commands")
app.add_typer(env_app, name="env")

template_app = typer.Typer(help="Template management commands")
app.add_typer(template_app, name="template")

crypto_app = typer.Typer(help="Encryption management commands")
app.add_typer(crypto_app, name="crypto")

snapshot_app = typer.Typer(help="Snapshot management commands")
app.add_typer(snapshot_app, name="snapshot")

export_app = typer.Typer(help="Export commands")
app.add_typer(export_app, name="export")

validate_app = typer.Typer(help="Validation commands")
app.add_typer(validate_app, name="validate")


def get_config_manager() -> ConfigManager:
    """Get configuration manager instance."""
    return ConfigManager()


def get_snapshot_service() -> SnapshotService:
    """Get snapshot service instance."""
    return SnapshotService(Path.cwd())


def get_export_service() -> ExportService:
    """Get export service instance."""
    return ExportService(Path.cwd())


def get_encryption_service() -> EncryptionService:
    """Get encryption service instance."""
    return EncryptionService(Path.cwd())


@project_app.command("init")
def project_init(
    name: str = typer.Argument(..., help="Project name"),
):
    """Initialize a new envsync project."""
    manager = get_config_manager()
    
    try:
        config_file = manager.init_project(name)
        console.print(Panel(
            f"[green]Project '{name}' initialized successfully![/green]\n"
            f"Configuration file: {config_file}",
            title="Project Initialized",
            border_style="green",
        ))
    except Exception as e:
        console.print(f"[red]Error initializing project: {e}[/red]")
        raise typer.Exit(1)


@project_app.command("info")
def project_info():
    """Show project information."""
    manager = get_config_manager()
    
    try:
        config = manager.load_project_config()
        
        console.print(Panel(
            f"[bold]Project:[/bold] {config.project_name}\n"
            f"[bold]Environments:[/bold] {len(config.environments)}\n"
            f"[bold]Schema file:[/bold] {config.schema_file or 'Not set'}\n"
            f"[bold]Sensitive fields:[/bold] {len(config.sensitive_fields)}",
            title="Project Information",
            border_style="blue",
        ))
    except FileNotFoundError:
        console.print("[red]Project not initialized. Run 'envsync project init' first.[/red]")
        raise typer.Exit(1)


@env_app.command("add")
def env_add(
    name: str = typer.Argument(..., help="Environment name"),
    file: Path = typer.Argument(..., help="Configuration file path"),
    sensitive: Optional[List[str]] = typer.Option(
        None, "--sensitive", "-s", help="Sensitive field patterns"
    ),
):
    """Add a new environment configuration."""
    manager = get_config_manager()
    
    try:
        manager.load_project_config()
        env_config = manager.add_environment(name, file, sensitive)
        
        console.print(Panel(
            f"[green]Environment '{name}' added successfully![/green]\n"
            f"File: {env_config.file_path}\n"
            f"Format: {env_config.format}",
            title="Environment Added",
            border_style="green",
        ))
    except FileNotFoundError:
        console.print("[red]Project not initialized. Run 'envsync project init' first.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error adding environment: {e}[/red]")
        raise typer.Exit(1)


@env_app.command("remove")
def env_remove(
    name: str = typer.Argument(..., help="Environment name"),
):
    """Remove an environment configuration."""
    manager = get_config_manager()
    
    try:
        manager.load_project_config()
        if manager.remove_environment(name):
            console.print(f"[green]Environment '{name}' removed successfully.[/green]")
        else:
            console.print(f"[yellow]Environment '{name}' not found.[/yellow]")
    except FileNotFoundError:
        console.print("[red]Project not initialized. Run 'envsync project init' first.[/red]")
        raise typer.Exit(1)


@env_app.command("list")
def env_list():
    """List all environments."""
    manager = get_config_manager()
    
    try:
        manager.load_project_config()
        environments = manager.list_environments()
        
        if not environments:
            console.print("[yellow]No environments configured.[/yellow]")
            return
        
        table = Table(title="Environments")
        table.add_column("Name", style="cyan")
        table.add_column("File", style="green")
        table.add_column("Format", style="yellow")
        
        for name in environments:
            env_config = manager.get_environment(name)
            table.add_row(
                name,
                str(env_config.file_path),
                env_config.format
            )
        
        console.print(table)
    except FileNotFoundError:
        console.print("[red]Project not initialized. Run 'envsync project init' first.[/red]")
        raise typer.Exit(1)


@env_app.command("show")
def env_show(
    name: str = typer.Argument(..., help="Environment name"),
    decrypt: bool = typer.Option(False, "--decrypt", "-d", help="Decrypt sensitive values"),
):
    """Show environment configuration."""
    manager = get_config_manager()
    
    try:
        manager.load_project_config()
        data = manager.load_environment(name)
        
        if decrypt:
            try:
                project_config = manager.project_config
                encryption_service = get_encryption_service()
                encryption_service.load_encryption(project_config.project_name)
                data = encryption_service.decrypt_environment(data)
            except Exception:
                pass
        
        tree = Tree(f"[bold]{name}[/bold]")
        _build_tree(tree, data)
        console.print(tree)
    except FileNotFoundError:
        console.print("[red]Project not initialized. Run 'envsync project init' first.[/red]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


def _build_tree(tree: Tree, data: dict, prefix: str = ""):
    """Build a tree representation of configuration data."""
    for key, value in data.items():
        if isinstance(value, dict):
            branch = tree.add(f"[cyan]{key}[/cyan]")
            _build_tree(branch, value, f"{prefix}{key}.")
        elif isinstance(value, list):
            branch = tree.add(f"[cyan]{key}[/cyan] (list)")
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    item_branch = branch.add(f"[{i}]")
                    _build_tree(item_branch, item)
                else:
                    branch.add(f"[{i}] [green]{item}[/green]")
        else:
            tree.add(f"[cyan]{key}[/cyan]: [green]{value}[/green]")


@env_app.command("set")
def env_set(
    name: str = typer.Argument(..., help="Environment name"),
    key: str = typer.Argument(..., help="Configuration key (dot notation)"),
    value: str = typer.Argument(..., help="Configuration value"),
):
    """Set a configuration value."""
    manager = get_config_manager()
    
    try:
        manager.load_project_config()
        data = manager.load_environment(name)
        
        keys = key.split(".")
        current = data
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            parsed_value = value
        
        current[keys[-1]] = parsed_value
        
        manager.save_environment(name, data)
        console.print(f"[green]Set {key} = {parsed_value}[/green]")
    except FileNotFoundError:
        console.print("[red]Project not initialized. Run 'envsync project init' first.[/red]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@env_app.command("get")
def env_get(
    name: str = typer.Argument(..., help="Environment name"),
    key: str = typer.Argument(..., help="Configuration key (dot notation)"),
):
    """Get a configuration value."""
    manager = get_config_manager()
    
    try:
        manager.load_project_config()
        data = manager.load_environment(name)
        
        keys = key.split(".")
        current = data
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                console.print(f"[yellow]Key '{key}' not found.[/yellow]")
                raise typer.Exit(1)
        
        if isinstance(current, dict):
            console.print_json(json.dumps(current, indent=2))
        else:
            console.print(f"[green]{current}[/green]")
    except FileNotFoundError:
        console.print("[red]Project not initialized. Run 'envsync project init' first.[/red]")
        raise typer.Exit(1)


@app.command("diff")
def diff_configs(
    source: str = typer.Argument(..., help="Source environment name"),
    target: str = typer.Argument(..., help="Target environment name"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, unified"),
    ignore: Optional[List[str]] = typer.Option(None, "--ignore", "-i", help="Fields to ignore"),
):
    """Compare two environment configurations."""
    manager = get_config_manager()
    
    try:
        manager.load_project_config()
        source_data = manager.load_environment(source)
        target_data = manager.load_environment(target)
        
        differ = ConfigDiffer(ignore_fields=ignore)
        result = differ.compare(source_data, target_data, source, target)
        
        if format == "json":
            console.print_json(json.dumps(result.to_dict(), indent=2))
        elif format == "unified":
            console.print(DiffFormatter.format_unified(result))
        else:
            console.print(DiffFormatter.format_table(result))
    except FileNotFoundError:
        console.print("[red]Project not initialized. Run 'envsync project init' first.[/red]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@template_app.command("list")
def template_list():
    """List all templates."""
    manager = TemplateManager()
    templates = manager.list_templates()
    
    if not templates:
        console.print("[yellow]No templates found.[/yellow]")
        return
    
    table = Table(title="Templates")
    table.add_column("Name", style="cyan")
    
    for name in templates:
        table.add_row(name)
    
    console.print(table)


@template_app.command("apply")
def template_apply(
    name: str = typer.Argument(..., help="Template name"),
    environment: str = typer.Argument(..., help="Target environment"),
    vars_file: Optional[Path] = typer.Option(None, "--vars", "-v", help="Variables file"),
    strict: bool = typer.Option(False, "--strict", help="Fail on undefined variables"),
):
    """Apply a template to an environment."""
    manager = get_config_manager()
    template_manager = TemplateManager()
    
    try:
        manager.load_project_config()
        
        variables = {}
        if vars_file:
            engine = TemplateEngine(strict=strict)
            engine.load_from_file(vars_file)
            variables = engine.variables
        
        output_path = template_manager.apply_template_to_environment(
            name, environment, variables
        )
        
        console.print(f"[green]Template '{name}' applied to environment '{environment}'[/green]")
        console.print(f"Output: {output_path}")
    except FileNotFoundError:
        console.print("[red]Project not initialized or template not found.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error applying template: {e}[/red]")
        raise typer.Exit(1)


@template_app.command("render")
def template_render(
    name: str = typer.Argument(..., help="Template name"),
    vars_file: Optional[Path] = typer.Option(None, "--vars", "-v", help="Variables file"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
    strict: bool = typer.Option(False, "--strict", help="Fail on undefined variables"),
):
    """Render a template and display or save the result."""
    template_manager = TemplateManager()
    
    try:
        variables = {}
        if vars_file:
            engine = TemplateEngine(strict=strict)
            engine.load_from_file(vars_file)
            variables = engine.variables
        
        result = template_manager.render_template(name, variables, strict=strict)
        
        if output:
            import yaml
            output.write_text(yaml.dump(result, default_flow_style=False), encoding="utf-8")
            console.print(f"[green]Rendered template saved to {output}[/green]")
        else:
            console.print_json(json.dumps(result, indent=2))
    except FileNotFoundError as e:
        console.print(f"[red]Template not found: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error rendering template: {e}[/red]")
        raise typer.Exit(1)


@crypto_app.command("init")
def crypto_init(
    password: Optional[str] = typer.Option(None, "--password", "-p", help="Encryption password"),
):
    """Initialize encryption for the project."""
    manager = get_config_manager()
    encryption_service = get_encryption_service()
    
    try:
        config = manager.load_project_config()
        
        if password is None:
            password = typer.prompt("Enter encryption password", hide_input=True)
        
        key = encryption_service.initialize(config.project_name, password)
        
        console.print("[green]Encryption initialized successfully![/green]")
        console.print(f"[dim]Key stored securely for project: {config.project_name}[/dim]")
    except FileNotFoundError:
        console.print("[red]Project not initialized. Run 'envsync project init' first.[/red]")
        raise typer.Exit(1)


@crypto_app.command("encrypt")
def crypto_encrypt(
    environment: str = typer.Argument(..., help="Environment name"),
    fields: Optional[List[str]] = typer.Option(None, "--field", "-f", help="Fields to encrypt"),
):
    """Encrypt sensitive fields in an environment."""
    manager = get_config_manager()
    encryption_service = get_encryption_service()
    
    try:
        config = manager.load_project_config()
        encryption_service.load_encryption(config.project_name)
        
        data = manager.load_environment(environment)
        encrypted_data, encrypted_fields = encryption_service.encrypt_environment(data, fields)
        
        manager.save_environment(environment, encrypted_data)
        
        console.print(f"[green]Encrypted {len(encrypted_fields)} fields in '{environment}'[/green]")
        for field in encrypted_fields:
            console.print(f"  - {field}")
    except FileNotFoundError:
        console.print("[red]Project not initialized or encryption not initialized.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error encrypting: {e}[/red]")
        raise typer.Exit(1)


@crypto_app.command("decrypt")
def crypto_decrypt(
    environment: str = typer.Argument(..., help="Environment name"),
    fields: Optional[List[str]] = typer.Option(None, "--field", "-f", help="Fields to decrypt"),
):
    """Decrypt sensitive fields in an environment."""
    manager = get_config_manager()
    encryption_service = get_encryption_service()
    
    try:
        config = manager.load_project_config()
        encryption_service.load_encryption(config.project_name)
        
        data = manager.load_environment(environment)
        decrypted_data = encryption_service.decrypt_environment(data, fields)
        
        manager.save_environment(environment, decrypted_data)
        
        console.print(f"[green]Decrypted fields in '{environment}'[/green]")
    except FileNotFoundError:
        console.print("[red]Project not initialized or encryption not initialized.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error decrypting: {e}[/red]")
        raise typer.Exit(1)


@crypto_app.command("rotate")
def crypto_rotate():
    """Rotate encryption key."""
    manager = get_config_manager()
    encryption_service = get_encryption_service()
    
    try:
        config = manager.load_project_config()
        encryption_service.load_encryption(config.project_name)
        
        if not typer.confirm("This will re-encrypt all configurations with a new key. Continue?"):
            raise typer.Abort()
        
        new_key = encryption_service.rotate_key(config.project_name)
        
        console.print("[green]Encryption key rotated successfully![/green]")
    except FileNotFoundError:
        console.print("[red]Project not initialized or encryption not initialized.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error rotating key: {e}[/red]")
        raise typer.Exit(1)


@snapshot_app.command("create")
def snapshot_create(
    environment: str = typer.Argument(..., help="Environment name"),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Snapshot message"),
    tags: Optional[List[str]] = typer.Option(None, "--tag", "-t", help="Tags for the snapshot"),
):
    """Create a snapshot of an environment configuration."""
    manager = get_config_manager()
    snapshot_service = get_snapshot_service()
    
    try:
        manager.load_project_config()
        data = manager.load_environment(environment)
        
        snapshot = snapshot_service.create_snapshot(
            environment=environment,
            data=data,
            message=message,
            tags=tags
        )
        
        console.print(f"[green]Snapshot created: {snapshot.id}[/green]")
        console.print(f"Environment: {environment}")
        console.print(f"Checksum: {snapshot.checksum}")
    except FileNotFoundError:
        console.print("[red]Project not initialized. Run 'envsync project init' first.[/red]")
        raise typer.Exit(1)


@snapshot_app.command("list")
def snapshot_list(
    environment: Optional[str] = typer.Argument(None, help="Environment name (optional)"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of snapshots"),
    tags: Optional[List[str]] = typer.Option(None, "--tag", "-t", help="Filter by tags"),
):
    """List snapshots."""
    snapshot_service = get_snapshot_service()
    
    try:
        snapshots = snapshot_service.list_snapshots(
            environment=environment,
            limit=limit,
            tags=tags
        )
        
        if not snapshots:
            console.print("[yellow]No snapshots found.[/yellow]")
            return
        
        table = Table(title="Snapshots")
        table.add_column("ID", style="cyan")
        table.add_column("Environment", style="green")
        table.add_column("Timestamp", style="yellow")
        table.add_column("Message", style="white")
        table.add_column("Tags", style="magenta")
        
        for snapshot in snapshots:
            table.add_row(
                snapshot["id"],
                snapshot["environment"],
                snapshot["timestamp"],
                snapshot.get("message", ""),
                ", ".join(snapshot.get("tags", []))
            )
        
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error listing snapshots: {e}[/red]")
        raise typer.Exit(1)


@snapshot_app.command("restore")
def snapshot_restore(
    snapshot_id: str = typer.Argument(..., help="Snapshot ID"),
    preview: bool = typer.Option(False, "--preview", "-p", help="Preview without applying"),
):
    """Restore configuration from a snapshot."""
    manager = get_config_manager()
    snapshot_service = get_snapshot_service()
    
    try:
        manager.load_project_config()
        
        if preview:
            preview_data = snapshot_service.snapshot_manager.get_snapshot(snapshot_id)
            if preview_data:
                console.print_json(json.dumps(preview_data.data, indent=2))
            else:
                console.print(f"[red]Snapshot not found: {snapshot_id}[/red]")
                raise typer.Exit(1)
        else:
            snapshot_data = snapshot_service.get_snapshot(snapshot_id)
            
            if not snapshot_data:
                console.print(f"[red]Snapshot not found: {snapshot_id}[/red]")
                raise typer.Exit(1)
            
            env_config = manager.get_environment(snapshot_data["environment"])
            manager.save_environment(
                snapshot_data["environment"],
                snapshot_data["data"]
            )
            
            console.print(f"[green]Restored {snapshot_data['environment']} from snapshot {snapshot_id}[/green]")
    except FileNotFoundError:
        console.print("[red]Project not initialized. Run 'envsync project init' first.[/red]")
        raise typer.Exit(1)


@snapshot_app.command("delete")
def snapshot_delete(
    snapshot_id: str = typer.Argument(..., help="Snapshot ID"),
):
    """Delete a snapshot."""
    snapshot_service = get_snapshot_service()
    
    if snapshot_service.delete_snapshot(snapshot_id):
        console.print(f"[green]Snapshot {snapshot_id} deleted.[/green]")
    else:
        console.print(f"[yellow]Snapshot {snapshot_id} not found.[/yellow]")


@snapshot_app.command("cleanup")
def snapshot_cleanup(
    environment: str = typer.Argument(..., help="Environment name"),
    keep: int = typer.Option(10, "--keep", "-k", help="Number of snapshots to keep"),
):
    """Clean up old snapshots."""
    snapshot_service = get_snapshot_service()
    
    deleted = snapshot_service.cleanup(environment, keep)
    
    if deleted:
        console.print(f"[green]Deleted {len(deleted)} old snapshots[/green]")
        for snapshot_id in deleted:
            console.print(f"  - {snapshot_id}")
    else:
        console.print("[yellow]No snapshots to clean up.[/yellow]")


@export_app.command("env")
def export_env(
    environment: str = typer.Argument(..., help="Environment name"),
    format: str = typer.Option("json", "--format", "-f", help="Export format: json, yaml, toml, env, csv"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    mask_sensitive: bool = typer.Option(False, "--mask", help="Mask sensitive values"),
    flatten: bool = typer.Option(False, "--flatten", help="Flatten nested structures"),
):
    """Export an environment configuration."""
    manager = get_config_manager()
    export_service = get_export_service()
    
    try:
        config = manager.load_project_config()
        data = manager.load_environment(environment)
        
        output_path = export_service.export_environment(
            environment=environment,
            data=data,
            format=format,
            output_path=output,
            mask_sensitive=mask_sensitive,
            sensitive_fields=config.sensitive_fields,
            flatten=flatten
        )
        
        console.print(f"[green]Exported '{environment}' to {output_path}[/green]")
    except FileNotFoundError:
        console.print("[red]Project not initialized. Run 'envsync project init' first.[/red]")
        raise typer.Exit(1)


@export_app.command("all")
def export_all(
    format: str = typer.Option("json", "--format", "-f", help="Export format"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory"),
    mask_sensitive: bool = typer.Option(False, "--mask", help="Mask sensitive values"),
    flatten: bool = typer.Option(False, "--flatten", help="Flatten nested structures"),
):
    """Export all environment configurations."""
    manager = get_config_manager()
    export_service = get_export_service()
    
    try:
        config = manager.load_project_config()
        
        environments = {}
        for env_name in config.environments:
            environments[env_name] = manager.load_environment(env_name)
        
        exported_files = export_service.export_all_environments(
            environments=environments,
            format=format,
            output_dir=output_dir,
            mask_sensitive=mask_sensitive,
            sensitive_fields=config.sensitive_fields,
            flatten=flatten
        )
        
        console.print(f"[green]Exported {len(exported_files)} environments[/green]")
        for file_path in exported_files:
            console.print(f"  - {file_path}")
    except FileNotFoundError:
        console.print("[red]Project not initialized. Run 'envsync project init' first.[/red]")
        raise typer.Exit(1)


@export_app.command("archive")
def export_archive(
    format: str = typer.Option("json", "--format", "-f", help="Export format"),
    name: str = typer.Option("configurations", "--name", "-n", help="Archive name"),
    mask_sensitive: bool = typer.Option(False, "--mask", help="Mask sensitive values"),
):
    """Export all environments to a ZIP archive."""
    manager = get_config_manager()
    export_service = get_export_service()
    
    try:
        config = manager.load_project_config()
        
        environments = {}
        for env_name in config.environments:
            environments[env_name] = manager.load_environment(env_name)
        
        archive_path = export_service.export_to_archive(
            environments=environments,
            archive_name=name,
            format=format,
            mask_sensitive=mask_sensitive,
            sensitive_fields=config.sensitive_fields
        )
        
        console.print(f"[green]Created archive: {archive_path}[/green]")
    except FileNotFoundError:
        console.print("[red]Project not initialized. Run 'envsync project init' first.[/red]")
        raise typer.Exit(1)


@validate_app.command("env")
def validate_env(
    environment: str = typer.Argument(..., help="Environment name"),
    schema: Optional[Path] = typer.Option(None, "--schema", "-s", help="JSON Schema file"),
    required: Optional[List[str]] = typer.Option(None, "--required", "-r", help="Required fields"),
):
    """Validate an environment configuration."""
    manager = get_config_manager()
    
    try:
        config = manager.load_project_config()
        data = manager.load_environment(environment)
        
        validator = ConfigValidator()
        
        if schema:
            validator.add_json_schema_file(schema)
        elif config.schema_file:
            validator.add_json_schema_file(config.schema_file)
        
        if required:
            validator.add_required_fields(required)
        
        result = validator.validate(data)
        
        if result.valid:
            console.print(f"[green]✓ Configuration for '{environment}' is valid[/green]")
        else:
            console.print(f"[red]✗ Configuration for '{environment}' has errors[/red]")
            
            for error in result.errors:
                console.print(f"  [red]ERROR[/red] {error.path}: {error.message}")
            
            for warning in result.warnings:
                console.print(f"  [yellow]WARNING[/yellow] {warning.path}: {warning.message}")
        
        console.print(f"\nSummary: {len(result.errors)} errors, {len(result.warnings)} warnings")
        
        if not result.valid:
            raise typer.Exit(1)
    except FileNotFoundError:
        console.print("[red]Project not initialized. Run 'envsync project init' first.[/red]")
        raise typer.Exit(1)


@validate_app.command("file")
def validate_file(
    file: Path = typer.Argument(..., help="Configuration file path"),
    schema: Optional[Path] = typer.Option(None, "--schema", "-s", help="JSON Schema file"),
):
    """Validate a configuration file."""
    validator = ConfigValidator()
    
    if schema:
        validator.add_json_schema_file(schema)
    
    result = validator.validate_file(file)
    
    if result.valid:
        console.print(f"[green]✓ Configuration file is valid[/green]")
    else:
        console.print(f"[red]✗ Configuration file has errors[/red]")
        
        for error in result.errors:
            console.print(f"  [red]ERROR[/red] {error.path}: {error.message}")
    
    if not result.valid:
        raise typer.Exit(1)


@validate_app.command("rules")
def validate_rules(
    action: str = typer.Argument(..., help="Action: create, show"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Rule set name"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
):
    """Manage validation rule sets."""
    if action == "create":
        if not name:
            console.print("[red]Please provide a name for the rule set.[/red]")
            raise typer.Exit(1)
        
        rule_set = ValidationRuleSet(
            name=name,
            description="Custom validation rules"
        )
        
        if output:
            rule_set.save(output)
            console.print(f"[green]Created rule set: {output}[/green]")
        else:
            console.print_json(json.dumps(rule_set.model_dump(), indent=2))
    else:
        console.print("[yellow]Unknown action. Use 'create' to create a new rule set.[/yellow]")


@app.command("version")
def show_version():
    """Show version information."""
    from . import __version__
    console.print(f"envsync version {__version__}")


if __name__ == "__main__":
    app()
