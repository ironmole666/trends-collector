.PHONY: install run report clean

install:
	pip install -r requirements.txt

run:
	python -m trends_collector --once

run-loop:
	python -m trends_collector

report:
	python -m trends_collector --report

deploy:
	bash deploy.sh
