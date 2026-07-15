import time
from typing import Any, Optional
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from app.cloud.auth import verify_aws_session
from app.utils.exceptions import AuthenticationError, ThrottlingError
from app.utils.logger import logger

# Boto3 client configuration with native retry policy
BOTO3_CONFIG = Config(
    retries={
        "max_attempts": 5,
        "mode": "standard",  # Standard retry logic handles throttling (RateExceeded, RequestLimitExceeded)
    }
)


class AWSClient:
    """Manages AWS authentication and Boto3 client/resource lifecycle."""

    def __init__(
        self,
        profile_name: Optional[str] = None,
        role_arn: Optional[str] = None,
        region: Optional[str] = None,
    ):
        self.profile_name = profile_name
        self.role_arn = role_arn
        self.region = region
        self._session: Optional[boto3.Session] = None

    def get_session(self) -> boto3.Session:
        """Returns or creates a validated Boto3 session.

        Handles profile lookup, IAM Role assumption, and environment variables.
        """
        if self._session:
            return self._session

        try:
            # 1. Initialize base session (uses env vars or local profile)
            logger.debug(
                f"Initializing AWS Session (profile={self.profile_name or 'default'})"
            )
            session = boto3.Session(
                profile_name=self.profile_name, region_name=self.region
            )

            # 2. Assume Role if role ARN is specified
            if self.role_arn:
                logger.info(f"Assuming AWS IAM Role: {self.role_arn}")
                sts_client = session.client("sts", config=BOTO3_CONFIG)
                assumed_role = sts_client.assume_role(
                    RoleArn=self.role_arn,
                    RoleSessionName="CloudAuditorSession",
                )
                credentials = assumed_role["Credentials"]
                session = boto3.Session(
                    aws_access_key_id=credentials["AccessKeyId"],
                    aws_secret_access_key=credentials["SecretAccessKey"],
                    aws_session_token=credentials["SessionToken"],
                    region_name=self.region or session.region_name,
                )

            # Validate session credentials
            verify_aws_session(session)
            self._session = session
            return self._session

        except (BotoCoreError, ClientError) as e:
            raise AuthenticationError(f"Failed to create AWS session: {e}")

    def get_client(self, service_name: str, region_name: Optional[str] = None) -> Any:
        """Retrieves a Boto3 client for a specific service and region."""
        session = self.get_session()
        region = region_name or self.region or session.region_name
        return session.client(
            service_name, region_name=region, config=BOTO3_CONFIG
        )

    def get_resource(self, service_name: str, region_name: Optional[str] = None) -> Any:
        """Retrieves a Boto3 resource for a specific service and region."""
        session = self.get_session()
        region = region_name or self.region or session.region_name
        return session.resource(
            service_name, region_name=region, config=BOTO3_CONFIG
        )

    @staticmethod
    def handle_client_error(e: ClientError) -> Exception:
        """Helper to map Boto3 ClientError to custom exceptions."""
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code in ["Throttling", "RequestLimitExceeded", "ProvisionedThroughputExceededException"]:
            return ThrottlingError(f"AWS API Throttling encountered: {e}")
        return e
