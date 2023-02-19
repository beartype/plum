.PHONY: docmake docopen docinit docremove docupdate install test clean

PACKAGE := plum

install:
	pip install -r requirements.txt

test:
	python setup.py --version
	pre-commit run --all-files && sleep 0.2 && \
		PRAGMA_VERSION=`python -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"` \
			pytest tests -v --cov=$(PACKAGE) --cov-report html:cover --cov-report term-missing
