import warnings

# Suppress EOL/Future warnings from Boto3 and Google SDKs to clean terminal outputs
warnings.filterwarnings("ignore", category=FutureWarning, module="google")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="boto3")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="google")

from app.cli.main import app

if __name__ == "__main__":
    app()
