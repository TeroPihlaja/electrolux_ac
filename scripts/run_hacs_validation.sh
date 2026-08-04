#!/bin/sh
# Runs the same HACS validation as .github/workflows/validate.yml, locally via Docker.
# Unlike hassfest, this checks the *pushed* state of the repo on GitHub (releases, topics,
# manifest on the default branch) rather than the local working tree, so it's only useful
# after pushing/tagging - run it as a release sanity check, not on every commit.
set -e

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    echo "hacs validation: docker not available (install/start OrbStack or Docker Desktop), skipping"
    exit 0
fi

if ! command -v gh >/dev/null 2>&1; then
    echo "hacs validation: gh CLI not found, needed for a token to call the GitHub API"
    exit 1
fi

REPO="TeroPihlaja/electrolux_ac"

docker run --rm \
    -e INPUT_CATEGORY=integration \
    -e INPUT_IGNORE=brands \
    -e INPUT_GITHUB_TOKEN="$(gh auth token)" \
    -e INPUT_REPOSITORY="$REPO" \
    ghcr.io/hacs/action
