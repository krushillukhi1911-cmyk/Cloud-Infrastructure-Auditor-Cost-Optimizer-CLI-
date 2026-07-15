import json
import os
from typing import Any, Dict
from app.utils.logger import logger


def export_json_report(scan_results: Dict[str, Any], output_path: str) -> None:
    """Exports scan findings to a JSON file."""
    try:
        # Resolve directory path and create if needed
        dir_name = os.path.dirname(os.path.abspath(output_path))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(scan_results, f, indent=4)
        logger.info(f"[green]Successfully exported JSON report to: {output_path}[/green]")
    except Exception as e:
        logger.error(f"Failed to export JSON report to {output_path}: {e}")
