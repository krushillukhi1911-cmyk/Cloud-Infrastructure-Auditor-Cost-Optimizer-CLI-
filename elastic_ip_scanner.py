from typing import Any, Dict, List
from botocore.exceptions import ClientError
from google.cloud import compute_v1
from app.cloud.aws_client import AWSClient
from app.cloud.gcp_client import GCPClient
from app.scanners.base_scanner import BaseScanner
from app.utils.config import AppConfig
from app.utils.logger import logger


class ElasticIPScanner(BaseScanner):
    """Scans for allocated but unassociated Elastic IPs (AWS) and External IPs (GCP)."""

    def __init__(
        self,
        config: AppConfig,
        aws_client: AWSClient = None,
        gcp_client: GCPClient = None,
    ):
        super().__init__(config)
        self.aws_client = aws_client or AWSClient()
        self.gcp_client = gcp_client or GCPClient()

    def scan(self, provider: str, region: str) -> List[Dict[str, Any]]:
        """Scans for unassociated IPs in the specified provider and region."""
        logger.info(f"Scanning for unused public IPs in {provider.upper()} ({region})")
        findings = []

        if provider.lower() == "aws":
            findings.extend(self._scan_aws(region))
        elif provider.lower() == "gcp":
            findings.extend(self._scan_gcp(region))

        return findings

    def _scan_aws(self, region: str) -> List[Dict[str, Any]]:
        findings = []
        try:
            ec2_client = self.aws_client.get_client("ec2", region_name=region)
            response = ec2_client.describe_addresses()
            addresses = response.get("Addresses", [])

            for addr in addresses:
                # An address is idle if it does not have an AssociationId or associated instance/interface
                is_associated = addr.get("AssociationId") or addr.get("InstanceId") or addr.get("NetworkInterfaceId")
                if not is_associated:
                    ip_address = addr.get("PublicIp", "")
                    allocation_id = addr.get("AllocationId", "")
                    monthly_cost = self.calculate_cost({"provider": "aws"})

                    finding = {
                        "resource_id": allocation_id or ip_address,
                        "resource_type": "Elastic IP",
                        "provider": "aws",
                        "region": region,
                        "issue": "Unassociated Elastic IP",
                        "monthly_cost": monthly_cost,
                        "metadata": {
                            "ip_address": ip_address,
                            "allocation_id": allocation_id,
                            "domain": addr.get("Domain", ""),
                            "tags": {t["Key"]: t["Value"] for t in addr.get("Tags", [])}
                        }
                    }
                    findings.append(finding)
                    logger.debug(
                        f"Found unassociated AWS Elastic IP: {ip_address} (Waste: ${monthly_cost:.2f}/mo)"
                    )
        except ClientError as e:
            logger.error(f"AWS Elastic IP scan failed in region {region}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error scanning AWS Elastic IP in region {region}: {e}")

        return findings

    def _scan_gcp(self, region: str) -> List[Dict[str, Any]]:
        findings = []
        try:
            addresses_client = self.gcp_client.get_addresses_client()
            project = self.gcp_client.project_id

            # aggregated_list lists external addresses in all zones/regions
            request = compute_v1.AggregatedListAddressesRequest(project=project)
            aggregated_addresses = addresses_client.aggregated_list(request=request)

            for scope, addresses_scoped_list in aggregated_addresses:
                # scope is e.g. "regions/us-central1"
                scope_region = scope.split("/")[-1]
                if scope_region != region:
                    continue

                if not addresses_scoped_list.addresses:
                    continue

                for address in addresses_scoped_list.addresses:
                    # In GCP, an unused static IP has a status of RESERVED.
                    # In-use IPs have a status of IN_USE.
                    if address.status == "RESERVED":
                        ip_address = address.address
                        address_name = address.name
                        monthly_cost = self.calculate_cost({"provider": "gcp"})

                        finding = {
                            "resource_id": address.id or address_name,
                            "resource_type": "External IP",
                            "provider": "gcp",
                            "region": region,
                            "issue": "Unused Reserved External IP",
                            "monthly_cost": monthly_cost,
                            "metadata": {
                                "name": address_name,
                                "ip_address": ip_address,
                                "status": address.status,
                                "create_time": address.creation_timestamp or ""
                            }
                        }
                        findings.append(finding)
                        logger.debug(
                            f"Found unused GCP External IP: {ip_address} (Waste: ${monthly_cost:.2f}/mo)"
                        )
        except Exception as e:
            logger.error(f"GCP External IP scan failed in region {region}: {e}")

        return findings

    def calculate_cost(self, resource: Dict[str, Any]) -> float:
        """Calculates waste cost for idle IP address."""
        provider = resource.get("provider", "aws")
        hours_per_month = 24 * 30  # 720 hours

        if provider == "aws":
            return float(self.config.pricing.aws.elastic_ip_idle_hour * hours_per_month)
        else:
            return float(self.config.pricing.gcp.external_ip_idle_hour * hours_per_month)
