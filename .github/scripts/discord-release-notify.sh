#!/usr/bin/env bash
# Post a release announcement to Discord using the matching section from CHANGELOG.md.
#
# Expects:
#   DISCORD_RELEASES_WEBHOOK_URL (or DISCORD_WEBHOOK) — channel webhook URL
#   GITHUB_REPOSITORY, GITHUB_SERVER_URL — set automatically in GitHub Actions
#
# Skips when:
#   - webhook secret is unset
#   - __version__.py is unchanged from the previous commit

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
CHANGELOG_FILE="${CHANGELOG_FILE:-CHANGELOG.md}"

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
if git rev-parse "$TAG" >/dev/null 2>&1; then
  RELEASE_URL="${SERVER_URL}/${REPO}/releases/tag/${TAG}"
else
  RELEASE_URL="${SERVER_URL}/${REPO}/blob/main/${CHANGELOG_FILE}"
fi

CHANGELOG_URL="${SERVER_URL}/${REPO}/blob/main/${CHANGELOG_FILE}"
DOCKER_IMAGE="${REGISTRY}/${IMAGE_NAME}:${TAG}"

python3 - "$VERSION" "$TAG" "$RELEASE_URL" "$DOCKER_IMAGE" "$CHANGELOG_URL" "$CHANGELOG_FILE" <<'PY' | curl -fsS -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d @-
import json
import re
import sys
from pathlib import Path

version, tag, release_url, docker_image, changelog_url, changelog_file = sys.argv[1:7]
path = Path(changelog_file)
if not path.is_file():
    raise SystemExit(f"{changelog_file} not found")

content = path.read_text(encoding="utf-8")
match = re.search(
    rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)",
    content,
    re.MULTILINE | re.DOTALL,
)
if not match:
    raise SystemExit(f"No ## [{version}] section in {changelog_file}")

notes = match.group(1).strip()
# Discord embeds do not render ### headings; use bold section labels instead.
notes = re.sub(r"^### (.+)$", r"**\1**", notes, flags=re.MULTILINE)

max_len = 4096
if len(notes) > max_len:
    notes = notes[: max_len - 1] + "…"

payload = {
    "embeds": [
        {
            "title": f"Cmdarr {tag} released",
            "url": release_url,
            "description": notes,
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

echo "Posted release notification for $TAG to Discord (from $CHANGELOG_FILE)."
