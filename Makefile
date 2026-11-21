.PHONY: setup venv install install-all test lint format build-ui run-server run-cli clean help

UV ?= $(shell which uv 2>/dev/null || echo ~/.local/bin/uv)
PYTHON ?= .venv/bin/python

help:
	@echo "Available commands:"
	@echo "  make setup        - Create virtual environment and install core dependencies"
	@echo "  make install-all  - Install core, ML, and dev dependencies"
	@echo "  make test         - Run test suite with pytest"
	@echo "  make lint         - Run ruff linter"
	@echo "  make format       - Format code with ruff"
	@echo "  make build-ui     - Install UI dependencies and build Svelte SPA"
	@echo "  make run-server   - Start the local FastAPI server"
	@echo "  make run-cli      - Run CLI interface"
	@echo "  make clean        - Remove caches and build artifacts"

setup: venv install

venv:
	@if [ ! -d ".venv" ]; then \
		echo "Creating virtual environment..."; \
		$(UV) venv --python 3.13 .venv; \
	fi

install: venv
	$(UV) pip install -e ".[dev]"

install-all: venv
	$(UV) pip install -e ".[ml,dev]"

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

build-ui:
	cd ui && npm install && npm run build

run-server:
	$(PYTHON) -m uvicorn server.app:app --host 127.0.0.1 --port 8000 --reload

run-cli:
	$(PYTHON) -m cli.main --help

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage dist build *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} +
