"""Environment diff commands."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from ..core import (
    ConfigManager,
    EnvironmentDiffer,
    DiffFormatter,
    UnifiedDiffGenerator,
    ChangeType,
)

app = typer.Typer(help="Environment diff commands")
console = Console()


def get_config_manager() -> ConfigManager:
    """Get a ConfigManager instance."""
    return ConfigManager()


@app.command("env")
def diff_env(
    env1: str = typer.Argument(..., help="First environment name (old)"),
    env2: str = typer.Argument(..., help="Second environment name (new)"),
    decrypt: bool = typer.Option(False, help="Decrypt sensitive values"),
    show_unchanged: bool = typer.Option(False, help="Show unchanged variables"),
    format: str = typer.Option("detailed", help="Output format (detailed, summary, unified, json)"),
    output: Optional[Path] = typer.Option(None, help="Output file path"),
):
    """Compare two environments."""
    config_manager = get_config_manager()
    from ..core import EncryptionManager

    encryption_manager = EncryptionManager()
    differ = EnvironmentDiffer(encryption_manager)

    # Load environments
    env1_obj = config_manager.load_environment(env1)
    env2_obj = config_manager.load_environment(env2)

    if not env1_obj:
        console.print(f"[red]Environment '{env1}' not found[/red]")
        raise typer.Exit(1)
    if not env2_obj:
        console.print(f"[red]Environment '{env2}' not found[/red]")
        raise typer.Exit(1)

    # Compare
    diff = differ.compare(env1_obj, env2_obj, decrypt=decrypt, show_unchanged=show_unchanged)

    # Format output
    output_content = ""
    if format == "detailed":
        output_content = DiffFormatter.format_detailed(diff)
        console.print(output_content)
    elif format == "summary":
        output_content = DiffFormatter.format_summary(diff)
        console.print(output_content)
    elif format == "unified":
        output_content = UnifiedDiffGenerator.generate(diff)
        console.print(output_content)
    elif format == "json":
        import json
        diff_dict = {
            "env1": diff.env1_name,
            "env2": diff.env2_name,
            "has_changes": diff.has_changes,
            "added": diff.added_count,
            "removed": diff.removed_count,
            "modified": diff.modified_count,
            "unchanged": diff.unchanged_count,
            "variables": [
                {
                    "name": v.name,
                    "change_type": v.change_type.value,
                    "old_value": v.old_value,
                    "new_value": v.new_value,
                }
                for v in diff.variables
            ],
        }
        output_content = json.dumps(diff_dict, indent=2)
        console.print(output_content)
    else:
        console.print(f"[red]Unknown format: {format}[/red]")
        raise typer.Exit(1)

    # Write to file if output specified
    if output:
        with open(output, "w") as f:
            f.write(output_content)
        console.print(f"\n[green]Diff written to '{output}'[/green]")

    # Exit with non-zero if there are changes
    if diff.has_changes:
        raise typer.Exit(1)


@app.command("file")
def diff_file(
    env: str = typer.Argument(..., help="Environment name"),
    file: Path = typer.Argument(..., help="Path to file to compare against"),
    decrypt: bool = typer.Option(False, help="Decrypt sensitive values"),
    show_unchanged: bool = typer.Option(False, help="Show unchanged variables"),
):
    """Compare an environment to a file."""
    config_manager = get_config_manager()
    from ..core import EncryptionManager, ConfigFileHandler, Environment, ConfigVariable
    from datetime import datetime

    encryption_manager = EncryptionManager()
    differ = EnvironmentDiffer(encryption_manager)

    # Load environment
    env_obj = config_manager.load_environment(env)
    if not env_obj:
        console.print(f"[red]Environment '{env}' not found[/red]")
        raise typer.Exit(1)

    # Load file as temporary environment
    if not file.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)

    try:
        file_vars = ConfigFileHandler.read_file(file)
    except Exception as e:
        console.print(f"[red]Error reading file: {e}[/red]")
        raise typer.Exit(1)

    # Create temporary environment from file
    file_env = Environment(
        name=file.name,
        variables={
            k: ConfigVariable(name=k, value=str(v)) for k, v in file_vars.items()
        },
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )

    # Compare
    diff = differ.compare(env_obj, file_env, decrypt=decrypt, show_unchanged=show_unchanged)

    # Display results
    console.print(f"Comparing environment '{env}' with file '{file}':")
    console.print()
    console.print(DiffFormatter.format_detailed(diff))

    # Exit with non-zero if there are changes
    if diff.has_changes:
        raise typer.Exit(1)


@app.command("snapshot")
def diff_snapshot(
    env: str = typer.Argument(..., help="Environment name"),
    snapshot_id: str = typer.Argument(..., help="Snapshot ID"),
    decrypt: bool = typer.Option(False, help="Decrypt sensitive values"),
    show_unchanged: bool = typer.Option(False, help="Show unchanged variables"),
):
    """Compare an environment with its version in a snapshot."""
    config_manager = get_config_manager()
    from ..core import EncryptionManager

    encryption_manager = EncryptionManager()
    differ = EnvironmentDiffer(encryption_manager)

    # Load current environment
    current_env = config_manager.load_environment(env)
    if not current_env:
        console.print(f"[red]Environment '{env}' not found[/red]")
        raise typer.Exit(1)

    # Load snapshot environment
    snapshot_data_dir = config_manager.get_snapshot_data_path(snapshot_id)
    if not snapshot_data_dir.exists():
        console.print(f"[red]Snapshot '{snapshot_id}' not found[/red]")
        raise typer.Exit(1)

    snapshot_env_file = snapshot_data_dir / f"{env}.json"
    if not snapshot_env_file.exists():
        console.print(f"[red]Environment '{env}' not found in snapshot '{snapshot_id}'[/red]")
        raise typer.Exit(1)

    import json
    with open(snapshot_env_file, "r") as f:
        from ..core.config import Environment
        snapshot_env = Environment.from_dict(json.load(f))

    # Compare
    diff = differ.compare(snapshot_env, current_env, decrypt=decrypt, show_unchanged=show_unchanged)

    # Display results
    console.print(f"Comparing snapshot '{snapshot_id}' of '{env}' with current state:")
    console.print()
    console.print(DiffFormatter.format_detailed(diff))

    # Exit with non-zero if there are changes
    if diff.has_changes:
        raise typer.Exit(1)


@app.command("template")
def diff_template(
    env: str = typer.Argument(..., help="Environment name"),
    template: str = typer.Argument("default", help="Template name"),
):
    """Compare an environment with a template to see missing variables."""
    config_manager = get_config_manager()
    from ..core import EnvironmentDiffer

    differ = EnvironmentDiffer()

    # Load environment and template
    env_obj = config_manager.load_environment(env)
    template_obj = config_manager.load_template(template)

    if not env_obj:
        console.print(f"[red]Environment '{env}' not found[/red]")
        raise typer.Exit(1)
    if not template_obj:
        console.print(f"[red]Template '{template}' not found[/red]")
        raise typer.Exit(1)

    # Compare with template
    missing_required, extra, missing_optional = differ.compare_to_template(
        env_obj, template_obj
    )

    # Display results
    console.print(f"Comparing environment '{env}' with template '{template}':")
    console.print()

    if missing_required:
        console.print("[red]Missing required variables:[/red]")
        for var in missing_required:
            console.print(f"  [red]- {var}[/red]")
        console.print()

    if missing_optional:
        console.print("[yellow]Missing optional variables:[/yellow]")
        for var in missing_optional:
            console.print(f"  [yellow]- {var}[/yellow]")
        console.print()

    if extra:
        console.print("[cyan]Extra variables not in template:[/cyan]")
        for var in extra:
            console.print(f"  [cyan]- {var}[/cyan]")
        console.print()

    if not missing_required and not missing_optional and not extra:
        console.print("[green]Environment matches template perfectly![/green]")

    # Exit with non-zero if there are missing required variables
    if missing_required:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
