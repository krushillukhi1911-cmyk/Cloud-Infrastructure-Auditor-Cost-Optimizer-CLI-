FROM python:3.12-slim

# Set system environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV CONFIG_PATH=/app/config/config.yaml

WORKDIR /app

# Install build dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc-dev \
    && rm -rf /var/lib/apt/lists/*

# Install requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . /app/

# Install the app package in editable mode
RUN pip install --no-cache-dir -e .

# Create volume mount points for configuration and reports
VOLUME ["/app/config", "/app/reports"]

# Default entrypoint routes to our CLI binary
ENTRYPOINT ["cloud-auditor"]
CMD ["--help"]
