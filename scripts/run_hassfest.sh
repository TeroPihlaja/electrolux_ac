#!/bin/sh
# Runs the same Hassfest validation as .github/workflows/validate.yml, locally via Docker.
# This is what caught the "strings.json must not contain URLs" failure in CI - run it
# before pushing so that class of failure shows up locally instead.
set -e

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    echo "hassfest: docker not available (install/start OrbStack or Docker Desktop), skipping"
    exit 0
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

# hassfest scans the whole mounted tree for manifest.json/strings.json files, so .venv
# (full of home-assistant's own bundled integrations) must be excluded or it gets scanned too.
rsync -a --exclude-from="$REPO_ROOT/.gitignore" --exclude='.git' "$REPO_ROOT/" "$WORKDIR/"

docker run --rm -v "$WORKDIR:/github/workspace" ghcr.io/home-assistant/hassfest
