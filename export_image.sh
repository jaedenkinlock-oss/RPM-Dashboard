#!/bin/bash
# Builds the Docker image and exports it as a .tar.gz you can send to anyone.

set -e

IMAGE="rpm-reit-dashboard:latest"
OUTPUT="rpm_dashboard.tar.gz"

echo "Building image..."
docker build -t "$IMAGE" .

echo "Exporting to $OUTPUT..."
docker save "$IMAGE" | gzip > "$OUTPUT"

SIZE=$(du -sh "$OUTPUT" | cut -f1)
echo ""
echo "Done. File: $OUTPUT ($SIZE)"
echo ""
echo "Recipient runs:"
echo "  docker load < $OUTPUT"
echo "  FRED_API_KEY=<key> docker run -p 8501:8501 $IMAGE"
echo "  # Then open http://localhost:8501"
