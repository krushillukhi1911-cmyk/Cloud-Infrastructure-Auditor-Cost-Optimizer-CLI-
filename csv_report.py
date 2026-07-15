import csv
import os
from typing import Any, Dict
from app.utils.logger import logger


def export_csv_report(scan_results: Dict[str, Any], output_path: str) -> None:
    """Exports scan findings to a CSV file."""
    findings = scan_results.get("findings", [])
    try:
        # Resolve directory path and create if needed
        dir_name = os.path.dirname(os.path.abspath(output_path))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        headers = [
            "Provider",
            "Region",
            "Resource ID",
            "Resource Type",
            "Issue Details",
            "Monthly Waste",
            "Recommendation",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for finding in findings:
                meta = finding.get("metadata", {})
                rec = meta.get("recommendation", "")
                if not rec:
                    if "EBS" in finding["resource_type"] or "Disk" in finding["resource_type"]:
                        rec = "Delete volume"
                    elif "IP" in finding["resource_type"]:
                        rec = "Release IP"
                    else:
                        rec = "Optimize"

                writer.writerow(
                    [
                        finding.get("provider", "").upper(),
                        finding.get("region", ""),
                        finding.get("resource_id", ""),
                        finding.get("resource_type", ""),
                        finding.get("issue", ""),
                        f"{finding.get('monthly_cost', 0.0):.2f}",
                        rec,
                    ]
                )

        logger.info(f"[green]Successfully exported CSV report to: {output_path}[/green]")
    except Exception as e:
        logger.error(f"Failed to export CSV report to {output_path}: {e}")
