#!/usr/bin/env bash
#
# Common environment setup and helpers for Iragi scripts.
#

set -euo pipefail

# Resolve project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Activate virtual environment if present
if [ -f "${PROJECT_ROOT}/.env/bin/activate" ]; then
    source "${PROJECT_ROOT}/.env/bin/activate"
fi

# Set PYTHONPATH
export PYTHONPATH="${PROJECT_ROOT}:${PROJECT_ROOT}/iragi:${PYTHONPATH:-}"

# Docker Compose arguments default
COMPOSE_ARGS="${COMPOSE_ARGS:-}"
