.PHONY: check
check:
	python3 scripts/check_repository.py
	python3 -m unittest discover -s tests -p 'test_*.py' -v
	git diff --check -- . ':!.agents/skills/**'
	git diff --cached --check -- . ':!.agents/skills/**'
