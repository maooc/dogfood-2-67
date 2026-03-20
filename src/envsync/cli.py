"""envsync CLI main entry point."""

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .commands.env_commands import app as env_app
from .commands.template_commands import app as template_app
from .commands.snapshot_commands import app as snapshot_app
from .commands.diff_commands import app as diff_app
from .core import ConfigManager, EncryptionManager

app = typer.Typer(
    name="envsync",
    help="Manage multi-environment configuration files with ease",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()

# Add subcommands
app.add_typer(env_app, name="env", help="Environment management commands")
app.add_typer(template_app, name="template", help="Template management commands")
app.add_typer(snapshot_app, name="snapshot", help="Snapshot management commands")
app.add_typer(diff_app, name="diff", help="Environment diff commands")


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        console.print(f"envsync v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """
    envsync - Manage multi-environment configuration files with ease.

    Features:
    - Manage multiple environments (dev, staging, prod)
    - Encrypt sensitive configuration values
    - Validate configurations against templates
    - Compare environments and track changes
    - Create snapshots and roll back
    - Render templates with variable substitution
    """
    pass


@app.command("init")
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configuration"),
):
    """Initialize envsync configuration."""
    config_manager = ConfigManager()
    encryption_manager = EncryptionManager()

    # Check if already initialized
    if (
        config_manager.base_dir.exists()
        and list(config_manager.base_dir.iterdir())
        and not force
    ):
        console.print(
            "[yellow]envsync is already initialized. Use --force to reinitialize.[/yellow]"
        )
        raise typer.Exit()

    # Create default template
    from .commands.template_commands import init_default
    init_default.callback(force=True)

    console.print("[green]envsync initialized successfully![/green]")
    console.print(f"[green]Configuration directory: {config_manager.base_dir}[/green]")


@app.command("status")
def status():
    """Show current status summary."""
    config_manager = ConfigManager()

    environments = config_manager.list_environments()
    templates = config_manager.list_templates()
    snapshots = config_manager.list_snapshots()

    table = Table(title="envsync Status")
    table.add_column("Category", style="cyan")
    table.add_column("Count")
    table.add_column("Items")

    table.add_row(
        "Environments",
        str(len(environments)),
        ", ".join(environments[:5]) + ("..." if len(environments) > 5 else ""),
    )
    table.add_row(
        "Templates",
        str(len(templates)),
        ", ".join(templates),
    )
    table.add_row(
        "Snapshots",
        str(len(snapshots)),
        ", ".join([s.id for s in snapshots[:3]]) + ("..." if len(snapshots) > 3 else ""),
    )

    console.print(table)


@app.command("encrypt")
def encrypt(
    value: str = typer.Argument(..., help="Value to encrypt"),
):
    """Encrypt a value using the envsync encryption key."""
    encryption_manager = EncryptionManager()
    encrypted = encryption_manager.encrypt(value)
    console.print(f"Encrypted value: {encrypted}")


@app.command("decrypt")
def decrypt(
    value: str = typer.Argument(..., help="Value to decrypt"),
):
    """Decrypt an encrypted value."""
    encryption_manager = EncryptionManager()
    if not encryption_manager.is_encrypted(value):
        console.print("[yellow]Warning: The value does not appear to be encrypted[/yellow]")

    decrypted = encryption_manager.decrypt(value)
    console.print(f"Decrypted value: {decrypted}")


@app.command("rotate-key")
def rotate_key(
    force: bool = typer.Option(False, "--force", "-f", help="Force key rotation"),
):
    """Rotate the encryption key (WARNING: Requires re-encrypting all values)."""
    config_manager = ConfigManager()
    encryption_manager = EncryptionManager()

    environments = config_manager.list_environments()
    encrypted_vars = []

    # Check for encrypted variables
    for env_name in environments:
        env = config_manager.load_environment(env_name)
        if env:
            for var in env.variables.values():
                if var.encrypted:
                    encrypted_vars.append((env_name, var.name))

    if encrypted_vars and not force:
        console.print("[red]WARNING: Key rotation will require re-encrypting all encrypted values![/red]")
        console.print(f"[red]Affected variables: {len(encrypted_vars)}[/red]")
        for env_name, var_name in encrypted_vars[:10]:
            console.print(f"  - {env_name}.{var_name}")
        if len(encrypted_vars) > 10:
            console.print(f"  - ... and {len(encrypted_vars) - 10} more")
        confirm = typer.confirm("Are you sure you want to proceed?")
        if not confirm:
            console.print("[yellow]Key rotation cancelled[/yellow]")
            raise typer.Exit()

    # Rotate key
    encryption_manager.rotate_key()
    console.print("[green]Encryption key rotated successfully[/green]")

    if encrypted_vars:
        console.print("[yellow]Note: You must re-encrypt all existing encrypted values![/yellow]")
        console.print("[yellow]Use 'envsync env set' to update values with the new key.[/yellow]")


if __name__ == "__main__":
    app()
