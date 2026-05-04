# Security audit follow-ups

## Pygments CVE-2026-4539 (GHSA-5239-wwwm-4pmq)

**Status:** Addressed. [requirements.txt](../requirements.txt) pins **Pygments>=2.20.0** (direct constraint on the transitive path `spotifyscraper` → `rich` → `pygments`). **`make check-audit`** and the PR **`pip-audit`** job run without **`--ignore-vuln`** for this CVE.

**Periodic check:** Run `make check-audit` after dependency changes.
