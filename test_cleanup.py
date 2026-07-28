import pytest
import boto3
from unittest.mock import MagicMock
from moto import mock_aws
from app.optimizer.cleanup import CleanupManager
from app.utils.exceptions import CleanupError
from app.optimizer.cost_analyzer import CostAnalyzer
from app.optimizer.recommendations import generate_recommendations_summary
from app.reports.json_report import export_json_report
from app.reports.csv_report import export_csv_report
from app.utils.config import load_config


@mock_aws
def test_cleanup_aws_ebs_dry_run_and_execution():
    ec2_res = boto3.resource("ec2", region_name="us-east-1")
    volume = ec2_res.create_volume(AvailabilityZone="us-east-1a", Size=10)

    findings = [
        {
            "resource_id": volume.id,
            "resource_type": "EBS Volume",
            "provider": "aws",
            "region": "us-east-1",
            "issue": "Unattached Volume",
            "monthly_cost": 0.8,
            "metadata": {},
        }
    ]

    cleanup_mgr = CleanupManager()

    # Test Dry Run
    dry_results = cleanup_mgr.execute_cleanup(findings, dry_run=True)
    assert len(dry_results) == 1
    assert dry_results[0]["action_status"] == "Skipped (Dry Run)"

    # Volume should still exist
    volume.reload()
    assert volume.state == "available"

    # Test Real Cleanup Execution
    exec_results = cleanup_mgr.execute_cleanup(findings, dry_run=False)
    assert len(exec_results) == 1
    assert exec_results[0]["action_status"] == "Success"

    # Volume should be deleted (reloading raises ClientError: InvalidVolume.NotFound)
    with pytest.raises(Exception) as exc:
        volume.reload()
    assert "InvalidVolume.NotFound" in str(exc.value)


@mock_aws
def test_cleanup_aws_ec2_stop():
    ec2_res = boto3.resource("ec2", region_name="us-east-1")
    instance = ec2_res.create_instances(
        ImageId="ami-12345678", MinCount=1, MaxCount=1, InstanceType="t2.micro"
    )[0]

    # Instance starts in 'pending' or 'running' state
    assert instance.state["Name"] in ["pending", "running"]

    findings = [
        {
            "resource_id": instance.id,
            "resource_type": "EC2 Instance",
            "provider": "aws",
            "region": "us-east-1",
            "issue": "Idle Instance",
            "monthly_cost": 8.5,
            "metadata": {"recommendation": "Stop Instance"},
        }
    ]

    cleanup_mgr = CleanupManager()
    exec_results = cleanup_mgr.execute_cleanup(findings, dry_run=False)

    assert exec_results[0]["action_status"] == "Success"
    instance.reload()
    # The state should transition to stopping/stopped
    assert instance.state["Name"] in ["stopping", "stopped"]


def test_cleanup_gcp_disk():
    # Mock GCP client
    mock_gcp = MagicMock()
    mock_disks_client = MagicMock()
    mock_gcp.get_disks_client.return_value = mock_disks_client
    mock_gcp.project_id = "test-project"

    findings = [
        {
            "resource_id": "test-gcp-disk",
            "resource_type": "Persistent Disk",
            "provider": "gcp",
            "region": "us-central1",
            "issue": "Unattached Disk",
            "monthly_cost": 5.0,
            "metadata": {"zone": "us-central1-a"},
        }
    ]

    cleanup_mgr = CleanupManager(gcp_client=mock_gcp)
    exec_results = cleanup_mgr.execute_cleanup(findings, dry_run=False)

    assert exec_results[0]["action_status"] == "Success"
    mock_disks_client.delete.assert_called_once_with(
        project="test-project", zone="us-central1-a", disk="test-gcp-disk"
    )


def test_recommendations_and_cost_analyzer_logic(tmp_path):
    config = load_config()
    analyzer = CostAnalyzer(config)

    # Mock the scanners to return predefined findings
    mock_ebs_scanner = MagicMock()
    mock_ebs_scanner.scan.return_value = [
        {
            "resource_id": "vol-12345",
            "resource_type": "EBS Volume",
            "provider": "aws",
            "region": "us-east-1",
            "issue": "Unattached Volume",
            "monthly_cost": 25.0,
            "metadata": {}
        }
    ]
    mock_ip_scanner = MagicMock()
    mock_ip_scanner.scan.return_value = []
    mock_ec2_scanner = MagicMock()
    mock_ec2_scanner.scan.return_value = []

    analyzer.scanners = [mock_ebs_scanner, mock_ip_scanner, mock_ec2_scanner]
    results = analyzer.analyze("aws", ["us-east-1"])

    assert results["total_resources"] == 1
    assert results["monthly_savings"] == 25.0
    assert results["yearly_savings"] == 300.0

    # Test recommendations summary generator
    summary_text = generate_recommendations_summary(results["findings"])
    assert "EBS Volume" in summary_text
    assert "vol-12345" in summary_text
    assert "$25.00" in summary_text

    # Test exports
    json_out = tmp_path / "report.json"
    csv_out = tmp_path / "report.csv"

    export_json_report(results, str(json_out))
    export_csv_report(results, str(csv_out))

    assert json_out.exists()
    assert csv_out.exists()

