import pytest
import boto3
from unittest.mock import MagicMock
from moto import mock_aws
from app.utils.config import load_config
from app.cloud.aws_client import AWSClient
from app.scanners.ebs_scanner import EBSScanner
from app.scanners.elastic_ip_scanner import ElasticIPScanner


@mock_aws
def test_ebs_scanner_aws_finds_unattached_volumes():
    # Setup mock AWS resource
    ec2_res = boto3.resource("ec2", region_name="us-east-1")

    # Create unattached volume (status: available)
    volume_unattached = ec2_res.create_volume(
        AvailabilityZone="us-east-1a",
        Size=80,
        VolumeType="gp3",
        TagSpecifications=[
            {
                "ResourceType": "volume",
                "Tags": [{"Key": "Name", "Value": "test-unattached-vol"}],
            }
        ],
    )

    # Create an attached volume (needs an instance to attach to)
    # We don't necessarily need to attach it in Moto unless we verify filtering.
    # By default, creating a volume makes it available. If we create an instance and attach it:
    # Let's verify that a standard unattached volume is flagged:
    config = load_config()
    scanner = EBSScanner(config)
    findings = scanner.scan("aws", "us-east-1")

    assert len(findings) >= 1
    # Check that volume_unattached.id is in findings
    found_ids = [f["resource_id"] for f in findings]
    assert volume_unattached.id in found_ids

    # Verify findings details
    target_finding = next(f for f in findings if f["resource_id"] == volume_unattached.id)
    assert target_finding["resource_type"] == "EBS"
    assert target_finding["monthly_cost"] == 80 * 0.08  # 80 GB * gp3 rate 0.08
    assert target_finding["metadata"]["name"] == "test-unattached-vol"


def test_ebs_scanner_gcp_finds_unattached_disks():
    config = load_config()

    # Create mock GCP Client and compute clients
    mock_gcp = MagicMock()
    mock_disks_client = MagicMock()
    mock_gcp.get_disks_client.return_value = mock_disks_client
    mock_gcp.project_id = "test-project"

    # Mock response for aggregated_list
    mock_disk = MagicMock()
    mock_disk.id = 99999
    mock_disk.name = "test-gcp-disk"
    mock_disk.size_gb = 200
    mock_disk.type_ = "zones/us-central1-a/diskTypes/pd-standard"
    mock_disk.users = []  # Empty users list = unattached!
    mock_disk.creation_timestamp = "2026-07-13T10:00:00.000-07:00"
    mock_disk.labels = {"env": "prod"}

    mock_scoped_list = MagicMock()
    mock_scoped_list.disks = [mock_disk]

    # aggregated_list returns iterator of (zone, scoped_list)
    mock_disks_client.aggregated_list.return_value = [
        ("zones/us-central1-a", mock_scoped_list)
    ]

    scanner = EBSScanner(config, gcp_client=mock_gcp)
    findings = scanner.scan("gcp", "us-central1")

    assert len(findings) == 1
    assert findings[0]["resource_id"] == "test-gcp-disk"
    assert findings[0]["monthly_cost"] == 200 * 0.04  # 200 GB * pd-standard 0.04
    assert findings[0]["metadata"]["volume_type"] == "pd-standard"


@mock_aws
def test_elastic_ip_scanner_aws_finds_unused():
    ec2_client = boto3.client("ec2", region_name="us-east-1")
    addr = ec2_client.allocate_address(Domain="vpc")

    config = load_config()
    aws_client = AWSClient(region="us-east-1")
    scanner = ElasticIPScanner(config, aws_client=aws_client)
    findings = scanner.scan("aws", "us-east-1")

    assert len(findings) >= 1
    found_ids = [f["resource_id"] for f in findings]
    assert addr["AllocationId"] in found_ids

    target = next(f for f in findings if f["resource_id"] == addr["AllocationId"])
    assert target["resource_type"] == "Elastic IP"
    assert target["monthly_cost"] == pytest.approx(0.005 * 24 * 30)


def test_elastic_ip_scanner_gcp_finds_unused():
    config = load_config()
    mock_gcp = MagicMock()
    mock_addr_client = MagicMock()
    mock_gcp.get_addresses_client.return_value = mock_addr_client
    mock_gcp.project_id = "test-project"

    mock_address = MagicMock()
    mock_address.id = 77777
    mock_address.name = "test-gcp-ip"
    mock_address.address = "35.192.0.1"
    mock_address.status = "RESERVED"  # Reserved but unused
    mock_address.creation_timestamp = "2026-07-13T10:00:00.000-07:00"

    mock_scoped_list = MagicMock()
    mock_scoped_list.addresses = [mock_address]

    mock_addr_client.aggregated_list.return_value = [
        ("regions/us-central1", mock_scoped_list)
    ]

    scanner = ElasticIPScanner(config, gcp_client=mock_gcp)
    findings = scanner.scan("gcp", "us-central1")

    assert len(findings) == 1
    assert findings[0]["resource_id"] == 77777
    assert findings[0]["metadata"]["ip_address"] == "35.192.0.1"
    assert findings[0]["monthly_cost"] == pytest.approx(0.010 * 24 * 30)

