import json
import os
from datetime import datetime, timezone
from typing import List, Optional
import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from app.utils.config import load_config
from app.utils.logger import setup_logger
from app.optimizer.cost_analyzer import CostAnalyzer
from app.optimizer.cleanup import CleanupManager
from app.optimizer.recommendations import generate_recommendations_summary
from app.reports.rich_report import render_terminal_report
from app.reports.json_report import export_json_report
from app.reports.csv_report import export_csv_report

# We define the Typer app inside commands
app = typer.Typer(no_args_is_help=True)
console = Console()


def _generate_mock_findings(provider: str, region: str) -> dict:
    """Generates fake wasteful resources for visual demonstration when --mock is used."""
    if provider == "aws":
        findings = [
            {
                "resource_id": "vol-0683a6b57d89abcdef",
                "resource_type": "EBS Volume",
                "provider": "aws",
                "region": region,
                "issue": "Unattached EBS Volume",
                "monthly_cost": 40.00,
                "metadata": {
                    "name": "dev-backup-db",
                    "size_gb": 500,
                    "volume_type": "gp2",
                    "recommendation": "Delete volume"
                }
            },
            {
                "resource_id": "eipalloc-0a8677fbc1d2",
                "resource_type": "Elastic IP",
                "provider": "aws",
                "region": region,
                "issue": "Unassociated Elastic IP",
                "monthly_cost": 3.60,
                "metadata": {
                    "ip_address": "54.210.12.87",
                    "allocation_id": "eipalloc-0a8677fbc1d2",
                    "recommendation": "Release IP"
                }
            },
            {
                "resource_id": "i-0987654321fedcba0",
                "resource_type": "EC2 Instance",
                "provider": "aws",
                "region": region,
                "issue": "Idle EC2 Instance (Avg CPU: 0.8%, Net: 1.2MB)",
                "monthly_cost": 62.00,
                "metadata": {
                    "name": "staging-analytics-worker",
                    "instance_type": "c5.large",
                    "avg_cpu_percent": 0.8,
                    "network_usage_mb": 1.2,
                    "recommendation": "Stop or Delete Instance"
                }
            }
        ]
    else:
        findings = [
            {
                "resource_id": "unused-gcp-disk",
                "resource_type": "Persistent Disk",
                "provider": "gcp",
                "region": region,
                "issue": "Unattached Persistent Disk",
                "monthly_cost": 34.00,
                "metadata": {
                    "name": "unused-gcp-disk",
                    "size_gb": 200,
                    "volume_type": "pd-ssd",
                    "recommendation": "Delete disk"
                }
            },
            {
                "resource_id": "gcp-external-ip",
                "resource_type": "External IP",
                "provider": "gcp",
                "region": region,
                "issue": "Unused Reserved External IP",
                "monthly_cost": 7.20,
                "metadata": {
                    "ip_address": "34.120.45.67",
                    "name": "gcp-external-ip",
                    "recommendation": "Release IP"
                }
            },
            {
                "resource_id": "idle-gce-vm",
                "resource_type": "GCE Instance",
                "provider": "gcp",
                "region": region,
                "issue": "Idle GCE Instance (Avg CPU: 0.5%, Net: 0.4MB)",
                "monthly_cost": 50.00,
                "metadata": {
                    "name": "idle-gce-vm",
                    "instance_type": "n1-standard-2",
                    "avg_cpu_percent": 0.5,
                    "network_usage_mb": 0.4,
                    "recommendation": "Stop or Delete Instance"
                }
            }
        ]
    return {
        "provider": provider,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "total_resources": len(findings),
        "unused_resources": len(findings),
        "monthly_savings": sum(f["monthly_cost"] for f in findings),
        "yearly_savings": sum(f["monthly_cost"] for f in findings) * 12,
        "findings": findings
    }


@app.command(name="scan")
def scan(
    provider: str = typer.Option(
        "aws",
        "--provider",
        "-p",
        help="Cloud provider to scan: 'aws' or 'gcp'",
    ),
    regions: Optional[str] = typer.Option(
        None,
        "--region",
        "-r",
        help="Comma-separated list of regions to scan (e.g. us-east-1,us-west-2). Falls back to config defaults.",
    ),
    config_path: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to YAML configuration file.",
    ),
    output_json: Optional[str] = typer.Option(
        None,
        "--output-json",
        "-j",
        help="Output path for JSON report.",
    ),
    output_csv: Optional[str] = typer.Option(
        None,
        "--output-csv",
        "-v",
        help="Output path for CSV report.",
    ),
    mock: bool = typer.Option(
        False,
        "--mock",
        "-m",
        help="Run scan in mock simulation mode (no credentials required).",
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        help="Console logging level: DEBUG, INFO, WARNING, ERROR",
    ),
):
    """Scan cloud infrastructure for wasteful resources and calculate optimization opportunities."""
    setup_logger(log_level=log_level)
    config = load_config(config_path)

    # Resolve regions to scan
    provider = provider.lower()
    if provider not in ["aws", "gcp"]:
        console.print(f"[bold red]Error: Invalid provider '{provider}'. Must be 'aws' or 'gcp'.[/bold red]")
        raise typer.Exit(code=1)

    target_regions = []
    if regions:
        target_regions = [r.strip() for r in regions.split(",") if r.strip()]
    else:
        if provider == "aws":
            target_regions = config.cloud.aws.regions
        else:
            target_regions = config.cloud.gcp.regions

    # Run analysis
    if mock:
        results = _generate_mock_findings(provider, target_regions[0] if target_regions else "us-east-1")
    else:
        analyzer = CostAnalyzer(config)
        results = analyzer.analyze(provider, target_regions)

    # Render pretty terminal report
    render_terminal_report(results)

    # Export formats
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    os.makedirs("reports", exist_ok=True)

    json_path = output_json or f"reports/report_{provider}_{timestamp}.json"
    export_json_report(results, json_path)

    if output_csv:
        export_csv_report(results, output_csv)
    else:
        csv_path = f"reports/report_{provider}_{timestamp}.csv"
        export_csv_report(results, csv_path)


@app.command(name="report")
def report(
    path: str = typer.Argument(
        ...,
        help="Path to a previously exported JSON scan report.",
    )
):
    """View a detailed terminal layout of a previously exported JSON scan report."""
    if not os.path.exists(path):
        console.print(f"[bold red]Error: File not found at '{path}'[/bold red]")
        raise typer.Exit(code=1)

    try:
        with open(path, "r") as f:
            data = json.load(f)
        render_terminal_report(data)
    except Exception as e:
        console.print(f"[bold red]Error: Failed to parse JSON report at '{path}': {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command(name="cleanup")
def cleanup(
    provider: str = typer.Option(
        "aws",
        "--provider",
        "-p",
        help="Cloud provider of target resources: 'aws' or 'gcp'",
    ),
    regions: Optional[str] = typer.Option(
        None,
        "--region",
        "-r",
        help="Comma-separated list of regions to scan & clean (e.g. us-east-1).",
    ),
    config_path: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file.",
    ),
    execute: bool = typer.Option(
        False,
        "--execute",
        "-e",
        help="Execute cleanup modifications (safeguarded by confirmation prompt). If not set, runs dry-run.",
    ),
    mock: bool = typer.Option(
        False,
        "--mock",
        "-m",
        help="Run cleanup in mock simulation mode (no credentials required).",
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        help="Logging level.",
    ),
):
    """Identify wasteful resources and execute deletion/suspension operations."""
    setup_logger(log_level=log_level)
    config = load_config(config_path)

    provider = provider.lower()
    if provider not in ["aws", "gcp"]:
        console.print(f"[bold red]Error: Invalid provider '{provider}'.[/bold red]")
        raise typer.Exit(code=1)

    target_regions = []
    if regions:
        target_regions = [r.strip() for r in regions.split(",") if r.strip()]
    else:
        if provider == "aws":
            target_regions = config.cloud.aws.regions
        else:
            target_regions = config.cloud.gcp.regions

    # Scan first to ensure we know what resources we are cleaning
    if mock:
        results = _generate_mock_findings(provider, target_regions[0] if target_regions else "us-east-1")
    else:
        console.print(f"[bold yellow]Running pre-cleanup scan for {provider.upper()} in {target_regions}...[/bold yellow]")
        analyzer = CostAnalyzer(config)
        results = analyzer.analyze(provider, target_regions)
        
    findings = results.get("findings", [])

    if not findings:
        console.print("[bold green]✔ Pre-cleanup scan found no waste. Nothing to clean up.[/bold green]")
        raise typer.Exit(code=0)

    render_terminal_report(results)

    # Handle execute mode vs dry-run
    if not execute:
        console.print("[yellow]Dry-run summary: The resources listed above would be deleted/stopped.[/yellow]")
        console.print("[yellow]To apply changes, run the command with --execute[/yellow]")
        if mock:
            console.print("[yellow]DRY-RUN MODE ENABLED. No changes will be applied.[/yellow]")
            for f in findings:
                console.print(f"Cleaning up {f['resource_type']} '{f['resource_id']}' in {f['provider'].upper()} ({f['region']})...")
        else:
            cleanup_mgr = CleanupManager()
            cleanup_mgr.execute_cleanup(findings, dry_run=True)
    else:
        console.print(
            f"[bold red]🚨 WARNING: You are about to permanently stop or delete {len(findings)} resources.[/bold red]\n"
            f"[bold red]This operation is IRREVERSIBLE and cannot be undone.[/bold red]"
        )
        confirm = typer.prompt("To proceed, type DELETE (case-sensitive)")

        if confirm != "DELETE":
            console.print("[yellow]Cleanup cancelled by user.[/yellow]")
            raise typer.Exit(code=0)

        if mock:
            for f in findings:
                console.print(f"Cleaning up {f['resource_type']} '{f['resource_id']}' in {f['provider'].upper()} ({f['region']})...")
                console.print(f"[green]Successfully cleaned up {f['resource_type']} {f['resource_id']}[/green]")
        else:
            cleanup_mgr = CleanupManager()
            cleanup_mgr.execute_cleanup(findings, dry_run=False)


@app.command(name="config")
def config(
    config_path: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to YAML configuration file.",
    )
):
    """View the active configuration configuration schema."""
    config_obj = load_config(config_path)
    console.print(Panel("[bold cyan]Active Configuration Settings[/bold cyan]", expand=False))
    # We dump config to yaml format and print
    dumped_yaml = yaml.dump(config_obj.model_dump(), default_flow_style=False)
    console.print(dumped_yaml)
