# Keep in sync with `.github/workflows/pr-checks.yml` (pip install zizmor==…).
ZIZMOR_VERSION = 1.24.1

.PHONY: check check-python check-zizmor check-test test check-frontend check-audit fix fix-python fix-zizmor fix-frontend

check: check-python check-zizmor check-frontend check-test check-audit
check-python:
	uv run ruff check . && uv run ruff format --check .
check-zizmor:
	uvx zizmor==$(ZIZMOR_VERSION) . --offline
check-test test:
	uv run --with-requirements requirements-dev.txt pytest tests/ -v \
		--cov=utils --cov=tests --cov-report=term-missing
check-frontend:
	cd frontend && npm run lint && npm run format:check
check-audit:
	cd frontend && npm audit --audit-level=high
	@# Audit project requirements only (pinned/fixed vulns handled in requirements.txt).
	pip-audit -r requirements.txt --cache-dir .pip-audit-cache 2>/dev/null \
		|| uv run pip-audit -r requirements.txt --cache-dir .pip-audit-cache

fix: fix-python fix-zizmor fix-frontend
fix-python:
	uv run ruff check . --fix && uv run ruff format .
fix-zizmor:
	uvx zizmor==$(ZIZMOR_VERSION) . --offline --fix=safe
fix-frontend:
	cd frontend && npm run lint:fix && npm run format
