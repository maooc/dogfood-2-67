"""Snapshot management commands."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from ..core import (
    ConfigManager,
)

app = typer.Typer(help="Snapshot management commands")
console = Console()


def get_config_manager() -> ConfigManager:
    """Get a ConfigManager instance."""
    return ConfigManager()


@app.command("create")
def create(
    name: str = typer.Argument(..., help="Name of the snapshot"),
    description: Optional[str] = typer.Option(None, help="Description of the snapshot"),
):
    """Create a snapshot of all environments."""
    config_manager = get_config_manager()

    environments = config_manager.list_environments()
    if not environments:
        console.print("[yellow]No environments to snapshot[/yellow]")
        raise typer.Exit(1)

    snapshot = config_manager.create_snapshot(name, description)
    console.print(
        f"[green]Created snapshot '{name}' with ID: {snapshot.id}[/green]"
    )
    console.print(f"[green]Environments included: {', '.join(snapshot.environments)}[/green]")


@app.command("list")
def list_snapshots(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
):
    """List all snapshots."""
    config_manager = get_config_manager()
    snapshots = config_manager.list_snapshots()

    if not snapshots:
        console.print("[yellow]No snapshots found[/yellow]")
        return

    table = Table(title="Snapshots")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="magenta")
    table.add_column("Environments")
    table.add_column("Timestamp")
    if verbose:
        table.add_column("Description")

    for snapshot in snapshots:
        timestamp = snapshot.timestamp.split("T")[0] if snapshot.timestamp else "N/A"
        row = [
            snapshot.id,
            snapshot.name,
            str(len(snapshot.environments)),
            timestamp,
        ]
        if verbose:
            row.append(snapshot.description or "-")
        table.add_row(*row)

    console.print(table)


@app.command("show")
def show(
    snapshot_id: str = typer.Argument(..., help="ID of the snapshot"),
):
    """Show snapshot details."""
    config_manager = get_config_manager()

    snapshot = config_manager.load_snapshot(snapshot_id)
    if not snapshot:
        console.print(f"[red]Snapshot '{snapshot_id}' not found[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Snapshot: {snapshot.name}[/bold]")
    console.print(f"ID: {snapshot.id}")
    console.print(f"Timestamp: {snapshot.timestamp}")
    console.print(f"Description: {snapshot.description or 'None'}")
    console.print(f"Environments ({len(snapshot.environments)}):")
    for env_name in sorted(snapshot.environments):
        console.print(f"  - {env_name}")


@app.command("restore")
def restore(
    snapshot_id: str = typer.Argument(..., help="ID of the snapshot"),
    force: bool = typer.Option(False, "--force", "-f", help="Force restore without confirmation"),
):
    """Restore environments from a snapshot."""
    config_manager = get_config_manager()

    snapshot = config_manager.load_snapshot(snapshot_id)
    if not snapshot:
        console.print(f"[red]Snapshot '{snapshot_id}' not found[/red]")
        raise typer.Exit(1)

    # Warn about existing environments being overwritten
    existing_envs = config_manager.list_environments()
    if existing_envs and not force:
        console.print("[yellow]Warning: This will overwrite all existing environments![/yellow]")
        console.print(f"Environments to be restored: {', '.join(snapshot.environments)}")
        if existing_envs:
            console.print(f"Environments to be overwritten: {', '.join(existing_envs)}")
        confirm = typer.confirm("Are you sure you want to proceed?")
        if not confirm:
            console.print("[yellow]Restore cancelled[/yellow]")
            raise typer.Exit()

    if config_manager.restore_snapshot(snapshot_id):
        console.print(
            f"[green]Restored snapshot '{snapshot.name}' ({snapshot_id})[/green]"
        )
        console.print(f"[green]Environments restored: {', '.join(snapshot.environments)}[/green]")
    else:
        console.print(f"[red]Failed to restore snapshot '{snapshot_id}'[/red]")
        raise typer.Exit(1)


@app.command("delete")
def delete(
    snapshot_id: str = typer.Argument(..., help="ID of the snapshot"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation"),
):
    """Delete a snapshot."""
    config_manager = get_config_manager()

    snapshot = config_manager.load_snapshot(snapshot_id)
    if not snapshot:
        console.print(f"[red]Snapshot '{snapshot_id}' not found[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete snapshot '{snapshot.name}' ({snapshot_id})?")
        if not confirm:
            console.print("[yellow]Deletion cancelled[/yellow]")
            raise typer.Exit()

    if config_manager.delete_snapshot(snapshot_id):
        console.print(
            f"[green]Deleted snapshot '{snapshot.name}' ({snapshot_id})[/green]"
        )
    else:
        console.print(f"[red]Failed to delete snapshot '{snapshot_id}'[/red]")
        raise typer.Exit(1)


@app.command("export")
def export(
    snapshot_id: str = typer.Argument(..., help="ID of the snapshot"),
    output_dir: Path = typer.Argument(..., help="Output directory"),
    format: str = typer.Option("json", help="Output format (json, yaml, env)"),
    decrypt: bool = typer.Option(True, help="Decrypt sensitive values"),
):
    """Export all environments from a snapshot to files."""
    config_manager = get_config_manager()
    from ..core import EncryptionManager, ConfigFileHandler

    snapshot = config_manager.load_snapshot(snapshot_id)
    if not snapshot:
        console.print(f"[red]Snapshot '{snapshot_id}' not found[/red]")
        raise typer.Exit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    encryption_manager = EncryptionManager()

    # Temporarily restore snapshot to read environments
    # Create a temporary config manager for the snapshot
    snapshot_data_dir = config_manager.get_snapshot_data_path(snapshot_id)
    temp_config_manager = ConfigManager(base_dir=snapshot_data_dir.parent)
    temp_config_manager.environments_dir = snapshot_data_dir

    exported = []
    for env_name in snapshot.environments:
        env = temp_config_manager.load_environment(env_name)
        if env:
            # Prepare output data
            output_data = {}
            for var in env.variables.values():
                value = var.value
                if decrypt and var.encrypted:
                    value = encryption_manager.decrypt(value)
                output_data[var.name] = value

            # Write to file
            output_file = output_dir / f"{env_name}.{format}"
            try:
                ConfigFileHandler.write_file(output_file, output_data)
                exported.append(env_name)
            except Exception as e:
                console.print(f"[red]Error exporting environment '{env_name}': {e}[/red]")

    if exported:
        console.print(
            f"[green]Exported {len(exported)} environments from snapshot '{snapshot_id}' to '{output_dir}'[/green]"
        )
    else:
        console.print("[yellow]No environments were exported[/yellow]")


if __name__ == "__main__":
    app()
