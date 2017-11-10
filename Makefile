.PHONY: doc init test docopen

doc:
	rm -rf doc/source
	sphinx-apidoc -eMT -o doc/source/ plum
	cd doc && make html

docopen:
	open doc/_build/html/index.html

init:
	pip install -r requirements.txt

test:
	nosetests tests
