.PHONY: doc init test docopen

doc:
	rm -rf doc/source
	sphinx-apidoc -eMT -o doc/source/ plum
	rm doc/source/plum.rst
	pandoc --from=markdown --to=rst --output=doc/readme.rst README.md
	cd doc && make html

docopen:
	open doc/_build/html/index.html

init:
	pip install -r requirements.txt

test:
	nosetests tests
