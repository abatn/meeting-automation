#!/bin/bash
set -e

# URL for the latest stable release of Docker Compose
DOCKER_COMPOSE_URL="https://github.com/docker/compose/releases/download/v2.24.5/docker-compose-linux-x86_64"

# Download the Docker Compose binary
echo "Downloading Docker Compose from $DOCKER_COMPOSE_URL..."
curl -L "$DOCKER_COMPOSE_URL" -o docker-compose

# Make the binary executable
echo "Making the binary executable..."
chmod +x docker-compose

# Move the binary to a directory in the system's PATH
echo "Moving docker-compose to /usr/local/bin/ (requires sudo)..."
sudo mv docker-compose /usr/local/bin/docker-compose

# Verify the installation
echo "Verifying installation..."
docker-compose --version

echo "Docker Compose installed successfully."