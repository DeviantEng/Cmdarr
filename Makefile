.PHONY: check check-python check-frontend check-audit fix fix-python fix-frontend

check: check-python check-frontend check-audit
check-python:
	uv run ruff check . && uv run ruff format --check .
check-frontend:
	cd frontend && npm run lint && npm run format:check
check-audit:
	cd frontend && npm audit --audit-level=high
	@# Audit app dependency tree only (not pip-audit’s own env). Ignore CVE-2026-4539 until
	@# Pygments >2.19.2 is on PyPI (transitive: spotifyscraper → rich → pygments); then add
	@# Pygments>=2.19.3 to requirements.txt and drop --ignore-vuln.
	pip-audit -r requirements.txt --cache-dir .pip-audit-cache --ignore-vuln CVE-2026-4539 2>/dev/null \
		|| uv run pip-audit -r requirements.txt --cache-dir .pip-audit-cache --ignore-vuln CVE-2026-4539

fix: fix-python fix-frontend
fix-python:
	uv run ruff check . --fix && uv run ruff format .
fix-frontend:
	cd frontend && npm run lint:fix && npm run format
