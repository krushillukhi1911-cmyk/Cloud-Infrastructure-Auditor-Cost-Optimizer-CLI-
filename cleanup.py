import typer
from typing import Any, Dict, List
from botocore.exceptions import ClientError
from google.cloud import compute_v1
from app.cloud.aws_client import AWSClient
from app.cloud.gcp_client import GCPClient
from app.utils.logger import logger


class CleanupManager:
    """Manages the deletion or suspension of wasteful cloud resources."""

    def __init__(
        self,
        aws_client: AWSClient = None,
        gcp_client: GCPClient = None,
    ):
        self.aws_client = aws_client or AWSClient()
        self.gcp_client = gcp_client or GCPClient()

    def execute_cleanup(
        self, findings: List[Dict[str, Any]], dry_run: bool = True
    ) -> List[Dict[str, Any]]:
        """Iterates through findings and cleans up resources.

        If dry_run is True, actions are logged but not executed.
        """
        results = []
        if dry_run:
            logger.info("[yellow]DRY-RUN MODE ENABLED. No changes will be applied.[/yellow]")

        for finding in findings:
            provider = finding.get("provider", "aws").lower()
            resource_id = finding.get("resource_id")
            resource_type = finding.get("resource_type")
            region = finding.get("region")
            metadata = finding.get("metadata", {})

            action_status = "Skipped (Dry Run)" if dry_run else "Pending"
            error_message = None

            logger.info(
                f"Cleaning up {resource_type} '{resource_id}' in {provider.upper()} ({region})..."
            )

            if not dry_run:
                try:
                    if provider == "aws":
                        self._cleanup_aws(resource_type, resource_id, region, metadata)
                    elif provider == "gcp":
                        self._cleanup_gcp(resource_type, resource_id, region, metadata)
                    action_status = "Success"
                    logger.info(f"[green]Successfully cleaned up {resource_type} {resource_id}[/green]")
                except Exception as e:
                    action_status = "Failed"
                    error_message = str(e)
                    logger.error(f"[red]Failed to clean up {resource_type} {resource_id}: {e}[/red]")

            results.append(
                {
                    "resource_id": resource_id,
                    "resource_type": resource_type,
                    "provider": provider,
                    "region": region,
                    "action_status": action_status,
                    "error": error_message,
                }
            )

        return results

    def _cleanup_aws(
        self, resource_type: str, resource_id: str, region: str, metadata: Dict[str, Any]
    ) -> None:
        """Deletes/releases AWS resources."""
        if "EBS" in resource_type:
            ec2_resource = self.aws_client.get_resource("ec2", region_name=region)
            volume = ec2_resource.Volume(resource_id)
            volume.delete()
        elif "Elastic IP" in resource_type:
            ec2_client = self.aws_client.get_client("ec2", region_name=region)
            # Allocation ID is preferred for VPC, otherwise PublicIp
            allocation_id = metadata.get("allocation_id")
            if allocation_id:
                ec2_client.release_address(AllocationId=allocation_id)
            else:
                ip_address = metadata.get("ip_address", resource_id)
                ec2_client.release_address(PublicIp=ip_address)
        elif "EC2 Instance" in resource_type:
            ec2_resource = self.aws_client.get_resource("ec2", region_name=region)
            instance = ec2_resource.Instance(resource_id)
            rec = metadata.get("recommendation", "")
            if "Stop" in rec:
                logger.info(f"Stopping AWS EC2 instance {resource_id}")
                instance.stop()
            else:
                logger.info(f"Terminating AWS EC2 instance {resource_id}")
                instance.terminate()
        else:
            raise NotImplementedError(f"Cleanup for AWS {resource_type} is not implemented")

    def _cleanup_gcp(
        self, resource_type: str, resource_id: str, region: str, metadata: Dict[str, Any]
    ) -> None:
        """Deletes/releases GCP resources."""
        project = self.gcp_client.project_id

        if "Persistent Disk" in resource_type:
            disks_client = self.gcp_client.get_disks_client()
            zone = metadata.get("zone")
            if not zone:
                raise ValueError(f"Zone metadata missing for GCP Disk {resource_id}")
            # delete returns an Operation object
            operation = disks_client.delete(project=project, zone=zone, disk=resource_id)
            logger.debug(f"GCP Disk deletion operation started: {operation.name}")
        elif "External IP" in resource_type:
            addresses_client = self.gcp_client.get_addresses_client()
            address_name = metadata.get("name", resource_id)
            operation = addresses_client.delete(project=project, region=region, address=address_name)
            logger.debug(f"GCP Address deletion operation started: {operation.name}")
        elif "GCE Instance" in resource_type:
            instances_client = self.gcp_client.get_instances_client()
            zone = metadata.get("zone")
            if not zone:
                raise ValueError(f"Zone metadata missing for GCP Instance {resource_id}")
            rec = metadata.get("recommendation", "")
            if "Stop" in rec:
                logger.info(f"Stopping GCP VM instance {resource_id}")
                operation = instances_client.stop(project=project, zone=zone, instance=resource_id)
            else:
                logger.info(f"Deleting GCP VM instance {resource_id}")
                operation = instances_client.delete(project=project, zone=zone, instance=resource_id)
            logger.debug(f"GCP Instance operation started: {operation.name}")
        else:
            raise NotImplementedError(f"Cleanup for GCP {resource_type} is not implemented")
