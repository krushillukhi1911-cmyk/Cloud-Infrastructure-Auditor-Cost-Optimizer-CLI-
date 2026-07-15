from typing import Any, Dict, List
from botocore.exceptions import ClientError
from google.cloud import compute_v1
from app.cloud.aws_client import AWSClient
from app.cloud.gcp_client import GCPClient
from app.scanners.base_scanner import BaseScanner
from app.scanners.cloudwatch_scanner import MetricScanner
from app.utils.config import AppConfig
from app.utils.helpers import get_aws_tag_value, get_gcp_label_value
from app.utils.logger import logger


class EC2Scanner(BaseScanner):
    """Scans for running but underutilized AWS EC2 and GCP GCE instances."""

    def __init__(
        self,
        config: AppConfig,
        aws_client: AWSClient = None,
        gcp_client: GCPClient = None,
        metric_scanner: MetricScanner = None,
    ):
        super().__init__(config)
        self.aws_client = aws_client or AWSClient()
        self.gcp_client = gcp_client or GCPClient()
        self.metric_scanner = metric_scanner or MetricScanner(
            aws_client=self.aws_client, gcp_client=self.gcp_client
        )

    def scan(self, provider: str, region: str) -> List[Dict[str, Any]]:
        """Scans for idle/underutilized instances in the specified provider and region."""
        logger.info(f"Scanning for idle instances in {provider.upper()} ({region})")
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
            # Only analyze running instances
            response = ec2_client.describe_instances(
                Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
            )

            rules = self.config.rules.ec2
            observation_days = rules.observation_days
            cpu_threshold = rules.cpu_threshold_percent
            network_threshold = rules.network_threshold_mbytes

            for reservation in response.get("Reservations", []):
                for inst in reservation.get("Instances", []):
                    instance_id = inst["InstanceId"]
                    instance_type = inst["InstanceType"]
                    instance_name = get_aws_tag_value(inst.get("Tags"), "Name") or instance_id

                    # Retrieve metrics
                    avg_cpu = self.metric_scanner.get_aws_ec2_cpu_average(
                        instance_id, region, days=observation_days
                    )
                    total_net = self.metric_scanner.get_aws_ec2_network_total_mb(
                        instance_id, region, days=observation_days
                    )

                    # Determine if underutilized
                    is_idle = avg_cpu < cpu_threshold and total_net < network_threshold

                    if is_idle:
                        monthly_cost = self.calculate_cost({
                            "provider": "aws",
                            "instance_type": instance_type
                        })

                        # Determine recommendation
                        if avg_cpu < 1.0 and total_net < 1.0:
                            recommendation = "Stop or Delete Instance"
                        else:
                            recommendation = "Resize Instance (Downsize)"

                        finding = {
                            "resource_id": instance_id,
                            "resource_type": "EC2 Instance",
                            "provider": "aws",
                            "region": region,
                            "issue": f"Idle EC2 Instance (Avg CPU: {avg_cpu:.1f}%, Net: {total_net:.1f}MB)",
                            "monthly_cost": monthly_cost,
                            "metadata": {
                                "name": instance_name,
                                "instance_type": instance_type,
                                "avg_cpu_percent": avg_cpu,
                                "network_usage_mb": total_net,
                                "recommendation": recommendation,
                                "launch_time": inst["LaunchTime"].isoformat() if "LaunchTime" in inst else "",
                                "tags": {t["Key"]: t["Value"] for t in inst.get("Tags", [])}
                            }
                        }
                        findings.append(finding)
                        logger.debug(
                            f"Found idle AWS instance: {instance_id} (CPU: {avg_cpu:.1f}%, Waste: ${monthly_cost:.2f}/mo)"
                        )
        except ClientError as e:
            logger.error(f"AWS EC2 scan failed in region {region}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error scanning AWS EC2 in region {region}: {e}")

        return findings

    def _scan_gcp(self, region: str) -> List[Dict[str, Any]]:
        findings = []
        try:
            instances_client = self.gcp_client.get_instances_client()
            project = self.gcp_client.project_id

            request = compute_v1.AggregatedListInstancesRequest(project=project)
            aggregated_instances = instances_client.aggregated_list(request=request)

            rules = self.config.rules.ec2
            observation_days = rules.observation_days
            cpu_threshold = rules.cpu_threshold_percent
            network_threshold = rules.network_threshold_mbytes

            for zone_path, instances_scoped_list in aggregated_instances:
                zone = zone_path.split("/")[-1]
                if not zone.startswith(region):
                    continue

                if not instances_scoped_list.instances:
                    continue

                for inst in instances_scoped_list.instances:
                    # GCE status: RUNNING, TERMINATED, etc. We scan RUNNING
                    if inst.status != "RUNNING":
                        continue

                    instance_id = str(inst.id)
                    instance_name = inst.name
                    machine_type_short = inst.machine_type.split("/")[-1] if inst.machine_type else "e2-medium"

                    # Retrieve metrics
                    avg_cpu = self.metric_scanner.get_gcp_gce_cpu_average(
                        instance_id, zone, days=observation_days
                    )
                    total_net = self.metric_scanner.get_gcp_gce_network_total_mb(
                        instance_id, zone, days=observation_days
                    )

                    is_idle = avg_cpu < cpu_threshold and total_net < network_threshold

                    if is_idle:
                        monthly_cost = self.calculate_cost({
                            "provider": "gcp",
                            "instance_type": machine_type_short
                        })

                        if avg_cpu < 1.0 and total_net < 1.0:
                            recommendation = "Stop or Delete Instance"
                        else:
                            recommendation = "Resize Instance (Downsize)"

                        finding = {
                            "resource_id": instance_name,  # Using name as resource_id for easier GCE API deletion
                            "resource_type": "GCE Instance",
                            "provider": "gcp",
                            "region": region,
                            "issue": f"Idle GCE Instance (Avg CPU: {avg_cpu:.1f}%, Net: {total_net:.1f}MB)",
                            "monthly_cost": monthly_cost,
                            "metadata": {
                                "name": instance_name,
                                "instance_id": instance_id,
                                "instance_type": machine_type_short,
                                "zone": zone,
                                "avg_cpu_percent": avg_cpu,
                                "network_usage_mb": total_net,
                                "recommendation": recommendation,
                                "create_time": inst.creation_timestamp or "",
                                "labels": dict(inst.labels) if inst.labels else {}
                            }
                        }
                        findings.append(finding)
                        logger.debug(
                            f"Found idle GCP instance: {instance_name} (CPU: {avg_cpu:.1f}%, Waste: ${monthly_cost:.2f}/mo)"
                        )
        except Exception as e:
            logger.error(f"GCP GCE scan failed in region {region}: {e}")

        return findings

    def calculate_cost(self, resource: Dict[str, Any]) -> float:
        """Calculates waste cost for running instance."""
        provider = resource.get("provider", "aws")
        inst_type = resource.get("instance_type", "")

        if provider == "aws":
            rates = self.config.pricing.aws
            return float(rates.ec2_estimated_monthly.get(inst_type, rates.ec2_estimated_monthly.get("default_fallback", 50.0)))
        else:
            rates = self.config.pricing.gcp
            return float(rates.gce_estimated_monthly.get(inst_type, rates.gce_estimated_monthly.get("default_fallback", 40.0)))
