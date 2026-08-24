#!/usr/bin/env bash
# Compare pinned Chainguard python digests in Dockerfile against :latest tag history.
# Exits 0 when pinned digests match registry; exits 1 when newer digests are available.
#
# Usage: .github/scripts/check-chainguard-python-digest.sh [Dockerfile]
# Requires: curl, jq, docker (optional, for python --version on new digest)

set -euo pipefail

DOCKERFILE="${1:-Dockerfile}"
IMAGE="chainguard/python"

pinned_runtime=$(grep -E '^FROM cgr.dev/chainguard/python(:[A-Za-z0-9._-]+)?@sha256:' "$DOCKERFILE" | grep -v ' AS ' \
  | sed -E 's/.*@sha256:([a-f0-9]+).*/\1/' | head -1)
pinned_builder=$(grep -E 'FROM cgr.dev/chainguard/python(:[A-Za-z0-9._-]+)?@sha256:.* AS python-builder' "$DOCKERFILE" \
  | sed -E 's/.*@sha256:([a-f0-9]+).*/\1/')

tok=$(curl -s "https://cgr.dev/token?scope=repository:${IMAGE}:pull" | jq -r .token)
latest_runtime=$(curl -s -H "Authorization: Bearer $tok" \
  "https://cgr.dev/v2/${IMAGE}/_chainguard/history/latest" | jq -r '.history[-1].digest' | sed 's/sha256://')
latest_builder=$(curl -s -H "Authorization: Bearer $tok" \
  "https://cgr.dev/v2/${IMAGE}/_chainguard/history/latest-dev" | jq -r '.history[-1].digest' | sed 's/sha256://')

echo "Runtime  pinned: sha256:${pinned_runtime}"
echo "Runtime  latest: sha256:${latest_runtime}"
echo "Builder  pinned: sha256:${pinned_builder}"
echo "Builder  latest: sha256:${latest_builder}"

if [[ "$pinned_runtime" == "$latest_runtime" && "$pinned_builder" == "$latest_builder" ]]; then
  echo "Digests are current."
  exit 0
fi

if command -v docker >/dev/null 2>&1; then
  if [[ "$pinned_runtime" != "$latest_runtime" ]]; then
    echo "New runtime digest — Python version:"
    docker run --rm "cgr.dev/${IMAGE}@sha256:${latest_runtime}" --version || true
  fi
  if [[ "$pinned_builder" != "$latest_builder" ]]; then
    echo "New builder digest — Python version:"
    docker run --rm --entrypoint python "cgr.dev/${IMAGE}@sha256:${latest_builder}" --version || true
  fi
fi

echo "Newer Chainguard digests available — review SBOM/python version before bumping Dockerfile."
exit 1
