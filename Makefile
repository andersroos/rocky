
PIP := pip3
PYTHON := python3
TWINE := twine

-include local.mk

.PHONY: default dev publish clean init test

default: dev

init:
	$(PIP) install -r requirements.txt --upgrade

dev:
	$(PIP) install -e .

test:
	$(PYTHON) setup.py test

publish: clean
	$(PYTHON) setup.py sdist
	$(PYTHON) setup.py bdist_wheel
	$(TWINE) upload dist/*

clean:
	rm -rf dist rocky.egg-info build

