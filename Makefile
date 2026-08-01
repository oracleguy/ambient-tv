.PHONY: generate check test lint apply

generate:
	python3 generate.py

check:
	python3 generate.py --check --no-publish

test:
	python3 -m pytest

lint:
	python3 -m ruff check .

apply: generate
	docker compose config --quiet
