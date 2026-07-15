from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.scanners.base_scanner import BaseScanner
from app.scanners.ebs_scanner import EBSScanner
from app.scanners.elastic_ip_scanner import ElasticIPScanner
from app.scanners.ec2_scanner import EC2Scanner
from app.utils.config import AppConfig
from app.utils.logger import logger


class CostAnalyzer:
    """Aggregates findings from various scanners and calculates cost optimizations."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.scanners: List[BaseScanner] = [
            EBSScanner(config),
            ElasticIPScanner(config),
            EC2Scanner(config),
        ]

    def analyze(self, provider: str, regions: List[str]) -> Dict[str, Any]:
        """Runs all scanners against specified regions for the given provider.

        Returns aggregated statistics and findings list.
        """
        logger.info(f"Starting cost analysis for provider: {provider.upper()} in regions: {regions}")
        all_findings = []

        for region in regions:
            for scanner in self.scanners:
                try:
                    findings = scanner.scan(provider, region)
                    all_findings.extend(findings)
                except Exception as e:
                    logger.error(
                        f"Scanner {scanner.__class__.__name__} failed in region {region} for provider {provider}: {e}"
                    )

        # Aggregate metrics
        total_findings = len(all_findings)
        total_monthly_savings = sum(f["monthly_cost"] for f in all_findings)
        total_yearly_savings = total_monthly_savings * 12

        result = {
            "provider": provider,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "total_resources": total_findings,  # Count of flagged resource waste items
            "unused_resources": total_findings,
            "monthly_savings": total_monthly_savings,
            "yearly_savings": total_yearly_savings,
            "findings": all_findings,
        }

        logger.info(
            f"Analysis complete for {provider.upper()}. "
            f"Flagged resources: {total_findings}, Potential Monthly Savings: ${total_monthly_savings:.2f}"
        )
        return result
