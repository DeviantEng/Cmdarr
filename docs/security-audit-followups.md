# Security audit follow-ups

## Pygments CVE-2026-4539 (GHSA-5239-wwwm-4pmq)

**Status:** Addressed. [requirements.txt](../requirements.txt) pins **Pygments>=2.20.0** (direct constraint on the transitive path `spotifyscraper` → `rich` → `pygments`). **`make check-audit`** and the PR **`pip-audit`** job run without **`--ignore-vuln`** for this CVE.

**Periodic check:** Run `make check-audit` after dependency changes.

## MAL-2026-4750 (pip-audit / OSV noise on FastAPI)

**Status:** Temporary **false positive** in OSV advisory data for **FastAPI**; correct upstream. **`make check-audit`** and the PR **`pip-audit`** job pass **`--ignore-vuln MAL-2026-4750`** until the advisory is retracted or fixed. Then remove **`PIPAUDIT_IGNORES`** in the [Makefile](../Makefile) and the **`--ignore-vuln`** flag in [.github/workflows/pr-checks.yml](../.github/workflows/pr-checks.yml).
