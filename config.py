import os
from pathlib import Path
from typing import List, Dict, Optional
import yaml
from pydantic import BaseModel, Field
from app.utils.exceptions import ConfigError

DEFAULT_CONFIG_PATH = Path(__file__).parents[2] / "config" / "config.yaml"


class AWSConfig(BaseModel):
    regions: List[str] = Field(default_factory=lambda: ["us-east-1"])
    assume_role_arn: Optional[str] = None
    profile_name: Optional[str] = None


class GCPConfig(BaseModel):
    regions: List[str] = Field(default_factory=lambda: ["us-central1"])
    project_id: Optional[str] = None


class CloudConfig(BaseModel):
    default_provider: str = "aws"
    aws: AWSConfig = Field(default_factory=AWSConfig)
    gcp: GCPConfig = Field(default_factory=GCPConfig)


class EC2Rules(BaseModel):
    cpu_threshold_percent: float = 5.0
    network_threshold_mbytes: float = 10.0
    observation_days: int = 14


class EBSRules(BaseModel):
    unused_days: int = 14
    large_volume_gb: int = 100


class ElasticIPRules(BaseModel):
    idle_days: int = 7


class RulesConfig(BaseModel):
    ec2: EC2Rules = Field(default_factory=EC2Rules)
    ebs: EBSRules = Field(default_factory=EBSRules)
    elastic_ip: ElasticIPRules = Field(default_factory=ElasticIPRules)


class AWSPricing(BaseModel):
    ebs_gp3_per_gb_month: float = 0.08
    ebs_gp2_per_gb_month: float = 0.10
    elastic_ip_idle_hour: float = 0.005
    ec2_estimated_monthly: Dict[str, float] = Field(default_factory=dict)


class GCPPricing(BaseModel):
    disk_pd_standard_per_gb_month: float = 0.040
    disk_pd_ssd_per_gb_month: float = 0.170
    external_ip_idle_hour: float = 0.010
    gce_estimated_monthly: Dict[str, float] = Field(default_factory=dict)


class PricingConfig(BaseModel):
    aws: AWSPricing = Field(default_factory=AWSPricing)
    gcp: GCPPricing = Field(default_factory=GCPPricing)


class AppConfig(BaseModel):
    cloud: CloudConfig = Field(default_factory=CloudConfig)
    rules: RulesConfig = Field(default_factory=RulesConfig)
    pricing: PricingConfig = Field(default_factory=PricingConfig)


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Loads configuration from a YAML file, merging environment variables if set."""
    path_to_use = config_path or os.getenv("CONFIG_PATH") or str(DEFAULT_CONFIG_PATH)

    if not os.path.exists(path_to_use):
        # Fallback if config file is not found, returning defaults
        return AppConfig()

    try:
        with open(path_to_use, "r") as f:
            data = yaml.safe_load(f) or {}
        config = AppConfig(**data)
    except Exception as e:
        raise ConfigError(f"Failed to parse configuration file at {path_to_use}: {e}")

    # Override GCP project from environment if present
    if os.getenv("GCP_PROJECT_ID"):
        config.cloud.gcp.project_id = os.getenv("GCP_PROJECT_ID")

    return config
