#!/usr/bin/env bash
# Post a release announcement to Discord using the annotated git tag message.
#
# Expects:
#   DISCORD_RELEASES_WEBHOOK_URL (or DISCORD_WEBHOOK) — channel webhook URL
#   GITHUB_REPOSITORY, GITHUB_SERVER_URL — set automatically in GitHub Actions
#
# Skips when:
#   - webhook secret is unset
#   - __version__.py is unchanged from the previous commit
#   - tag v{version} is missing or not annotated

set -euo pipefail

WEBHOOK_URL="${DISCORD_RELEASES_WEBHOOK_URL:-${DISCORD_WEBHOOK:-}}"
if [[ -z "$WEBHOOK_URL" ]]; then
  echo "DISCORD_RELEASES_WEBHOOK_URL not set; skipping Discord notification."
  exit 0
fi

REPO="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
SERVER_URL="${GITHUB_SERVER_URL:-https://github.com}"
REGISTRY="${REGISTRY:-ghcr.io}"
IMAGE_NAME="${IMAGE_NAME:-devianteng/cmdarr}"

VERSION="$(python3 -c "from __version__ import __version__; print(__version__)")"
PREV_VERSION=""
if PREV_FILE="$(git show HEAD~1:__version__.py 2>/dev/null)"; then
  PREV_VERSION="$(printf '%s' "$PREV_FILE" | python3 -c "
import sys
for line in sys.stdin:
    if line.strip().startswith('__version__'):
        print(line.split('=', 1)[1].strip().strip('\"').strip(\"'\"))
        break
")"
fi

if [[ -n "$PREV_VERSION" && "$PREV_VERSION" == "$VERSION" ]]; then
  echo "Version unchanged ($VERSION); skipping Discord notification."
  exit 0
fi

TAG="v${VERSION}"
if ! git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag $TAG not found; skipping Discord notification."
  exit 0
fi

TAG_MESSAGE="$(git tag -l --format='%(contents)' "$TAG")"
if [[ -z "$TAG_MESSAGE" ]]; then
  echo "Tag $TAG has no annotated message. Create it with: git tag -a $TAG -m \"...\""
  exit 1
fi

TAG_URL="${SERVER_URL}/${REPO}/releases/tag/${TAG}"
CHANGELOG_URL="${SERVER_URL}/${REPO}/blob/main/CHANGELOG.md"
DOCKER_IMAGE="${REGISTRY}/${IMAGE_NAME}:${TAG}"

python3 - "$TAG" "$TAG_URL" "$DOCKER_IMAGE" "$CHANGELOG_URL" "$TAG_MESSAGE" <<'PY' | curl -fsS -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d @-
import json
import sys

tag, tag_url, docker_image, changelog_url, message = sys.argv[1:6]
max_len = 4096
if len(message) > max_len:
    message = message[: max_len - 1] + "…"

payload = {
    "embeds": [
        {
            "title": f"Cmdarr {tag} released",
            "url": tag_url,
            "description": message,
            "color": 5793266,
            "fields": [
                {
                    "name": "Docker",
                    "value": f"`{docker_image}`",
                    "inline": False,
                },
                {
                    "name": "Changelog",
                    "value": f"[CHANGELOG.md]({changelog_url})",
                    "inline": False,
                },
            ],
        }
    ]
}
print(json.dumps(payload))
PY

echo "Posted release notification for $TAG to Discord."
