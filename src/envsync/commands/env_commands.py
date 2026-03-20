"""Environment management commands."""

from datetime import datetime
from pathlib import Path
from typing import Optional, List
import typer
from rich.console import Console
from rich.table import Table
from rich.syntax import Syntax

from ..core import (
    ConfigManager,
    Environment,
    ConfigVariable,
    ConfigFileHandler,
    TemplateRenderer,
    ConfigFormat,
    EncryptionManager,
    ConfigValidator,
)

app = typer.Typer(help="Environment management commands")
console = Console()


def get_config_manager() -> ConfigManager:
    """Get a ConfigManager instance."""
    return ConfigManager()


def get_encryption_manager() -> EncryptionManager:
    """Get an EncryptionManager instance."""
    return EncryptionManager()


@app.command("create")
def create(
    name: str = typer.Argument(..., help="Name of the environment"),
    description: Optional[str] = typer.Option(None, help="Description of the environment"),
    from_file: Optional[Path] = typer.Option(None, help="Import variables from file"),
    template: Optional[str] = typer.Option(None, help="Template to use for validation"),
):
    """Create a new environment."""
    config_manager = get_config_manager()

    if config_manager.environment_exists(name):
        console.print(f"[red]Environment '{name}' already exists[/red]")
        raise typer.Exit(1)

    variables = {}

    # Import from file if specified
    if from_file:
        if not from_file.exists():
            console.print(f"[red]File not found: {from_file}[/red]")
            raise typer.Exit(1)
        try:
            file_vars = ConfigFileHandler.read_file(from_file)
            variables = {
                k: ConfigVariable(name=k, value=str(v)) for k, v in file_vars.items()
            }
        except Exception as e:
            console.print(f"[red]Error reading file: {e}[/red]")
            raise typer.Exit(1)

    # Create environment
    env = Environment(
        name=name,
        description=description,
        variables=variables,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )

    config_manager.save_environment(env)
    console.print(f"[green]Created environment '{name}'[/green]")

    # Validate against template if specified
    if template:
        _validate_environment(name, template, console)


@app.command("list")
def list_envs(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
):
    """List all environments."""
    config_manager = get_config_manager()
    environments = config_manager.list_environments()

    if not environments:
        console.print("[yellow]No environments found[/yellow]")
        return

    table = Table(title="Environments")
    table.add_column("Name", style="cyan")
    table.add_column("Variables")
    table.add_column("Created")
    table.add_column("Updated")
    if verbose:
        table.add_column("Description")

    for env_name in sorted(environments):
        env = config_manager.load_environment(env_name)
        if env:
            created = env.created_at.split("T")[0] if env.created_at else "N/A"
            updated = env.updated_at.split("T")[0] if env.updated_at else "N/A"
            row = [
                env.name,
                str(len(env.variables)),
                created,
                updated,
            ]
            if verbose:
                row.append(env.description or "-")
            table.add_row(*row)

    console.print(table)


@app.command("show")
def show(
    name: str = typer.Argument(..., help="Name of the environment"),
    decrypt: bool = typer.Option(False, help="Decrypt sensitive values"),
    format: str = typer.Option("table", help="Output format (table, json, yaml, env)"),
):
    """Show environment variables."""
    config_manager = get_config_manager()
    encryption_manager = get_encryption_manager()

    env = config_manager.load_environment(name)
    if not env:
        console.print(f"[red]Environment '{name}' not found[/red]")
        raise typer.Exit(1)

    # Prepare output data
    output_data = {}
    for var in env.variables.values():
        value = var.value
        if decrypt and var.encrypted:
            value = encryption_manager.decrypt(value)
        output_data[var.name] = value

    if format == "table":
        table = Table(title=f"Environment: {name}")
        table.add_column("Name", style="cyan")
        table.add_column("Value")
        table.add_column("Encrypted", style="magenta")
        table.add_column("Type", style="blue")
        table.add_column("Required", style="yellow")

        for var in env.variables.values():
            value = var.value
            if decrypt and var.encrypted:
                value = encryption_manager.decrypt(value)
            # Truncate long values for display
            display_value = value[:50] + "..." if len(str(value)) > 50 else str(value)
            table.add_row(
                var.name,
                display_value,
                "✓" if var.encrypted else "-",
                var.type,
                "✓" if var.required else "-",
            )
        console.print(table)

    elif format == "json":
        import json
        console.print(Syntax(json.dumps(output_data, indent=2), "json"))

    elif format == "yaml":
        import yaml
        console.print(Syntax(yaml.dump(output_data, default_flow_style=False), "yaml"))

    elif format == "env":
        env_output = "\n".join([f"{k}={v}" for k, v in output_data.items()])
        console.print(env_output)

    else:
        console.print(f"[red]Unknown format: {format}[/red]")
        raise typer.Exit(1)


@app.command("set")
def set_var(
    env: str = typer.Argument(..., help="Name of the environment"),
    key: str = typer.Argument(..., help="Variable name"),
    value: str = typer.Argument(..., help="Variable value"),
    description: Optional[str] = typer.Option(None, help="Variable description"),
    encrypted: bool = typer.Option(False, help="Encrypt this value"),
    var_type: str = typer.Option("string", help="Variable type (string, int, bool, float)"),
    required: bool = typer.Option(False, help="Mark as required"),
):
    """Set an environment variable."""
    config_manager = get_config_manager()
    encryption_manager = get_encryption_manager()

    environment = config_manager.load_environment(env)
    if not environment:
        console.print(f"[red]Environment '{env}' not found[/red]")
        raise typer.Exit(1)

    # Encrypt value if requested
    stored_value = value
    if encrypted:
        stored_value = encryption_manager.encrypt(value)

    # Update or add variable
    environment.variables[key] = ConfigVariable(
        name=key,
        value=stored_value,
        description=description,
        encrypted=encrypted,
        type=var_type,
        required=required,
    )

    config_manager.save_environment(environment)
    console.print(f"[green]Set {key}={value} in environment '{env}'[/green]")


@app.command("get")
def get_var(
    env: str = typer.Argument(..., help="Name of the environment"),
    key: str = typer.Argument(..., help="Variable name"),
    decrypt: bool = typer.Option(True, help="Decrypt sensitive values"),
):
    """Get an environment variable."""
    config_manager = get_config_manager()
    encryption_manager = get_encryption_manager()

    environment = config_manager.load_environment(env)
    if not environment:
        console.print(f"[red]Environment '{env}' not found[/red]")
        raise typer.Exit(1)

    if key not in environment.variables:
        console.print(f"[red]Variable '{key}' not found in environment '{env}'[/red]")
        raise typer.Exit(1)

    var = environment.variables[key]
    value = var.value
    if decrypt and var.encrypted:
        value = encryption_manager.decrypt(value)

    console.print(f"{key}={value}")


@app.command("delete")
def delete(
    name: str = typer.Argument(..., help="Name of the environment"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation"),
):
    """Delete an environment."""
    config_manager = get_config_manager()

    if not config_manager.environment_exists(name):
        console.print(f"[red]Environment '{name}' not found[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete environment '{name}'?")
        if not confirm:
            console.print("[yellow]Deletion cancelled[/yellow]")
            raise typer.Exit()

    if config_manager.delete_environment(name):
        console.print(f"[green]Deleted environment '{name}'[/green]")
    else:
        console.print(f"[red]Failed to delete environment '{name}'[/red]")
        raise typer.Exit(1)


@app.command("import")
def import_vars(
    env: str = typer.Argument(..., help="Name of the environment"),
    file: Path = typer.Argument(..., help="Path to input file"),
    merge: bool = typer.Option(True, help="Merge with existing variables"),
    create: bool = typer.Option(False, help="Create environment if it doesn't exist"),
):
    """Import variables from a file."""
    config_manager = get_config_manager()

    if not file.exists():
        console.print(f"[red]File not found: {file}[/red]")
        raise typer.Exit(1)

    # Read file
    try:
        file_vars = ConfigFileHandler.read_file(file)
    except Exception as e:
        console.print(f"[red]Error reading file: {e}[/red]")
        raise typer.Exit(1)

    # Get or create environment
    environment = config_manager.load_environment(env)
    if not environment:
        if create:
            environment = Environment(
                name=env,
                variables={},
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            )
            console.print(f"[green]Created new environment '{env}'[/green]")
        else:
            console.print(f"[red]Environment '{env}' not found[/red]")
            raise typer.Exit(1)

    # Merge or replace variables
    new_variables = (
        {k: ConfigVariable(name=k, value=str(v)) for k, v in file_vars.items()}
        if merge
        else {}
    )

    if not merge:
        environment.variables = new_variables
    else:
        for k, v in file_vars.items():
            environment.variables[k] = ConfigVariable(name=k, value=str(v))

    config_manager.save_environment(environment)
    console.print(
        f"[green]Imported {len(file_vars)} variables from '{file}' into environment '{env}'[/green]"
    )


@app.command("export")
def export(
    env: str = typer.Argument(..., help="Name of the environment"),
    output: Optional[Path] = typer.Option(None, help="Output file path"),
    format: str = typer.Option("env", help="Output format (env, json, yaml, toml)"),
    decrypt: bool = typer.Option(True, help="Decrypt sensitive values"),
    template: Optional[Path] = typer.Option(None, help="Apply template rendering"),
):
    """Export environment variables to a file."""
    config_manager = get_config_manager()
    encryption_manager = get_encryption_manager()

    environment = config_manager.load_environment(env)
    if not environment:
        console.print(f"[red]Environment '{env}' not found[/red]")
        raise typer.Exit(1)

    # Prepare output data
    output_data = {}
    for var in environment.variables.values():
        value = var.value
        if decrypt and var.encrypted:
            value = encryption_manager.decrypt(value)
        output_data[var.name] = value

    # Apply template rendering if specified
    if template:
        if not template.exists():
            console.print(f"[red]Template file not found: {template}[/red]")
            raise typer.Exit(1)

        try:
            template_data = ConfigFileHandler.read_file(template)
            output_data = TemplateRenderer.render_dict(template_data, output_data)
        except Exception as e:
            console.print(f"[red]Error rendering template: {e}[/red]")
            raise typer.Exit(1)

    # Write to file or print to console
    if output:
        try:
            ConfigFileHandler.write_file(output, output_data)
            console.print(f"[green]Exported environment '{env}' to '{output}'[/green]")
        except Exception as e:
            console.print(f"[red]Error writing file: {e}[/red]")
            raise typer.Exit(1)
    else:
        if format == "json":
            import json
            console.print(Syntax(json.dumps(output_data, indent=2), "json"))
        elif format == "yaml":
            import yaml
            console.print(Syntax(yaml.dump(output_data, default_flow_style=False), "yaml"))
        elif format == "toml":
            import toml
            console.print(Syntax(toml.dumps(output_data), "toml"))
        else:  # env format
            env_output = "\n".join([f"{k}={v}" for k, v in output_data.items()])
            console.print(env_output)


@app.command("validate")
def validate(
    env: str = typer.Argument(..., help="Name of the environment"),
    template: str = typer.Argument("default", help="Template to validate against"),
    rules: Optional[Path] = typer.Option(None, help="Path to custom rules file"),
):
    """Validate an environment against a template and custom rules."""
    _validate_environment(env, template, console, rules)


def _validate_environment(
    env_name: str,
    template_name: str,
    console: Console,
    rules_path: Optional[Path] = None,
) -> None:
    """Internal function to validate an environment."""
    config_manager = get_config_manager()
    encryption_manager = get_encryption_manager()
    validator = ConfigValidator(encryption_manager)

    # Load environment
    env = config_manager.load_environment(env_name)
    if not env:
        console.print(f"[red]Environment '{env_name}' not found[/red]")
        raise typer.Exit(1)

    # Load template
    template = config_manager.load_template(template_name)
    if not template:
        console.print(f"[red]Template '{template_name}' not found[/red]")
        raise typer.Exit(1)

    # Validate against template
    result = validator.validate_environment_against_template(env, template)

    # Validate against custom rules if specified
    if rules_path:
        if not rules_path.exists():
            console.print(f"[red]Rules file not found: {rules_path}[/red]")
            raise typer.Exit(1)
        try:
            import json
            with open(rules_path, "r") as f:
                rules = json.load(f)
            rules_result = validator.validate_custom_rules(env, rules)
            result.merge(rules_result)
        except Exception as e:
            console.print(f"[red]Error loading custom rules: {e}[/red]")
            raise typer.Exit(1)

    # Display results
    if result.is_valid:
        console.print(f"[green]Environment '{env_name}' is valid![/green]")
    else:
        console.print(f"[red]Environment '{env_name}' has validation errors:[/red]")
        for error in result.errors:
            console.print(f"  [red]- {error}[/red]")

    if result.warnings:
        console.print(f"[yellow]Warnings:[/yellow]")
        for warning in result.warnings:
            console.print(f"  [yellow]- {warning}[/yellow]")

    if not result.is_valid:
        raise typer.Exit(1)


@app.command("render")
def render(
    env: str = typer.Argument(..., help="Name of the environment"),
    template: Path = typer.Argument(..., help="Path to template file"),
    output: Path = typer.Argument(..., help="Path to output file"),
    decrypt: bool = typer.Option(True, help="Decrypt sensitive values"),
):
    """Render a template file with environment variables."""
    config_manager = get_config_manager()
    encryption_manager = get_encryption_manager()

    environment = config_manager.load_environment(env)
    if not environment:
        console.print(f"[red]Environment '{env}' not found[/red]")
        raise typer.Exit(1)

    if not template.exists():
        console.print(f"[red]Template file not found: {template}[/red]")
        raise typer.Exit(1)

    # Get variables
    variables = {}
    for var in environment.variables.values():
        value = var.value
        if decrypt and var.encrypted:
            value = encryption_manager.decrypt(value)
        variables[var.name] = value

    # Render template
    try:
        TemplateRenderer.render_file(template, output, variables)
        console.print(f"[green]Rendered template '{template}' to '{output}'[/green]")
    except Exception as e:
        console.print(f"[red]Error rendering template: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
