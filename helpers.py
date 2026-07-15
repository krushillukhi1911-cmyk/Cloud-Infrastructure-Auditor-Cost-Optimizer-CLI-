from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional


def format_currency(amount: float) -> str:
    """Formats a float as a currency string."""
    return f"${amount:,.2f}"


def get_past_date(days: int) -> datetime:
    """Returns a datetime object set to the specified number of days in the past (UTC)."""
    return datetime.now(timezone.utc) - timedelta(days=days)


def get_aws_tag_value(tags: Optional[List[Dict[str, str]]], key: str) -> str:
    """Extracts a tag value from a standard list of AWS tags."""
    if not tags:
        return ""
    for tag in tags:
        if tag.get("Key", "").lower() == key.lower():
            return tag.get("Value", "")
    return ""


def get_gcp_label_value(labels: Optional[Dict[str, str]], key: str) -> str:
    """Extracts a label value from GCP labels dict."""
    if not labels:
        return ""
    return labels.get(key, "")
