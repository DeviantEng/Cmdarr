.PHONY: check check-python check-frontend check-audit fix fix-python fix-frontend

check: check-python check-frontend check-audit
check-python:
	ruff check . && ruff format --check .
check-frontend:
	cd frontend && npm run lint && npm run format:check
check-audit:
	cd frontend && npm audit --audit-level=high
	pip-audit --cache-dir .pip-audit-cache 2>/dev/null || uv run pip-audit --cache-dir .pip-audit-cache

fix: fix-python fix-frontend
fix-python:
	ruff check . --fix && ruff format .
fix-frontend:
	cd frontend && npm run lint:fix && npm run format
