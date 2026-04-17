#!/usr/bin/env bash
# Wrapper that applies strixnoapi's hardened docker-run flags.
#
# Usage:
#     containers/docker-run-hardened.sh <image> <cmd...>
#
# Example:
#     containers/docker-run-hardened.sh strixnoapi-sandbox:0.1.0 bash
#
# Flags follow `containers/Dockerfile.hardened`. Override via env:
#     STRIX_ALLOW_NET_RAW=0  disables NET_RAW/NET_ADMIN capabilities

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <image> [cmd...]" >&2
  exit 64
fi

IMAGE="$1"
shift

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SECCOMP_PATH="${SCRIPT_DIR}/seccomp.json"

DOCKER_FLAGS=(
  --rm
  --read-only
  --cap-drop=ALL
  --security-opt=no-new-privileges
  --pids-limit=512
  --memory=4g
  --memory-swap=4g
  --tmpfs=/tmp:rw,size=1g,mode=1777
  --tmpfs=/workspace/.cache:rw,size=512m
)

if [[ -f "${SECCOMP_PATH}" ]]; then
  DOCKER_FLAGS+=(--security-opt=seccomp="${SECCOMP_PATH}")
fi

if [[ "${STRIX_ALLOW_NET_RAW:-1}" == "1" ]]; then
  DOCKER_FLAGS+=(--cap-add=NET_RAW --cap-add=NET_ADMIN)
fi

exec docker run "${DOCKER_FLAGS[@]}" "${IMAGE}" "$@"
