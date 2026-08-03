.PHONY: setup test lint format pipeline dashboard clean

PYTHON := venv/Scripts/python.exe
PIP := venv/Scripts/pip.exe

setup:
	python -m venv venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	$(PYTHON) -m pre_commit install

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	$(PYTHON) -m ruff check src/ tests/
	$(PYTHON) -m mypy src/ --strict

format:
	$(PYTHON) -m black --line-length 100 src/ tests/
	$(PYTHON) -m ruff check --fix src/ tests/

pipeline:
	$(PYTHON) scripts/run_pipeline.py

dashboard:
	$(PYTHON) -m streamlit run app.py

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true