.PHONY: docmake docopen docinit docremove docupdate install test clean

PACKAGE := plum

docmake:
	rm -rf docs/source
	sphinx-apidoc -eMT -o docs/source/ $(PACKAGE)
	rm docs/source/$(PACKAGE).rst
	pandoc --from=markdown --to=rst --output=docs/readme.rst README.md
	cd docs && make html

docopen:
	open docs/_build/html/index.html

docinit:
	$(eval BRANCH := $(shell git rev-parse --abbrev-ref HEAD))
	git checkout -b gh-pages
	git ls-tree HEAD \
		| awk '$$4 !~ /\.nojekyll|docs|index\.html/ { print $$4 }' \
		| xargs -I {} git rm -r {}
	touch .nojekyll
	echo '<meta http-equiv="refresh" content="0; url=./docs/_build/html/index.html" />' > index.html
	git add .nojekyll index.html
	git commit -m "Branch cleaned for docs"
	git push origin gh-pages
	git checkout $(BRANCH)

docremove:
	git branch -D gh-pages
	git push origin --delete gh-pages

docupdate: docmake
	$(eval BRANCH := $(shell git rev-parse --abbrev-ref HEAD))
	rm -rf docs/_build/html_new
	mv docs/_build/html docs/_build/html_new
	git checkout gh-pages
	rm -rf docs/_build/html
	mv docs/_build/html_new docs/_build/html
	git add -f docs/_build/html
	git commit -m "Update docs at $$(date +'%d %b %Y, %H:%M')"
	git push origin gh-pages
	git checkout $(BRANCH)

install:
	pip install -r requirements.txt

test:
	python setup.py --version
	pytest -v --cov=$(PACKAGE) --cov-report html:cover --cov-report term-missing

clean:
	rm -rf docs/_build docs/source docs/readme.rst
	git rm --cached -r docs
	git add docs/Makefile docs/conf.py docs/index.rst docs/api.rst
	rm -rf .coverage cover
	find . | grep '\(\.DS_Store\|\.pyc\)$$' | xargs rm
