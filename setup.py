from setuptools import setup, find_packages

setup(
    name="cloud-auditor",
    version="1.0.0",
    description="Cloud Infrastructure Auditor & Cost Optimizer CLI",
    author="FinOps Architect",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "typer[all]>=0.12.0",
        "rich>=13.7.0",
        "boto3>=1.34.0",
        "google-cloud-compute>=1.18.0",
        "google-cloud-monitoring>=2.19.0",
        "google-auth>=2.29.0",
        "pyyaml>=6.0.1",
        "pydantic>=2.7.0",
    ],
    entry_points={
        "console_scripts": [
            "cloud-auditor=app.cli.main:app",
        ],
    },
    python_requires=">=3.9",
)
