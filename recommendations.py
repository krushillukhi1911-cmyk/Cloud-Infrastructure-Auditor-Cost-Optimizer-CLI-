from typing import Any, Dict, List


def generate_recommendations_summary(findings: List[Dict[str, Any]]) -> str:
    """Generates a text summary of optimization recommendations from findings."""
    if not findings:
        return "No waste found. Cloud infrastructure is fully optimized!"

    total_monthly = sum(f["monthly_cost"] for f in findings)
    total_yearly = total_monthly * 12

    summary = []
    summary.append("====================================================")
    summary.append("COST OPTIMIZATION RECOMMENDATIONS")
    summary.append("====================================================")
    summary.append(f"Potential Monthly Savings: ${total_monthly:,.2f}")
    summary.append(f"Potential Yearly Savings:  ${total_yearly:,.2f}")
    summary.append("")
    summary.append("Detailed Recommendations:")
    summary.append("-------------------------")

    for i, finding in enumerate(findings, 1):
        res_id = finding["resource_id"]
        res_type = finding["resource_type"]
        provider = finding["provider"].upper()
        region = finding["region"]
        issue = finding["issue"]
        saving = finding["monthly_cost"]

        # Extract recommendation if available
        rec = finding.get("metadata", {}).get("recommendation")
        if not rec:
            if "EBS" in res_type or "Disk" in res_type:
                rec = "Delete unattached disk volume"
            elif "IP" in res_type:
                rec = "Release unassociated static IP address"
            else:
                rec = "Review resource usage"

        summary.append(f"{i}. [{provider}] {res_type} '{res_id}' in {region}")
        summary.append(f"   Issue:          {issue}")
        summary.append(f"   Action:         {rec}")
        summary.append(f"   Monthly Waste:  ${saving:,.2f}/mo")
        summary.append("")

    return "\n".join(summary)
