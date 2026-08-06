#!/usr/bin/env bash
# Build the shared task base image. Run this once before the benchmark; task
# Dockerfiles are `FROM jj-bench-base:0.38.0` and docker resolves it locally.
set -euo pipefail

TAG="${TAG:-jj-bench-base:0.38.0}"
PLATFORM="${DOCKER_DEFAULT_PLATFORM:-}"

cd "$(dirname "$0")/.."
docker build ${PLATFORM:+--platform "$PLATFORM"} -t "$TAG" base/
echo "built $TAG${PLATFORM:+ for $PLATFORM}"
