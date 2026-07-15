import boto3
from botocore.exceptions import BotoCoreError, ClientError
from google.auth import default
from google.auth.exceptions import DefaultCredentialsError
from app.utils.exceptions import AuthenticationError
from app.utils.logger import logger


def verify_aws_session(session: boto3.Session) -> str:
    """Verifies that an AWS session is authenticated by fetching caller identity.

    Returns the AWS Account ID if successful.
    """
    try:
        sts = session.client("sts")
        caller_identity = sts.get_caller_identity()
        account_id = caller_identity.get("Account")
        logger.debug(f"AWS Authenticated. Account ID: {account_id}")
        return account_id
    except (BotoCoreError, ClientError) as e:
        raise AuthenticationError(f"Failed to authenticate with AWS: {e}")


def verify_gcp_credentials() -> str:
    """Verifies GCP authentication by resolving Google Application Default Credentials (ADC).

    Returns the GCP Project ID if successful.
    """
    try:
        credentials, project_id = default()
        if not project_id:
            raise AuthenticationError(
                "GCP Project ID could not be determined. "
                "Set GCP_PROJECT_ID environment variable or specify in config."
            )
        logger.debug(f"GCP Authenticated. Project ID: {project_id}")
        return project_id
    except DefaultCredentialsError as e:
        raise AuthenticationError(f"Failed to authenticate with GCP: {e}")
