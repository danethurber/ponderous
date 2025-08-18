# Makefile for Ponderous MTG Collection Analyzer
#
# This Makefile provides common development tasks for the Ponderous project.
# It handles environment setup, testing, coverage, and code validation.

.PHONY: help setup test test-coverage validate lint format typecheck clean install-hooks run-hooks

# Default target
help:
	@echo "Ponderous MTG Collection Analyzer - Development Commands"
	@echo ""
	@echo "Available targets:"
	@echo "  help           Show this help message"
	@echo "  setup          Setup environment and install dependencies"
	@echo "  test           Run tests"
	@echo "  test-coverage  Run tests with coverage report"
	@echo "  validate       Run all validation (lint, format, typecheck)"
	@echo "  lint           Run linting checks"
	@echo "  format         Format code"
	@echo "  typecheck      Run type checking"
	@echo "  install-hooks  Install pre-commit hooks"
	@echo "  run-hooks      Run pre-commit hooks manually"
	@echo "  clean          Clean up build artifacts and cache"
	@echo ""
	@echo "Environment:"
	@echo "  This project uses uv for dependency management."
	@echo "  UV_NO_CONFIG=1 is used to bypass global uv configuration."

# Setup environment and install dependencies
setup:
	@echo "🚀 Setting up Ponderous development environment..."
	uv --version || (echo "❌ uv not found. Install from https://github.com/astral-sh/uv" && exit 1)
	UV_NO_CONFIG=1 uv sync --all-groups
	UV_NO_CONFIG=1 uv run --group dev pre-commit install
	@echo "✅ Environment setup complete!"

# Install dependencies only
install:
	@echo "📦 Installing dependencies..."
	UV_NO_CONFIG=1 uv sync --all-groups
	@echo "✅ Dependencies installed!"

# Run tests
test:
	@echo "🧪 Running tests..."
	UV_NO_CONFIG=1 uv run --group test pytest

# Run tests with coverage
test-coverage:
	@echo "🧪 Running tests with coverage..."
	UV_NO_CONFIG=1 uv run --group test pytest --cov=src/ponderous --cov-report=term-missing --cov-report=html

# Run all validation (lint, format check, typecheck)
validate: lint format typecheck
	@echo "✅ All validation checks complete!"

# Run linting
lint:
	@echo "🔍 Running linting..."
	UV_NO_CONFIG=1 uv run --group lint ruff check src tests

# Fix linting issues
lint-fix:
	@echo "🔧 Fixing linting issues..."
	UV_NO_CONFIG=1 uv run --group lint ruff check --fix src tests

# Format code
format:
	@echo "🎨 Formatting code..."
	UV_NO_CONFIG=1 uv run --group lint ruff format src tests

# Check if code is formatted
format-check:
	@echo "🎨 Checking code formatting..."
	UV_NO_CONFIG=1 uv run --group lint ruff format --check src tests

# Run type checking
typecheck:
	@echo "🔎 Running type checking..."
	UV_NO_CONFIG=1 uv run --group lint mypy src

# Install pre-commit hooks
install-hooks:
	@echo "🪝 Installing pre-commit hooks..."
	UV_NO_CONFIG=1 uv run --group dev pre-commit install
	@echo "✅ Pre-commit hooks installed!"

# Run pre-commit hooks manually
run-hooks:
	@echo "🪝 Running pre-commit hooks..."
	UV_NO_CONFIG=1 uv run --group dev pre-commit run --all-files

# Run quality gate hook
quality-gate:
	@echo "🚦 Running quality gate..."
	UV_NO_CONFIG=1 uv run python .claude/hooks/claude_quality_gate.py src/ tests/

# Clean up build artifacts and cache
clean:
	@echo "🧹 Cleaning up..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	@echo "✅ Cleanup complete!"

# Development shortcuts
dev-setup: setup
	@echo "🎯 Development environment ready!"

# Quick validation for CI
ci-validate: lint format-check typecheck test
	@echo "✅ CI validation complete!"

# Full test suite with coverage for CI
ci-test: test-coverage
	@echo "✅ CI testing complete!"
