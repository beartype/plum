.PHONY: install test

PACKAGE := plum

install:
	pip install -e '.[dev]'

test:
	python check_linter_assertions.py tests/typechecked
	pre-commit run --all-files
	PRAGMA_VERSION=`python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"` \
		pytest tests -v --cov=$(PACKAGE) --cov-report html:cover --cov-report term-missing
