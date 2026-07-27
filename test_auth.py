import pytest
import boto3
from moto import mock_aws
from app.cloud.auth import verify_aws_session, verify_gcp_credentials
from app.cloud.aws_client import AWSClient
from app.utils.exceptions import AuthenticationError


@mock_aws
def test_verify_aws_session_success():
    # Moto mocks STS backend, so it returns standard caller identity.
    session = boto3.Session(
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        region_name="us-east-1",
    )
    account_id = verify_aws_session(session)
    assert account_id == "123456789012"


def test_verify_aws_session_failure():
    # Pass a session with non-working config to trigger failure
    session = boto3.Session(
        aws_access_key_id="",
        aws_secret_access_key="",
        region_name="us-east-1",
    )
    # Patch get_caller_identity to raise ClientError or let standard Boto3 error out
    # Since credentials are empty, botocore raises exception
    with pytest.raises(AuthenticationError):
        verify_aws_session(session)


@mock_aws
def test_aws_client_session_creation():
    client = AWSClient(profile_name=None, region="us-east-1")
    session = client.get_session()
    assert session is not None
    assert session.region_name == "us-east-1"


@mock_aws
def test_aws_client_assume_role():
    client = AWSClient(
        region="us-east-1", role_arn="arn:aws:iam::123456789012:role/MockAuditorRole"
    )
    session = client.get_session()
    assert session is not None
    # Check that temporary credentials from AssumeRole are loaded
    creds = session.get_credentials()
    assert creds.access_key.startswith("ASIA")  # Assumed role credentials prefix in AWS
