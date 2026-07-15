from typing import Any, Dict, List
from botocore.exceptions import ClientError
from google.cloud import compute_v1
from app.cloud.aws_client import AWSClient
from app.cloud.gcp_client import GCPClient
from app.scanners.base_scanner import BaseScanner
from app.utils.config import AppConfig
from app.utils.helpers import get_aws_tag_value, get_gcp_label_value
from app.utils.logger import logger


class EBSScanner(BaseScanner):
    """Scans for unattached AWS EBS volumes and GCP Persistent Disks."""

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
        """Scans for unattached disks/volumes in the specified provider and region."""
        logger.info(f"Scanning for unattached storage in {provider.upper()} ({region})")
        findings = []

        if provider.lower() == "aws":
            findings.extend(self._scan_aws(region))
        elif provider.lower() == "gcp":
            findings.extend(self._scan_gcp(region))

        return findings

    def _scan_aws(self, region: str) -> List[Dict[str, Any]]:
        findings = []
        try:
            # We fetch using the ec2 resource
            ec2 = self.aws_client.get_resource("ec2", region_name=region)
            # Filter for volumes that are "available" (i.e. unattached)
            volumes = ec2.volumes.filter(
                Filters=[{"Name": "status", "Values": ["available"]}]
            )

            for volume in volumes:
                volume_name = get_aws_tag_value(volume.tags, "Name") or volume.id
                monthly_cost = self.calculate_cost({
                    "provider": "aws",
                    "size": volume.size,
                    "volume_type": volume.volume_type
                })

                finding = {
                    "resource_id": volume.id,
                    "resource_type": "EBS",
                    "provider": "aws",
                    "region": region,
                    "issue": "Unattached EBS Volume",
                    "monthly_cost": monthly_cost,
                    "metadata": {
                        "name": volume_name,
                        "size_gb": volume.size,
                        "volume_type": volume.volume_type,
                        "create_time": volume.create_time.isoformat() if volume.create_time else "",
                        "tags": {t["Key"]: t["Value"] for t in volume.tags} if volume.tags else {}
                    }
                }
                findings.append(finding)
                logger.debug(f"Found unattached AWS volume: {volume.id} (Size: {volume.size}GB, Waste: ${monthly_cost:.2f}/mo)")
        except ClientError as e:
            logger.error(f"AWS EBS scan failed in region {region}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error scanning AWS EBS in region {region}: {e}")

        return findings

    def _scan_gcp(self, region: str) -> List[Dict[str, Any]]:
        findings = []
        try:
            disks_client = self.gcp_client.get_disks_client()
            project = self.gcp_client.project_id

            # aggregated_list returns items by zone.
            # Filters can't easily query users list, so we query aggregated disks and filter in memory.
            request = compute_v1.AggregatedListDisksRequest(project=project)
            aggregated_disks = disks_client.aggregated_list(request=request)

            for zone_path, disks_scoped_list in aggregated_disks:
                # zone_path is e.g. "zones/us-central1-a"
                zone = zone_path.split("/")[-1]
                # Filter zone disks that match the requested region
                if not zone.startswith(region):
                    continue

                if not disks_scoped_list.disks:
                    continue

                for disk in disks_scoped_list.disks:
                    # An unattached disk has no 'users' list (i.e. no instance is using it)
                    if not disk.users:
                        disk_name = disk.name
                        disk_type_short = disk.type_.split("/")[-1] if disk.type_ else "pd-standard"
                        monthly_cost = self.calculate_cost({
                            "provider": "gcp",
                            "size": disk.size_gb,
                            "volume_type": disk_type_short
                        })

                        finding = {
                            "resource_id": disk.name,
                            "resource_type": "Persistent Disk",
                            "provider": "gcp",
                            "region": region,
                            "issue": "Unattached Persistent Disk",
                            "monthly_cost": monthly_cost,
                            "metadata": {
                                "name": disk_name,
                                "size_gb": disk.size_gb,
                                "volume_type": disk_type_short,
                                "zone": zone,
                                "create_time": disk.creation_timestamp or "",
                                "labels": dict(disk.labels) if disk.labels else {}
                            }
                        }
                        findings.append(finding)
                        logger.debug(f"Found unattached GCP disk: {disk_name} (Size: {disk.size_gb}GB, Waste: ${monthly_cost:.2f}/mo)")
        except Exception as e:
            logger.error(f"GCP Disk scan failed in region {region}: {e}")

        return findings

    def calculate_cost(self, resource: Dict[str, Any]) -> float:
        """Calculates waste cost for storage."""
        provider = resource.get("provider", "aws")
        size = resource.get("size", 0)
        vol_type = resource.get("volume_type", "")

        if provider == "aws":
            rates = self.config.pricing.aws
            # Use gp3/gp2 rates or fallback
            rate = rates.ebs_gp3_per_gb_month if "gp3" in vol_type.lower() else rates.ebs_gp2_per_gb_month
            return float(size * rate)
        else:
            rates = self.config.pricing.gcp
            rate = rates.disk_pd_ssd_per_gb_month if "ssd" in vol_type.lower() or "ssd" in vol_type.split("-") else rates.disk_pd_standard_per_gb_month
            return float(size * rate)
