# Makefile for scraping-emails-mod

.PHONY: help install test lint format clean check-branch switch-main switch-apollo

help:
	@echo "Available commands:"
	@echo "  make install        - Install dependencies"
	@echo "  make test          - Run tests"
	@echo "  make lint          - Run linting"
	@echo "  make format        - Format code"
	@echo "  make clean         - Clean temporary files"
	@echo "  make check-branch  - Check current branch and features"
	@echo "  make switch-main   - Switch to main branch"
	@echo "  make switch-apollo - Switch to apollo-integration branch"

install:
	pip install -r requirements.txt
	playwright install chromium

test:
	pytest tests/unit -v

test-coverage:
	pytest --cov=scraper --cov-report=html tests/unit

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf htmlcov/ .coverage 2>/dev/null || true

check-branch:
	@python check_branch.py

switch-main:
	@echo "Switching to main branch (core features only)..."
	git checkout main
	@python check_branch.py

switch-apollo:
	@echo "Switching to apollo-integration branch (full features)..."
	git checkout apollo-integration
	@python check_branch.py

# Quick scrape commands
scrape-test:
	python -m scraper scrape restaurants --city cairo --limit 5

ui:
	python -m scraper ui

acquisition-ui:
	python -m scraper acquisition-ui
