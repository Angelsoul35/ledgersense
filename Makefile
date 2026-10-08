.PHONY: install test lint run demo clean

install:
	pip install -e ".[dev]"

test:
	pytest --cov=ledgersense --cov-report=term-missing

lint:
	ruff check ledgersense tests

run:
	uvicorn ledgersense.main:app --reload --port 8000

demo:
	python -m ledgersense.cli demo

clean:
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov
