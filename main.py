import warnings

# Suppress EOL/Future warnings from Boto3 and Google SDKs to clean terminal outputs
warnings.filterwarnings("ignore", category=FutureWarning, module="google")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="boto3")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="google")

import typer
from app.cli.commands import app
from app.utils.logger import setup_logger

# Initialize logging on startup
setup_logger()

# Set up main help documentation and options
app.info.name = "cloud-auditor"
app.info.help = "Cloud Infrastructure Auditor & Cost Optimizer CLI Tool"

if __name__ == "__main__":
    app()
