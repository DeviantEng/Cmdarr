#!/usr/bin/env bash
# ZAP baseline scan against a running container.
# Uses zap-baseline.py (passive spider + passive scan). For deeper coverage, consider
# zaproxy/action-full-scan (spider + optional AJAX spider + active scan) - see
# https://github.com/marketplace/actions/zap-full-scan
#
# Usage: ./zap-scan.sh <image> [workspace]
#   image     - Docker image to run (e.g. ghcr.io/devianteng/cmdarr:scan)
#   workspace - Path for zap-wrk (default: $GITHUB_WORKSPACE or .)
#
# Expects: .github/zap/zap_auth_hook.py, .github/zap/zap-baseline.conf
# Outputs: zap-wrk/zap-report.json, appends to $GITHUB_STEP_SUMMARY when set

set -euo pipefail

IMAGE="${1:?Usage: $0 <image> [workspace]}"
WORKSPACE="${2:-${GITHUB_WORKSPACE:-.}}"
ZAP_WRK="${WORKSPACE}/zap-wrk"
TARGET="http://cmdarr-zap-target:8080"
NETWORK="zap-net"

# Clean up any leftover container from a previous run
docker rm -f cmdarr-zap-target 2>/dev/null || true

# Create network and start target container
docker network create "$NETWORK" 2>/dev/null || true
docker run -d --name cmdarr-zap-target --network "$NETWORK" -p 8080:8080 \
  -v cmdarr-zap-data:/app/data \
  -e LIDARR_API_KEY=zap-scan-dummy -e LASTFM_API_KEY=zap-scan-dummy \
  "$IMAGE"

# Wait for app health
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health 2>/dev/null || true)
  [[ "$code" == "200" || "$code" == "503" ]] && break
  sleep 2
done
[[ "$code" == "200" || "$code" == "503" ]] || { echo "App did not become ready"; exit 1; }
sleep 5

# Run ZAP baseline scan
mkdir -p "$ZAP_WRK"
cp .github/zap/zap_auth_hook.py .github/zap/zap-baseline.conf "$ZAP_WRK/"
chmod 777 "$ZAP_WRK"

exitcode=0
docker run --rm --network "$NETWORK" -v "${ZAP_WRK}:/zap/wrk:rw" -t ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py -t "$TARGET" -I -j -c /zap/wrk/zap-baseline.conf -J /zap/wrk/zap-report.json \
  --hook=/zap/wrk/zap_auth_hook.py || exitcode=$?

# Append to GitHub Step Summary when in Actions
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  echo "## ZAP Baseline Scan Findings" >> "$GITHUB_STEP_SUMMARY"
  echo "" >> "$GITHUB_STEP_SUMMARY"
  if [[ -f "${ZAP_WRK}/zap-report.json" ]]; then
    count=$(jq -r '[.site[]?.alerts[]? | select((.riskcode | tonumber) > 0)] | length' "${ZAP_WRK}/zap-report.json" 2>/dev/null || echo "0")
    if [[ "$count" != "0" && "$count" != "null" ]]; then
      echo "| Severity | Rule ID | Finding | URL |" >> "$GITHUB_STEP_SUMMARY"
      echo "|----------|---------|---------|-----|" >> "$GITHUB_STEP_SUMMARY"
      jq -r '.site[]?.alerts[]? | select((.riskcode | tonumber) > 0) | "| \(.riskdesc) | \(.pluginid) | \(.alert | gsub("\\|"; "&#124;") | .[0:50]) | \((.instances[0].uri // "N/A") | .[0:50]) |"' "${ZAP_WRK}/zap-report.json" 2>/dev/null >> "$GITHUB_STEP_SUMMARY" || true
    else
      echo "No failures or warnings." >> "$GITHUB_STEP_SUMMARY"
    fi
  else
    echo "Report not generated." >> "$GITHUB_STEP_SUMMARY"
  fi
fi

exit $exitcode
