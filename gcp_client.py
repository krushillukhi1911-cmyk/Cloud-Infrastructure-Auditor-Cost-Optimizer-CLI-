import os
from typing import Any, Optional
from google.auth import default
from google.auth.credentials import Credentials
from google.auth.exceptions import DefaultCredentialsError
from google.oauth2 import service_account
from google.cloud import compute_v1
from google.cloud import monitoring_v3
from app.utils.exceptions import AuthenticationError
from app.utils.logger import logger


class GCPClient:
    """Manages GCP credentials, Project ID resolution, and client instances."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        credentials_path: Optional[str] = None,
    ):
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        self.credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self._credentials: Optional[Credentials] = None

    def get_credentials(self) -> Credentials:
        """Resolves GCP Credentials from path or defaults (ADC)."""
        if self._credentials:
            return self._credentials

        try:
            if self.credentials_path and os.path.exists(self.credentials_path):
                logger.info(
                    f"Loading GCP Service Account credentials from: {self.credentials_path}"
                )
                self._credentials = service_account.Credentials.from_service_account_file(
                    self.credentials_path
                )
                # Parse project_id from SA if not explicitly specified
                if not self.project_id:
                    import json
                    with open(self.credentials_path, "r") as f:
                        info = json.load(f)
                        self.project_id = info.get("project_id")
            else:
                logger.debug("Attempting to load Google Default Credentials (ADC)")
                credentials, resolved_project = default()
                self._credentials = credentials
                if not self.project_id:
                    self.project_id = resolved_project

            if not self.project_id:
                raise AuthenticationError(
                    "GCP project ID could not be identified. "
                    "Ensure GCP_PROJECT_ID environment variable is set."
                )

            return self._credentials
        except DefaultCredentialsError as e:
            raise AuthenticationError(f"Failed to authenticate GCP client: {e}")

    def get_instances_client(self) -> compute_v1.InstancesClient:
        """Returns the GCP Compute Instances client."""
        return compute_v1.InstancesClient(credentials=self.get_credentials())

    def get_disks_client(self) -> compute_v1.DisksClient:
        """Returns the GCP Compute Disks (volume) client."""
        return compute_v1.DisksClient(credentials=self.get_credentials())

    def get_addresses_client(self) -> compute_v1.AddressesClient:
        """Returns the GCP Compute External Addresses (EIP) client."""
        return compute_v1.AddressesClient(credentials=self.get_credentials())

    def get_monitoring_client(self) -> monitoring_v3.MetricServiceClient:
        """Returns the GCP Monitoring Client."""
        return monitoring_v3.MetricServiceClient(credentials=self.get_credentials())
