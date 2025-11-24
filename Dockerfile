FROM python:3.13.2-slim

# Install system dependencies for image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency files
COPY pyproject.toml requirements.txt README.md /app/

# Copy source code
COPY src/ /app/src/

# Install Python dependencies
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install the package
RUN pip install --no-cache-dir -e .

# Create directory for data
WORKDIR /data

# Set the entry point to the CLI
ENTRYPOINT ["dicom-extract"]
CMD ["--help"]
