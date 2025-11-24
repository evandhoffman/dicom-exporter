#!/bin/bash
# Build and test script for dicom-exporter Docker image

set -e

echo "Building Docker image..."
docker build -t dicom-exporter:latest .

echo ""
echo "Build successful! Testing help command..."
docker run --rm dicom-exporter:latest --help

echo ""
echo "Docker image ready to use!"
echo ""
echo "Example usage:"
echo "  docker run --rm -v \$(pwd)/data:/data dicom-exporter:latest \\"
echo "    --input-file /data/scan.iso \\"
echo "    --convert-to-png"
echo ""
echo "To run interactively:"
echo "  docker run --rm -it -v \$(pwd)/data:/data dicom-exporter:latest bash"
