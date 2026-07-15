from typing import Any, Dict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from app.utils.helpers import format_currency


def render_terminal_report(scan_results: Dict[str, Any]) -> None:
    """Prints a styled terminal dashboard of the scanning results using Rich."""
    console = Console()

    provider = scan_results.get("provider", "unknown").upper()
    findings = scan_results.get("findings", [])
    monthly_savings = scan_results.get("monthly_savings", 0.0)
    yearly_savings = scan_results.get("yearly_savings", 0.0)

    # 1. Print Title Banner
    console.print(
        Panel(
            f"[bold cyan]Cloud Infrastructure Auditor & Cost Optimizer CLI[/bold cyan]\n"
            f"[dim]Provider: {provider} | Scanned At: {scan_results.get('scanned_at')}[/dim]",
            expand=False,
            border_style="cyan",
        )
    )

    # 2. Print Savings Key Cards
    total_waste_card = Panel(
        f"[bold red]{scan_results.get('total_resources', 0)}[/bold red]",
        title="Flagged Resources",
        border_style="red",
    )
    monthly_savings_card = Panel(
        f"[bold green]{format_currency(monthly_savings)}[/bold green]",
        title="Est. Monthly Savings",
        border_style="green",
    )
    yearly_savings_card = Panel(
        f"[bold green]{format_currency(yearly_savings)}[/bold green]",
        title="Est. Yearly Savings",
        border_style="green",
    )

    console.print(Columns([total_waste_card, monthly_savings_card, yearly_savings_card]))
    console.print()

    # 3. Print Findings Table
    if not findings:
        console.print("[bold green]✔ No waste identified! All scanned resources conform to optimization rules.[/bold green]")
        console.print()
        return

    table = Table(
        title="Identified Waste & Recommendations",
        title_style="bold underline",
        show_header=True,
        header_style="bold magenta",
        expand=True,
    )

    table.add_column("Resource ID", style="cyan", min_width=15)
    table.add_column("Type", style="yellow")
    table.add_column("Region", style="dim")
    table.add_column("Issue Details", style="white")
    table.add_column("Monthly Waste", style="red", justify="right")
    table.add_column("Action Recommendation", style="green")

    for f in findings:
        meta = f.get("metadata", {})
        rec = meta.get("recommendation")
        if not rec:
            if "EBS" in f["resource_type"] or "Disk" in f["resource_type"]:
                rec = "Delete volume"
            elif "IP" in f["resource_type"]:
                rec = "Release IP"
            else:
                rec = "Optimize"

        table.add_row(
            f["resource_id"],
            f["resource_type"],
            f["region"],
            f["issue"],
            format_currency(f["monthly_cost"]),
            rec,
        )

    console.print(table)
    console.print()
