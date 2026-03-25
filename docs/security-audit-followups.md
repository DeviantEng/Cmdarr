# Security audit follow-ups

## Pygments CVE-2026-4539 (GHSA-5239-wwwm-4pmq)

**Status:** Intentionally ignored in `make check-audit` and PR `pip-audit` until a fixed release is on PyPI.

**Checklist (revisit periodically):**

1. Run `pip index versions Pygments` or open [PyPI Pygments](https://pypi.org/project/Pygments/#history) and confirm a version **newer than 2.19.2** is published.
2. Add to [requirements.txt](../requirements.txt): `Pygments>=2.19.3` (or whatever the first fixed version is).
3. Remove `--ignore-vuln CVE-2026-4539` from [Makefile](../Makefile) (`check-audit` target) and [.github/workflows/pr-checks.yml](../.github/workflows/pr-checks.yml) (`pip-audit` job).
4. Run `make check-audit` and confirm **no ignored vulnerabilities** remain for this CVE.

**Why ignored:** The vulnerable package is transitive (`spotifyscraper` → `rich` → `pygments`). No patched wheel was available at the time the ignore was added.
