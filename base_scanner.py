from abc import ABC, abstractmethod
from typing import Dict, List, Any
from app.utils.config import AppConfig


class BaseScanner(ABC):
    """Abstract base class for cloud resource scanners."""

    def __init__(self, config: AppConfig):
        self.config = config

    @abstractmethod
    def scan(self, provider: str, region: str) -> List[Dict[str, Any]]:
        """Scans resources for the given cloud provider and region.

        Returns:
            List of findings. Each finding is a dictionary containing:
                - resource_id (str): Unique ID of the resource
                - resource_type (str): Type of resource (e.g. EBS, ElasticIP, EC2)
                - provider (str): 'aws' or 'gcp'
                - region (str): Cloud region scanned
                - issue (str): Problem description (e.g. "Unattached Volume")
                - monthly_cost (float): Estimated monthly waste
                - metadata (dict): Additional resource attributes (name, tags, size, etc.)
        """
        pass

    @abstractmethod
    def calculate_cost(self, resource: Dict[str, Any]) -> float:
        """Calculates estimated monthly cost waste of the resource."""
        pass
