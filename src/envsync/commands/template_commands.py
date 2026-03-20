"""Template management commands."""

from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import typer
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax
import json

from ..core import (
    ConfigManager,
    Template,
    ConfigFileHandler,
)

app = typer.Typer(help="Template management commands")
console = Console()


def get_config_manager() -> ConfigManager:
    """Get a ConfigManager instance."""
    return ConfigManager()


@app.command("create")
def create(
    name: str = typer.Argument(..., help="Name of the template"),
    description: Optional[str] = typer.Option(None, help="Description of the template"),
    from_file: Optional[Path] = typer.Option(None, help="Import template from JSON file"),
):
    """Create a new template."""
    config_manager = get_config_manager()

    if config_manager.template_exists(name):
        console.print(f"[red]Template '{name}' already exists[/red]")
        raise typer.Exit(1)

    if from_file:
        if not from_file.exists():
            console.print(f"[red]File not found: {from_file}[/red]")
            raise typer.Exit(1)
        try:
            template_data = ConfigFileHandler.read_file(from_file)
        except Exception as e:
            console.print(f"[red]Error reading file: {e}[/red]")
            raise typer.Exit(1)

        # Create template from file data
        template = Template(
            name=name,
            description=description or template_data.get("description"),
            variables=template_data.get("variables", {}),
            required=template_data.get("required", []),
            sensitive=template_data.get("sensitive", []),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
    else:
        # Create empty template with default structure
        template = Template(
            name=name,
            description=description,
            variables={
                "DATABASE_URL": {
                    "type": "url",
                    "description": "Database connection URL",
                },
                "API_KEY": {
                    "type": "string",
                    "description": "API key for external service",
                },
                "DEBUG": {
                    "type": "bool",
                    "description": "Enable debug mode",
                    "default": "false",
                },
                "PORT": {
                    "type": "int",
                    "description": "Port to listen on",
                    "default": "8000",
                },
            },
            required=["DATABASE_URL", "API_KEY"],
            sensitive=["API_KEY", "DATABASE_URL"],
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

    config_manager.save_template(template)
    console.print(f"[green]Created template '{name}'[/green]")


@app.command("list")
def list_templates(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
):
    """List all templates."""
    config_manager = get_config_manager()
    templates = config_manager.list_templates()

    if not templates:
        console.print("[yellow]No templates found[/yellow]")
        return

    table = Table(title="Templates")
    table.add_column("Name", style="cyan")
    table.add_column("Variables")
    table.add_column("Required")
    table.add_column("Sensitive")
    table.add_column("Created")
    if verbose:
        table.add_column("Description")

    for template_name in sorted(templates):
        template = config_manager.load_template(template_name)
        if template:
            created = template.created_at.split("T")[0] if template.created_at else "N/A"
            row = [
                template.name,
                str(len(template.variables)),
                str(len(template.required)),
                str(len(template.sensitive)),
                created,
            ]
            if verbose:
                row.append(template.description or "-")
            table.add_row(*row)

    console.print(table)


@app.command("show")
def show(
    name: str = typer.Argument(..., help="Name of the template"),
    format: str = typer.Option("table", help="Output format (table, json, yaml)"),
):
    """Show template details."""
    config_manager = get_config_manager()

    template = config_manager.load_template(name)
    if not template:
        console.print(f"[red]Template '{name}' not found[/red]")
        raise typer.Exit(1)

    if format == "table":
        # Basic info
        console.print(f"[bold]Template: {name}[/bold]")
        console.print(f"Description: {template.description or 'None'}")
        console.print(f"Created: {template.created_at}")
        console.print(f"Updated: {template.updated_at}")
        console.print()

        # Variables table
        var_table = Table(title="Variables")
        var_table.add_column("Name", style="cyan")
        var_table.add_column("Type", style="blue")
        var_table.add_column("Required", style="yellow")
        var_table.add_column("Sensitive", style="magenta")
        var_table.add_column("Default", style="green")
        var_table.add_column("Description")

        for var_name, var_schema in template.variables.items():
            var_table.add_row(
                var_name,
                var_schema.get("type", "string"),
                "✓" if var_name in template.required else "-",
                "✓" if var_name in template.sensitive else "-",
                var_schema.get("default", "-"),
                var_schema.get("description", "-"),
            )

        console.print(var_table)

    elif format == "json":
        console.print(Syntax(json.dumps(template.to_dict(), indent=2), "json"))

    elif format == "yaml":
        import yaml
        console.print(Syntax(yaml.dump(template.to_dict(), default_flow_style=False), "yaml"))

    else:
        console.print(f"[red]Unknown format: {format}[/red]")
        raise typer.Exit(1)


@app.command("delete")
def delete(
    name: str = typer.Argument(..., help="Name of the template"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation"),
):
    """Delete a template."""
    config_manager = get_config_manager()

    if not config_manager.template_exists(name):
        console.print(f"[red]Template '{name}' not found[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete template '{name}'?")
        if not confirm:
            console.print("[yellow]Deletion cancelled[/yellow]")
            raise typer.Exit()

    if config_manager.delete_template(name):
        console.print(f"[green]Deleted template '{name}'[/green]")
    else:
        console.print(f"[red]Failed to delete template '{name}'[/red]")
        raise typer.Exit(1)


@app.command("export")
def export(
    name: str = typer.Argument(..., help="Name of the template"),
    output: Optional[Path] = typer.Option(None, help="Output file path"),
    format: str = typer.Option("json", help="Output format (json, yaml)"),
):
    """Export a template to a file."""
    config_manager = get_config_manager()

    template = config_manager.load_template(name)
    if not template:
        console.print(f"[red]Template '{name}' not found[/red]")
        raise typer.Exit(1)

    template_dict = template.to_dict()

    if output:
        try:
            ConfigFileHandler.write_file(output, template_dict)
            console.print(f"[green]Exported template '{name}' to '{output}'[/green]")
        except Exception as e:
            console.print(f"[red]Error writing file: {e}[/red]")
            raise typer.Exit(1)
    else:
        if format == "json":
            console.print(Syntax(json.dumps(template_dict, indent=2), "json"))
        elif format == "yaml":
            import yaml
            console.print(Syntax(yaml.dump(template_dict, default_flow_style=False), "yaml"))
        else:
            console.print(f"[red]Unknown format: {format}[/red]")
            raise typer.Exit(1)


@app.command("add-variable")
def add_variable(
    template: str = typer.Argument(..., help="Name of the template"),
    name: str = typer.Argument(..., help="Variable name"),
    var_type: str = typer.Option("string", help="Variable type"),
    description: Optional[str] = typer.Option(None, help="Variable description"),
    required: bool = typer.Option(False, help="Mark as required"),
    sensitive: bool = typer.Option(False, help="Mark as sensitive"),
    default: Optional[str] = typer.Option(None, help="Default value"),
    pattern: Optional[str] = typer.Option(None, help="Validation pattern"),
):
    """Add a variable to a template."""
    config_manager = get_config_manager()

    template_obj = config_manager.load_template(template)
    if not template_obj:
        console.print(f"[red]Template '{template}' not found[/red]")
        raise typer.Exit(1)

    # Check if variable already exists
    if name in template_obj.variables:
        console.print(f"[yellow]Variable '{name}' already exists in template '{template}'[/yellow]")
        confirm = typer.confirm("Do you want to overwrite it?")
        if not confirm:
            console.print("[yellow]Operation cancelled[/yellow]")
            raise typer.Exit()

    # Add variable to template
    template_obj.variables[name] = {
        "type": var_type,
        "description": description,
        "default": default,
        "pattern": pattern,
    }

    # Update required and sensitive lists
    if required and name not in template_obj.required:
        template_obj.required.append(name)
    elif not required and name in template_obj.required:
        template_obj.required.remove(name)

    if sensitive and name not in template_obj.sensitive:
        template_obj.sensitive.append(name)
    elif not sensitive and name in template_obj.sensitive:
        template_obj.sensitive.remove(name)

    config_manager.save_template(template_obj)
    console.print(f"[green]Added variable '{name}' to template '{template}'[/green]")


@app.command("remove-variable")
def remove_variable(
    template: str = typer.Argument(..., help="Name of the template"),
    name: str = typer.Argument(..., help="Variable name"),
    force: bool = typer.Option(False, "--force", "-f", help="Force removal without confirmation"),
):
    """Remove a variable from a template."""
    config_manager = get_config_manager()

    template_obj = config_manager.load_template(template)
    if not template_obj:
        console.print(f"[red]Template '{template}' not found[/red]")
        raise typer.Exit(1)

    if name not in template_obj.variables:
        console.print(f"[red]Variable '{name}' not found in template '{template}'[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Are you sure you want to remove variable '{name}' from template '{template}'?")
        if not confirm:
            console.print("[yellow]Operation cancelled[/yellow]")
            raise typer.Exit()

    # Remove variable
    del template_obj.variables[name]

    # Remove from required and sensitive lists if present
    if name in template_obj.required:
        template_obj.required.remove(name)
    if name in template_obj.sensitive:
        template_obj.sensitive.remove(name)

    config_manager.save_template(template_obj)
    console.print(f"[green]Removed variable '{name}' from template '{template}'[/green]")


@app.command("init-default")
def init_default(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite if exists"),
):
    """Initialize the default template."""
    config_manager = get_config_manager()

    if config_manager.template_exists("default") and not force:
        console.print("[yellow]Default template already exists. Use --force to overwrite.[/yellow]")
        raise typer.Exit()

    # Create default template with common variables
    default_template = Template(
        name="default",
        description="Default configuration template",
        variables={
            "ENVIRONMENT": {
                "type": "string",
                "description": "Environment name (development, staging, production)",
                "default": "development",
            },
            "DEBUG": {
                "type": "bool",
                "description": "Enable debug mode",
                "default": "false",
            },
            "DATABASE_URL": {
                "type": "url",
                "description": "Database connection URL",
            },
            "DATABASE_POOL_SIZE": {
                "type": "int",
                "description": "Database connection pool size",
                "default": "10",
            },
            "REDIS_URL": {
                "type": "url",
                "description": "Redis connection URL",
            },
            "CACHE_TTL": {
                "type": "int",
                "description": "Cache TTL in seconds",
                "default": "3600",
            },
            "API_KEY": {
                "type": "string",
                "description": "API key for external services",
            },
            "API_SECRET": {
                "type": "string",
                "description": "API secret for external services",
            },
            "LOG_LEVEL": {
                "type": "string",
                "description": "Logging level",
                "default": "INFO",
            },
            "PORT": {
                "type": "int",
                "description": "Port to listen on",
                "default": "8000",
            },
            "HOST": {
                "type": "string",
                "description": "Host to bind to",
                "default": "0.0.0.0",
            },
            "SSL_ENABLED": {
                "type": "bool",
                "description": "Enable SSL/TLS",
                "default": "false",
            },
            "CORS_ORIGINS": {
                "type": "string",
                "description": "Comma-separated CORS origins",
                "default": "*",
            },
        },
        required=["DATABASE_URL", "API_KEY", "API_SECRET"],
        sensitive=["DATABASE_URL", "API_KEY", "API_SECRET", "REDIS_URL"],
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )

    config_manager.save_template(default_template)
    console.print("[green]Initialized default template[/green]")


if __name__ == "__main__":
    app()
