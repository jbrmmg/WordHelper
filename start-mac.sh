#!/usr/bin/env bash
set -e

REGISTRY="nexus.jbrmmg.me.uk:8084"
COMPOSE_FILE="$(dirname "$0")/docker-compose-mac.yml"

# Ensure the word database directory exists
mkdir -p "${HOME}/.wordhelper"

echo "Pulling latest images from ${REGISTRY}..."
docker login "${REGISTRY}"
docker compose -f "${COMPOSE_FILE}" pull

echo "Starting containers..."
docker compose -f "${COMPOSE_FILE}" up -d

echo ""
echo "Running:"
echo "  wordscanner -> http://localhost:8080"
echo "  wordclue    -> http://localhost:8081"
echo "  connections -> http://localhost:8082"
