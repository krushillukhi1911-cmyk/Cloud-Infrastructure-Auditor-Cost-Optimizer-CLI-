import pytest
import boto3
from unittest.mock import MagicMock
from moto import mock_aws
from app.utils.config import load_config
from app.scanners.ec2_scanner import EC2Scanner


@mock_aws
def test_ec2_scanner_aws_flags_idle_instance():
    # Setup mock AWS EC2 instance
    ec2_res = boto3.resource("ec2", region_name="us-east-1")
    # We must first launch an instance in Moto
    # To launch an instance, we need an AMI. Moto mocks AMIs as well.
    instance = ec2_res.create_instances(
        ImageId="ami-12345678",
        MinCount=1,
        MaxCount=1,
        InstanceType="t2.micro",
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": "test-idle-instance"}],
            }
        ],
    )[0]

    config = load_config()

    # Create a mock MetricScanner that returns low CPU and network usage
    mock_metrics = MagicMock()
    mock_metrics.get_aws_ec2_cpu_average.return_value = 0.5  # Below 1.0% stop threshold
    mock_metrics.get_aws_ec2_network_total_mb.return_value = 0.2  # Below 1.0MB stop threshold

    scanner = EC2Scanner(config, metric_scanner=mock_metrics)
    findings = scanner.scan("aws", "us-east-1")

    assert len(findings) >= 1
    found_ids = [f["resource_id"] for f in findings]
    assert instance.id in found_ids

    target_finding = next(f for f in findings if f["resource_id"] == instance.id)
    assert target_finding["resource_type"] == "EC2 Instance"
    assert target_finding["monthly_cost"] == 8.5  # t2.micro default monthly cost
    assert "Stop or Delete" in target_finding["metadata"]["recommendation"]


def test_ec2_scanner_gcp_flags_idle_instance():
    config = load_config()

    # Mock GCP client and subclients
    mock_gcp = MagicMock()
    mock_instances_client = MagicMock()
    mock_gcp.get_instances_client.return_value = mock_instances_client
    mock_gcp.project_id = "test-project"

    # Mock GCE instance
    mock_instance = MagicMock()
    mock_instance.id = 11111
    mock_instance.name = "test-gce-vm"
    mock_instance.status = "RUNNING"
    mock_instance.machine_type = "zones/us-central1-a/machineTypes/f1-micro"
    mock_instance.creation_timestamp = "2026-07-13T10:00:00.000-07:00"
    mock_instance.labels = {"team": "dev"}

    mock_scoped_list = MagicMock()
    mock_scoped_list.instances = [mock_instance]

    # aggregated_list returns (zone, scoped_list)
    mock_instances_client.aggregated_list.return_value = [
        ("zones/us-central1-a", mock_scoped_list)
    ]

    # Mock metrics
    mock_metrics = MagicMock()
    mock_metrics.get_gcp_gce_cpu_average.return_value = 0.5
    mock_metrics.get_gcp_gce_network_total_mb.return_value = 0.2

    scanner = EC2Scanner(config, gcp_client=mock_gcp, metric_scanner=mock_metrics)
    findings = scanner.scan("gcp", "us-central1")

    assert len(findings) == 1
    assert findings[0]["resource_id"] == "test-gce-vm"
    assert findings[0]["monthly_cost"] == 5.0  # f1-micro monthly cost
    assert "Stop or Delete" in findings[0]["metadata"]["recommendation"]
