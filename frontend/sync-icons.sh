#!/usr/bin/env bash
# Copy canonical icons from assets/icon into frontend/public for Vite.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ICON_DIR="$ROOT/assets/icon"
PUBLIC_DIR="$(dirname "$0")/public"

if [[ ! -f "$ICON_DIR/icon-512.png" ]]; then
  echo "Missing $ICON_DIR/icon-512.png" >&2
  exit 1
fi

mkdir -p "$PUBLIC_DIR"
for f in icon-32.png icon-192.png icon-512.png icon-1024.png apple-touch-icon.png site.webmanifest; do
  cp "$ICON_DIR/$f" "$PUBLIC_DIR/"
done

echo "Synced icons to frontend/public"
