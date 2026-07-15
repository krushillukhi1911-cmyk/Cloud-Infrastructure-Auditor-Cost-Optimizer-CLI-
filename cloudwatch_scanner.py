from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from app.cloud.aws_client import AWSClient
from app.cloud.gcp_client import GCPClient
from app.utils.logger import logger


class MetricScanner:
    """Queries monitoring metrics (CPU, Network) from AWS CloudWatch and GCP Monitoring."""

    def __init__(
        self,
        aws_client: Optional[AWSClient] = None,
        gcp_client: Optional[GCPClient] = None,
    ):
        self.aws_client = aws_client or AWSClient()
        self.gcp_client = gcp_client or GCPClient()

    def get_aws_ec2_cpu_average(
        self, instance_id: str, region: str, days: int = 14
    ) -> float:
        """Queries AWS CloudWatch for the average CPU utilization of an EC2 instance over N days."""
        try:
            cw = self.aws_client.get_client("cloudwatch", region_name=region)
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=days)

            response = cw.get_metric_statistics(
                Namespace="AWS/EC2",
                MetricName="CPUUtilization",
                Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600 * 24,  # Daily averages
                Statistics=["Average"],
            )

            datapoints = response.get("Datapoints", [])
            if not datapoints:
                logger.debug(f"No CPU metric datapoints found for AWS instance {instance_id}")
                return 0.0

            # Calculate the total average over all daily datapoints
            avg_cpu = sum(dp["Average"] for dp in datapoints) / len(datapoints)
            return avg_cpu
        except Exception as e:
            logger.warning(
                f"Failed to retrieve AWS CPU metrics for instance {instance_id} in {region}: {e}"
            )
            return 0.0

    def get_aws_ec2_network_total_mb(
        self, instance_id: str, region: str, days: int = 14
    ) -> float:
        """Queries AWS CloudWatch for total Network Transfer (In + Out) of an EC2 instance in MB."""
        try:
            cw = self.aws_client.get_client("cloudwatch", region_name=region)
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=days)

            total_network_bytes = 0.0

            for metric_name in ["NetworkIn", "NetworkOut"]:
                response = cw.get_metric_statistics(
                    Namespace="AWS/EC2",
                    MetricName=metric_name,
                    Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600 * 24 * days,  # Single summary datapoint for simplicity
                    Statistics=["Sum"],
                )
                datapoints = response.get("Datapoints", [])
                if datapoints:
                    total_network_bytes += sum(dp["Sum"] for dp in datapoints)

            # Convert bytes to MegaBytes
            return total_network_bytes / (1024 * 1024)
        except Exception as e:
            logger.warning(
                f"Failed to retrieve AWS Network metrics for instance {instance_id} in {region}: {e}"
            )
            return 0.0

    def get_gcp_gce_cpu_average(
        self, instance_id: str, zone: str, days: int = 14
    ) -> float:
        """Queries GCP Cloud Monitoring for average CPU utilization of a VM instance."""
        try:
            client = self.gcp_client.get_monitoring_client()
            project_id = self.gcp_client.project_id
            project_name = f"projects/{project_id}"

            now = datetime.now(timezone.utc)
            start_time = now - timedelta(days=days)

            # Define TimeInterval
            interval = monitoring_v3.TimeInterval(
                {
                    "end_time": {"seconds": int(now.timestamp())},
                    "start_time": {"seconds": int(start_time.timestamp())},
                }
            )

            # Define GCP Metric Filter
            metric_filter = (
                f'metric.type = "compute.googleapis.com/instance/cpu/utilization" '
                f'AND resource.labels.instance_id = "{instance_id}"'
            )

            # Aggregate values over the period
            aggregation = monitoring_v3.Aggregation(
                {
                    "alignment_period": {"seconds": 3600 * 24},
                    "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_MEAN,
                }
            )

            results = client.list_time_series(
                request={
                    "name": project_name,
                    "filter": metric_filter,
                    "interval": interval,
                    "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                    "aggregation": aggregation,
                }
            )

            values = []
            for result in results:
                for point in result.points:
                    # CPU Utilization metric in GCP returns decimal (e.g. 0.05 = 5%)
                    # Convert to percentage
                    values.append(point.value.double_value * 100)

            if not values:
                logger.debug(f"No CPU metric data points found for GCP instance {instance_id}")
                return 0.0

            return sum(values) / len(values)
        except Exception as e:
            logger.warning(
                f"Failed to retrieve GCP CPU metrics for instance {instance_id} in {zone}: {e}"
            )
            return 0.0

    def get_gcp_gce_network_total_mb(
        self, instance_id: str, zone: str, days: int = 14
    ) -> float:
        """Queries GCP Cloud Monitoring for total Network Transfer (In + Out) of a VM instance in MB."""
        try:
            client = self.gcp_client.get_monitoring_client()
            project_id = self.gcp_client.project_id
            project_name = f"projects/{project_id}"

            now = datetime.now(timezone.utc)
            start_time = now - timedelta(days=days)

            interval = monitoring_v3.TimeInterval(
                {
                    "end_time": {"seconds": int(now.timestamp())},
                    "start_time": {"seconds": int(start_time.timestamp())},
                }
            )

            total_bytes = 0.0
            # Query incoming and outgoing network traffic metrics
            for metric in [
                "compute.googleapis.com/instance/network/received_bytes_count",
                "compute.googleapis.com/instance/network/sent_bytes_count",
            ]:
                metric_filter = (
                    f'metric.type = "{metric}" '
                    f'AND resource.labels.instance_id = "{instance_id}"'
                )

                aggregation = monitoring_v3.Aggregation(
                    {
                        "alignment_period": {"seconds": 3600 * 24 * days},
                        "per_series_aligner": monitoring_v3.Aggregation.Aligner.ALIGN_SUM,
                    }
                )

                results = client.list_time_series(
                    request={
                        "name": project_name,
                        "filter": metric_filter,
                        "interval": interval,
                        "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
                        "aggregation": aggregation,
                    }
                )

                for result in results:
                    for point in result.points:
                        total_bytes += point.value.int64_value

            return total_bytes / (1024 * 1024)
        except Exception as e:
            logger.warning(
                f"Failed to retrieve GCP Network metrics for instance {instance_id} in {zone}: {e}"
            )
            return 0.0
