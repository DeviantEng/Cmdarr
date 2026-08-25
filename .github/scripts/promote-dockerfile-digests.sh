#!/usr/bin/env bash
# Copy Dockerfile FROM pins (tag + digest) from the current tree onto origin/main
# and open or update a PR. Used after a green :develop image publish so production
# tags can move without an app version bump.
#
# Usage: .github/scripts/promote-dockerfile-digests.sh
# Requires: git, python3, gh, GH_TOKEN (or GITHUB_TOKEN)

set -euo pipefail

BRANCH="ci/promote-docker-digests"
DOCKERFILE="${DOCKERFILE:-Dockerfile}"
BASE="${BASE_REF:-main}"
REMOTE="${REMOTE:-origin}"

if [[ -z "${GH_TOKEN:-${GITHUB_TOKEN:-}}" ]]; then
  echo "GH_TOKEN or GITHUB_TOKEN is required." >&2
  exit 1
fi
export GH_TOKEN="${GH_TOKEN:-${GITHUB_TOKEN}}"
gh auth setup-git

git fetch --no-tags "$REMOTE" "$BASE"

python3 - "$DOCKERFILE" "$REMOTE/$BASE:$DOCKERFILE" <<'PY'
import pathlib
import re
import subprocess
import sys

dockerfile, main_spec = sys.argv[1], sys.argv[2]
src = pathlib.Path(dockerfile).read_text(encoding="utf-8")
dst = subprocess.check_output(["git", "show", main_spec], text=True)

as_re = re.compile(r"\sAS\s+(\S+)\s*$", re.IGNORECASE)


def stage_key(line: str) -> str:
    match = as_re.search(line)
    return match.group(1) if match else "__runtime__"


src_from = {stage_key(line): line for line in src.splitlines() if line.startswith("FROM ")}
out_lines = []
changed = False
for line in dst.splitlines():
    if line.startswith("FROM "):
        replacement = src_from.get(stage_key(line))
        if replacement is not None and replacement != line:
            out_lines.append(replacement)
            changed = True
            continue
    out_lines.append(line)

new_dst = "\n".join(out_lines)
if dst.endswith("\n"):
    new_dst += "\n"

pathlib.Path("/tmp/cmdarr-promoted.Dockerfile").write_text(new_dst, encoding="utf-8")
pathlib.Path("/tmp/cmdarr-promote-changed").write_text("yes" if changed else "no", encoding="utf-8")
PY

if [[ "$(cat /tmp/cmdarr-promote-changed)" != "yes" ]]; then
  echo "main already has the same Dockerfile FROM pins."
  exit 0
fi

git switch --detach "$REMOTE/$BASE"
git switch -C "$BRANCH"
cp /tmp/cmdarr-promoted.Dockerfile "$DOCKERFILE"
git add "$DOCKERFILE"

if git diff --cached --quiet; then
  echo "No staged Dockerfile changes after promote."
  exit 0
fi

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git commit -m "$(cat <<'EOF'
ci: promote Dockerfile base image digests to main

Refresh digest-pinned Wolfi/Node FROM lines from develop after a green
image scan, without bumping the app version.
EOF
)"

git push --force-with-lease -u "$REMOTE" "$BRANCH"

repo="${GITHUB_REPOSITORY:-}"
if [[ -z "$repo" ]]; then
  repo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
fi
server="${GITHUB_SERVER_URL:-https://github.com}"
compare_url="${server}/${repo}/compare/${BASE}...${BRANCH}?expand=1"

pr_body="$(cat <<'EOF'
## Summary
- Copies `Dockerfile` `FROM` pins (tag + digest) from `develop` onto `main` after the `:develop` image published successfully (including Trivy).
- No app version bump, changelog section, or git tag. Discord release notify already skips when `__version__.py` is unchanged.
- Merging retags the current prod Docker tags (`latest`, `v0`, `v0.x`, patch) with the patched base image.

## Test plan
- [ ] PR diff is `Dockerfile` `FROM` lines only
- [ ] Merge and confirm `docker-publish` on `main` passes Trivy before push
EOF
)"

write_manual_pr_help() {
  local err="$1"
  echo "$err"
  echo "::warning::GITHUB_TOKEN cannot open PRs until this is enabled: Settings → Actions → General → Workflow permissions → Allow GitHub Actions to create and approve pull requests. Branch ${BRANCH} is already pushed; open ${compare_url}"
  if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    cat >> "$GITHUB_STEP_SUMMARY" <<EOF
## Dockerfile digest PR not opened

GitHub blocked \`gh pr create\` (\`GitHub Actions is not permitted to create or approve pull requests\`).

1. Repo **Settings → Actions → General → Workflow permissions**
2. Enable **Allow GitHub Actions to create and approve pull requests**
3. Re-run this job, or open the PR now: ${compare_url}
EOF
  fi
}

existing="$(gh pr list --base "$BASE" --head "$BRANCH" --state open --json number --jq '.[0].number // empty')"
if [[ -n "$existing" ]]; then
  echo "Updated existing PR #${existing}"
  exit 0
fi

set +e
create_out="$(gh pr create --base "$BASE" --head "$BRANCH" \
  --title "ci: promote Dockerfile base digests (no app version bump)" \
  --body "$pr_body" 2>&1)"
create_rc=$?
set -e

if [[ "$create_rc" -eq 0 ]]; then
  echo "$create_out"
  exit 0
fi

if echo "$create_out" | grep -q 'not permitted to create or approve pull requests'; then
  write_manual_pr_help "$create_out"
  exit 0
fi

echo "$create_out" >&2
exit "$create_rc"
