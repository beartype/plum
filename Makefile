.PHONY: autodoc doc init test docopen

autodoc:
	rm -rf doc/source
	sphinx-apidoc -eMT -o doc/source/ plum
	rm doc/source/plum.rst
	pandoc --from=markdown --to=rst --output=doc/readme.rst README.md

doc:
	cd doc && make html

docopen:
	open doc/_build/html/index.html

init:
	pip install -r requirements.txt

test:
	nosetests --with-coverage --cover-html
