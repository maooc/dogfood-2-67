"""CLI 命令接口."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from envsync.config import ConfigManager
from envsync.crypto import CryptoManager
from envsync.diff import DiffEngine, DiffType
from envsync.exporter import ConfigExporter
from envsync.models import ConfigFormat, ValidationRule
from envsync.snapshot import SnapshotManager
from envsync.template import TemplateEngine
from envsync.validator import ConfigValidator

app = typer.Typer(
    name="envsync",
    help="多环境配置文件管理工具",
    rich_markup_mode="rich",
)
console = Console()


def get_config_manager() -> ConfigManager:
    """获取配置管理器."""
    return ConfigManager()


@app.command()
def init(
    name: str = typer.Option(..., "--name", "-n", help="项目名称"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="项目描述"),
    environments: Optional[List[str]] = typer.Option(
        None, "--env", "-e", help="初始环境（可多次指定）"
    ),
) -> None:
    """初始化新项目."""
    config_manager = ConfigManager()

    try:
        config = config_manager.init_project(
            name=name,
            description=description,
            environments=environments,
        )
        console.print(Panel.fit(
            f"[green]项目初始化成功![/green]\n"
            f"名称: {config.name}\n"
            f"环境: {', '.join(config.environments.keys())}",
            title="Envsync",
        ))
    except Exception as e:
        console.print(f"[red]初始化失败: {e}[/red]")
        raise typer.Exit(1)


# 环境管理子命令
env_app = typer.Typer(help="环境管理命令")
app.add_typer(env_app, name="env")


@env_app.command(name="list")
def env_list() -> None:
    """列出所有环境."""
    config_manager = get_config_manager()

    table = Table(title="环境列表")
    table.add_column("名称", style="cyan")
    table.add_column("描述", style="green")
    table.add_column("变量数", style="yellow")
    table.add_column("配置文件数", style="magenta")
    table.add_column("父环境", style="blue")

    for name, env in config_manager.config.environments.items():
        file_count = len(config_manager.get_environment_files(name))
        parent = env.parent or "-"
        table.add_row(
            name,
            env.description or "-",
            str(len(env.variables)),
            str(file_count),
            parent,
        )

    console.print(table)


@env_app.command(name="add")
def env_add(
    name: str = typer.Argument(..., help="环境名称"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="环境描述"),
    parent: Optional[str] = typer.Option(None, "--parent", "-p", help="父环境"),
) -> None:
    """添加新环境."""
    config_manager = get_config_manager()

    try:
        env = config_manager.add_environment(name, description, parent)
        console.print(f"[green]环境添加成功: {env.name}[/green]")
    except Exception as e:
        console.print(f"[red]添加失败: {e}[/red]")
        raise typer.Exit(1)


@env_app.command(name="remove")
def env_remove(
    name: str = typer.Argument(..., help="环境名称"),
    force: bool = typer.Option(False, "--force", "-f", help="强制删除"),
) -> None:
    """删除环境."""
    config_manager = get_config_manager()

    try:
        config_manager.remove_environment(name, force)
        console.print(f"[green]环境删除成功: {name}[/green]")
    except Exception as e:
        console.print(f"[red]删除失败: {e}[/red]")
        raise typer.Exit(1)


# 变量管理子命令
var_app = typer.Typer(help="变量管理命令")
app.add_typer(var_app, name="var")


@var_app.command(name="list")
def var_list(
    environment: str = typer.Argument(..., help="环境名称"),
    show_values: bool = typer.Option(False, "--show-values", "-v", help="显示变量值"),
) -> None:
    """列出环境变量."""
    config_manager = get_config_manager()

    env = config_manager.get_environment(environment)
    if not env:
        console.print(f"[red]环境不存在: {environment}[/red]")
        raise typer.Exit(1)

    table = Table(title=f"{environment} 环境变量")
    table.add_column("名称", style="cyan")
    table.add_column("值", style="green")
    table.add_column("描述", style="yellow")
    table.add_column("敏感", style="magenta")

    for name, var in env.variables.items():
        value = var.value if show_values else "***" if var.is_sensitive else var.value[:20]
        sensitive = "是" if var.is_sensitive else "否"
        table.add_row(name, value, var.description or "-", sensitive)

    console.print(table)


@var_app.command(name="set")
def var_set(
    environment: str = typer.Argument(..., help="环境名称"),
    name: str = typer.Argument(..., help="变量名"),
    value: str = typer.Argument(..., help="变量值"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="变量描述"),
    sensitive: bool = typer.Option(False, "--sensitive", "-s", help="敏感字段"),
) -> None:
    """设置环境变量."""
    config_manager = get_config_manager()

    try:
        config_manager.set_variable(environment, name, value, description, sensitive)
        console.print(f"[green]变量设置成功: {name}[/green]")
    except Exception as e:
        console.print(f"[red]设置失败: {e}[/red]")
        raise typer.Exit(1)


@var_app.command(name="remove")
def var_remove(
    environment: str = typer.Argument(..., help="环境名称"),
    name: str = typer.Argument(..., help="变量名"),
) -> None:
    """删除环境变量."""
    config_manager = get_config_manager()

    try:
        config_manager.remove_variable(environment, name)
        console.print(f"[green]变量删除成功: {name}[/green]")
    except Exception as e:
        console.print(f"[red]删除失败: {e}[/red]")
        raise typer.Exit(1)


# 配置文件管理子命令
file_app = typer.Typer(help="配置文件管理命令")
app.add_typer(file_app, name="file")


@file_app.command(name="list")
def file_list() -> None:
    """列出所有配置文件."""
    config_manager = get_config_manager()

    table = Table(title="配置文件列表")
    table.add_column("名称", style="cyan")
    table.add_column("路径", style="green")
    table.add_column("格式", style="yellow")
    table.add_column("环境", style="magenta")
    table.add_column("加密字段", style="blue")

    for cf in config_manager.config.config_files:
        encrypted = ", ".join(cf.encrypted_fields) if cf.encrypted_fields else "-"
        table.add_row(cf.name, str(cf.path), cf.format.value, cf.environment, encrypted)

    console.print(table)


@file_app.command(name="add")
def file_add(
    name: str = typer.Argument(..., help="配置文件名称"),
    path: Path = typer.Argument(..., help="文件路径"),
    format: ConfigFormat = typer.Argument(..., help="文件格式"),
    environment: str = typer.Option(..., "--env", "-e", help="所属环境"),
    template: Optional[Path] = typer.Option(None, "--template", "-t", help="模板文件路径"),
    encrypted: Optional[List[str]] = typer.Option(
        None, "--encrypt", help="加密字段（可多次指定）"
    ),
) -> None:
    """添加配置文件."""
    config_manager = get_config_manager()

    try:
        cf = config_manager.add_config_file(
            name=name,
            path=path,
            format=format,
            environment=environment,
            template=template,
            encrypted_fields=encrypted,
        )
        console.print(f"[green]配置文件添加成功: {cf.name}[/green]")
    except Exception as e:
        console.print(f"[red]添加失败: {e}[/red]")
        raise typer.Exit(1)


@file_app.command(name="remove")
def file_remove(
    name: str = typer.Argument(..., help="配置文件名称"),
) -> None:
    """删除配置文件."""
    config_manager = get_config_manager()

    try:
        config_manager.remove_config_file(name)
        console.print(f"[green]配置文件删除成功: {name}[/green]")
    except Exception as e:
        console.print(f"[red]删除失败: {e}[/red]")
        raise typer.Exit(1)


# 模板管理子命令
template_app = typer.Typer(help="模板管理命令")
app.add_typer(template_app, name="template")


@template_app.command(name="render")
def template_render(
    config_name: str = typer.Argument(..., help="配置文件名称"),
    environment: str = typer.Option(..., "--env", "-e", help="环境名称"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出路径"),
    strict: bool = typer.Option(False, "--strict", help="严格模式"),
) -> None:
    """渲染模板."""
    config_manager = get_config_manager()
    template_engine = TemplateEngine(config_manager)

    cf = config_manager.get_config_file(config_name)
    if not cf:
        console.print(f"[red]配置文件不存在: {config_name}[/red]")
        raise typer.Exit(1)

    try:
        result_path = template_engine.process_config_file(cf, environment, output, strict)
        console.print(f"[green]模板渲染成功: {result_path}[/green]")
    except Exception as e:
        console.print(f"[red]渲染失败: {e}[/red]")
        raise typer.Exit(1)


@template_app.command(name="preview")
def template_preview(
    config_name: str = typer.Argument(..., help="配置文件名称"),
    environment: str = typer.Option(..., "--env", "-e", help="环境名称"),
) -> None:
    """预览模板渲染结果."""
    config_manager = get_config_manager()
    template_engine = TemplateEngine(config_manager)

    cf = config_manager.get_config_file(config_name)
    if not cf:
        console.print(f"[red]配置文件不存在: {config_name}[/red]")
        raise typer.Exit(1)

    try:
        preview = template_engine.preview(cf, environment)
        console.print(Panel(preview, title=f"预览: {config_name}"))
    except Exception as e:
        console.print(f"[red]预览失败: {e}[/red]")
        raise typer.Exit(1)


# 差异对比子命令
diff_app = typer.Typer(help="差异对比命令")
app.add_typer(diff_app, name="diff")


@diff_app.command(name="env")
def diff_env(
    env1: str = typer.Argument(..., help="第一个环境"),
    env2: str = typer.Argument(..., help="第二个环境"),
) -> None:
    """对比两个环境."""
    config_manager = get_config_manager()
    diff_engine = DiffEngine(config_manager)

    try:
        results = diff_engine.compare_environments(env1, env2)

        summary_table = diff_engine.format_diff_summary(results)
        console.print(summary_table)

        for category, diffs in results.items():
            if diffs:
                diff_table = diff_engine.format_diff_table(diffs, f"{category} 差异")
                console.print(diff_table)
    except Exception as e:
        console.print(f"[red]对比失败: {e}[/red]")
        raise typer.Exit(1)


@diff_app.command(name="vars")
def diff_vars(
    env1: str = typer.Argument(..., help="第一个环境"),
    env2: str = typer.Argument(..., help="第二个环境"),
) -> None:
    """对比两个环境的变量."""
    config_manager = get_config_manager()
    diff_engine = DiffEngine(config_manager)

    try:
        results = diff_engine.compare_variables(env1, env2)
        table = diff_engine.format_diff_table(results, f"{env1} vs {env2} 变量差异")
        console.print(table)
    except Exception as e:
        console.print(f"[red]对比失败: {e}[/red]")
        raise typer.Exit(1)


# 加密管理子命令
crypto_app = typer.Typer(help="加密管理命令")
app.add_typer(crypto_app, name="crypto")


@crypto_app.command(name="init")
def crypto_init(
    password: Optional[str] = typer.Option(None, "--password", "-p", help="加密密码"),
) -> None:
    """初始化加密系统."""
    config_manager = get_config_manager()
    crypto_manager = CryptoManager(config_manager)

    try:
        key_path = crypto_manager.initialize(password)
        console.print(f"[green]加密系统初始化成功: {key_path}[/green]")
    except Exception as e:
        console.print(f"[red]初始化失败: {e}[/red]")
        raise typer.Exit(1)


@crypto_app.command(name="encrypt")
def crypto_encrypt(
    config_name: str = typer.Argument(..., help="配置文件名称"),
) -> None:
    """加密配置文件."""
    config_manager = get_config_manager()
    crypto_manager = CryptoManager(config_manager)

    cf = config_manager.get_config_file(config_name)
    if not cf:
        console.print(f"[red]配置文件不存在: {config_name}[/red]")
        raise typer.Exit(1)

    try:
        crypto_manager.process_config_file(cf, encrypt=True)
        console.print(f"[green]加密成功: {config_name}[/green]")
    except Exception as e:
        console.print(f"[red]加密失败: {e}[/red]")
        raise typer.Exit(1)


@crypto_app.command(name="decrypt")
def crypto_decrypt(
    config_name: str = typer.Argument(..., help="配置文件名称"),
) -> None:
    """解密配置文件."""
    config_manager = get_config_manager()
    crypto_manager = CryptoManager(config_manager)

    cf = config_manager.get_config_file(config_name)
    if not cf:
        console.print(f"[red]配置文件不存在: {config_name}[/red]")
        raise typer.Exit(1)

    try:
        crypto_manager.process_config_file(cf, encrypt=False)
        console.print(f"[green]解密成功: {config_name}[/green]")
    except Exception as e:
        console.print(f"[red]解密失败: {e}[/red]")
        raise typer.Exit(1)


# 配置校验子命令
validate_app = typer.Typer(help="配置校验命令")
app.add_typer(validate_app, name="validate")


@validate_app.command(name="file")
def validate_file(
    config_name: str = typer.Argument(..., help="配置文件名称"),
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="环境名称"),
) -> None:
    """校验配置文件."""
    config_manager = get_config_manager()
    validator = ConfigValidator(config_manager)

    cf = config_manager.get_config_file(config_name)
    if not cf:
        console.print(f"[red]配置文件不存在: {config_name}[/red]")
        raise typer.Exit(1)

    try:
        result = validator.validate_config_file(cf, environment)

        if result.valid:
            console.print(f"[green]校验通过: {config_name}[/green]")
        else:
            console.print(f"[red]校验失败: {config_name}[/red]")
            for error in result.errors:
                console.print(f"  [red]错误: {error}[/red]")

        for warning in result.warnings:
            console.print(f"  [yellow]警告: {warning}[/yellow]")

        if not result.valid:
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]校验失败: {e}[/red]")
        raise typer.Exit(1)


@validate_app.command(name="env")
def validate_env(
    environment: str = typer.Argument(..., help="环境名称"),
) -> None:
    """校验环境的所有配置文件."""
    config_manager = get_config_manager()
    validator = ConfigValidator(config_manager)

    try:
        results = validator.validate_environment(environment)

        all_valid = True
        for file_name, result in results.items():
            if result.valid:
                console.print(f"[green]通过: {file_name}[/green]")
            else:
                all_valid = False
                console.print(f"[red]失败: {file_name}[/red]")
                for error in result.errors:
                    console.print(f"  [red]错误: {error}[/red]")

        if not all_valid:
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]校验失败: {e}[/red]")
        raise typer.Exit(1)


# 快照管理子命令
snapshot_app = typer.Typer(help="快照管理命令")
app.add_typer(snapshot_app, name="snapshot")


@snapshot_app.command(name="create")
def snapshot_create(
    environment: str = typer.Argument(..., help="环境名称"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="快照描述"),
) -> None:
    """创建快照."""
    config_manager = get_config_manager()
    snapshot_manager = SnapshotManager(config_manager)

    try:
        snapshot = snapshot_manager.create(environment, description)
        console.print(f"[green]快照创建成功: {snapshot.id}[/green]")
    except Exception as e:
        console.print(f"[red]创建失败: {e}[/red]")
        raise typer.Exit(1)


@snapshot_app.command(name="list")
def snapshot_list(
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="环境过滤"),
) -> None:
    """列出快照."""
    config_manager = get_config_manager()
    snapshot_manager = SnapshotManager(config_manager)

    snapshots = snapshot_manager.list(environment)

    table = Table(title="快照列表")
    table.add_column("ID", style="cyan")
    table.add_column("环境", style="green")
    table.add_column("创建时间", style="yellow")
    table.add_column("描述", style="magenta")

    for snapshot in snapshots:
        desc = snapshot.description or "-"
        if len(desc) > 30:
            desc = desc[:27] + "..."
        table.add_row(
            snapshot.id,
            snapshot.environment,
            snapshot.created_at.strftime("%Y-%m-%d %H:%M"),
            desc,
        )

    console.print(table)


@snapshot_app.command(name="restore")
def snapshot_restore(
    snapshot_id: str = typer.Argument(..., help="快照 ID"),
    target_env: Optional[str] = typer.Option(None, "--target", "-t", help="目标环境"),
    force: bool = typer.Option(False, "--force", "-f", help="强制恢复"),
) -> None:
    """恢复快照."""
    config_manager = get_config_manager()
    snapshot_manager = SnapshotManager(config_manager)

    try:
        snapshot_manager.restore(snapshot_id, target_env, force)
        console.print(f"[green]快照恢复成功: {snapshot_id}[/green]")
    except Exception as e:
        console.print(f"[red]恢复失败: {e}[/red]")
        raise typer.Exit(1)


@snapshot_app.command(name="delete")
def snapshot_delete(
    snapshot_id: str = typer.Argument(..., help="快照 ID"),
) -> None:
    """删除快照."""
    config_manager = get_config_manager()
    snapshot_manager = SnapshotManager(config_manager)

    try:
        snapshot_manager.delete(snapshot_id)
        console.print(f"[green]快照删除成功: {snapshot_id}[/green]")
    except Exception as e:
        console.print(f"[red]删除失败: {e}[/red]")
        raise typer.Exit(1)


@snapshot_app.command(name="export")
def snapshot_export(
    snapshot_id: str = typer.Argument(..., help="快照 ID"),
    output: Path = typer.Option(..., "--output", "-o", help="输出路径"),
    format: str = typer.Option("zip", "--format", "-f", help="导出格式 (zip/tar.gz)"),
) -> None:
    """导出快照为归档文件."""
    config_manager = get_config_manager()
    snapshot_manager = SnapshotManager(config_manager)

    try:
        result_path = snapshot_manager.export(snapshot_id, output, format)
        console.print(f"[green]快照导出成功: {result_path}[/green]")
    except Exception as e:
        console.print(f"[red]导出失败: {e}[/red]")
        raise typer.Exit(1)


@snapshot_app.command(name="import")
def snapshot_import(
    archive_path: Path = typer.Argument(..., help="归档文件路径"),
) -> None:
    """从归档文件导入快照."""
    config_manager = get_config_manager()
    snapshot_manager = SnapshotManager(config_manager)

    try:
        snapshot = snapshot_manager.import_snapshot(archive_path)
        console.print(f"[green]快照导入成功: {snapshot.id}[/green]")
    except Exception as e:
        console.print(f"[red]导入失败: {e}[/red]")
        raise typer.Exit(1)


# 导出子命令
export_app = typer.Typer(help="导出命令")
app.add_typer(export_app, name="export")


@export_app.command(name="env")
def export_env(
    environment: str = typer.Argument(..., help="环境名称"),
    output: Path = typer.Option(..., "--output", "-o", help="输出路径"),
    format: ConfigFormat = typer.Option(ConfigFormat.YAML, "--format", "-f", help="输出格式"),
    decrypt: bool = typer.Option(False, "--decrypt", "-d", help="解密敏感字段"),
) -> None:
    """导出环境配置."""
    config_manager = get_config_manager()
    exporter = ConfigExporter(config_manager)

    try:
        result_path = exporter.export_to_format(environment, output, format, decrypt)
        console.print(f"[green]导出成功: {result_path}[/green]")
    except Exception as e:
        console.print(f"[red]导出失败: {e}[/red]")
        raise typer.Exit(1)


@export_app.command(name="csv")
def export_csv(
    environments: List[str] = typer.Argument(..., help="环境名称列表"),
    output: Path = typer.Option(..., "--output", "-o", help="输出路径"),
    include_sensitive: bool = typer.Option(False, "--sensitive", "-s", help="包含敏感变量"),
) -> None:
    """导出变量为 CSV."""
    config_manager = get_config_manager()
    exporter = ConfigExporter(config_manager)

    try:
        result_path = exporter.export_csv(environments, output, include_sensitive)
        console.print(f"[green]导出成功: {result_path}[/green]")
    except Exception as e:
        console.print(f"[red]导出失败: {e}[/red]")
        raise typer.Exit(1)


@export_app.command(name="k8s")
def export_k8s(
    environment: str = typer.Argument(..., help="环境名称"),
    output: Path = typer.Option(..., "--output", "-o", help="输出路径"),
    secret_name: Optional[str] = typer.Option(None, "--name", "-n", help="Secret 名称"),
    namespace: str = typer.Option("default", "--namespace", help="命名空间"),
) -> None:
    """导出为 Kubernetes Secret."""
    config_manager = get_config_manager()
    exporter = ConfigExporter(config_manager)

    try:
        result_path = exporter.export_kubernetes_secret(
            environment, output, secret_name, namespace
        )
        console.print(f"[green]导出成功: {result_path}[/green]")
    except Exception as e:
        console.print(f"[red]导出失败: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def status() -> None:
    """显示项目状态."""
    config_manager = get_config_manager()
    config = config_manager.config

    tree = Tree(f"[bold cyan]{config.name}[/bold cyan]")

    env_branch = tree.add("[bold]环境[/bold]")
    for env_name, env in config.environments.items():
        env_node = env_branch.add(f"[green]{env_name}[/green]")
        env_node.add(f"变量: {len(env.variables)}")
        env_node.add(f"文件: {len(config_manager.get_environment_files(env_name))}")

    files_branch = tree.add("[bold]配置文件[/bold]")
    for cf in config.config_files:
        files_branch.add(f"[yellow]{cf.name}[/yellow] ({cf.environment})")

    console.print(tree)


if __name__ == "__main__":
    app()
