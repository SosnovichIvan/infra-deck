UV ?= python3 -m uv

.PHONY: check backend frontend e2e
check:
	python3 scripts/check_repository.py
	python3 -m unittest discover -s tests -p 'test_*.py' -v
	git diff --check -- . ':!.agents/skills/**'
	git diff --cached --check -- . ':!.agents/skills/**'
backend:
	$(UV) run ruff check services/control-plane/src
	$(UV) run ruff format --check services/control-plane/src
	$(UV) run mypy services/control-plane/src
	$(UV) run pytest --cov=infradeck --cov-report=json:.runtime/backend-coverage.json
	$(UV) run python scripts/check_coverage.py .runtime/backend-coverage.json
frontend:
	npm --prefix apps/web run lint
	npm --prefix apps/web run typecheck
	npm --prefix apps/web test
	npm --prefix apps/web run verify-build
e2e:
	scripts/e2e.sh
