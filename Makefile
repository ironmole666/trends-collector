.PHONY: install run report test clean

PYTHON ?= python3

install:
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) -m trends_collector --once

run-loop:
	$(PYTHON) -m trends_collector

report:
	$(PYTHON) -m trends_collector --report

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

deploy:
	bash deploy.sh
