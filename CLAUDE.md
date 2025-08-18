# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

Ponderous is a Python 3.11 CLI application that analyzes Magic: The Gathering collections to recommend buildable Commander decks. It follows clean architecture principles with domain-driven design.

The application integrates with Moxfield (collection management) and EDHREC (deck statistics) to provide data-driven deck recommendations based on owned cards, budget constraints, and deck buildability scores.

## Code Quality Standards

- **Language**: Python 3.11 with modern type hints (`X | None` instead of `Optional[X]`)
- **Code Style**: Black formatting, Ruff linting, MyPy type checking
- **Test Coverage**: 95%+ coverage required
- **Documentation**: Only add comments/docstrings that provide genuine value or unknown context
- **Architecture**: Clean architecture with clear separation of concerns

## Architecture Overview

Ponderous follows clean architecture with clear separation between layers:

### Domain Layer (`src/ponderous/domain/`)
- **Models**: Core entities (Card, Collection, Commander, Deck, User) with business logic
- **Services**: Domain services for complex business operations (deck analysis algorithms)
- **Repositories**: Abstract interfaces for data access (dependency inversion)

### Infrastructure Layer (`src/ponderous/infrastructure/`)
- **Database**: DuckDB connection management and migrations for analytical queries
- **External APIs**: Moxfield API client and EDHREC web scraper with rate limiting
- **ETL**: Data pipelines using dlt (Data Load Tool) for bulk data operations

### Application Layer (`src/ponderous/application/`)
- **Use Cases**: Business workflows (discover commanders, analyze collections)
- **Services**: Application services that orchestrate domain and infrastructure

### Presentation Layer (`src/ponderous/presentation/`)
- **CLI**: Click-based command line interface with rich output formatting
- **Formatters**: Output formatting for different display modes
- **Validators**: Input validation for CLI commands

### Key Domain Concepts
- **Buildability Scoring**: Algorithms that calculate deck completion percentages based on owned cards and EDHREC inclusion rates
- **Impact Analysis**: Card prioritization using synergy scores, inclusion rates, and category weights (signature/high_synergy/staple/basic)
- **Budget Analysis**: Cost estimation for completing decks with missing high-impact cards

## Development Commands

All development commands use the `just` command runner for ergonomic argument passing.

### Environment Setup
```bash
# Complete development environment setup (install dependencies and pre-commit hooks)
just setup

# Install dependencies only
just install
```

### Testing
```bash
# Run all tests with coverage
just test

# Run specific test categories
just test -m unit
just test -m integration
just test -m e2e

# Run tests in parallel
just test -n auto

# Run specific test file with verbose output
just test tests/unit/domain/test_card.py -v

# Run with specific markers
just test -m "not slow" -v

# Run tests with coverage report
just test-coverage
```

### Code Quality
```bash
# Run all linting (ruff check + format check)
just lint

# Auto-fix linting issues
just lint --fix

# Format code (black + ruff format)
just format

# Check formatting only
just format-check

# Type checking
just typecheck

# Type check specific file
just typecheck src/ponderous/domain/models/card.py

# Security scan
just security-scan

# Run pre-commit hooks manually
just pre-commit

# Run all validation checks
just validate

# Quick development checks (fast subset)
just quick
```

### Application Commands
```bash
# Run the CLI application
just ponderous --help
just ponderous sync-collection --username your_username --source moxfield

# Alternative alias
just run --help
```

### Project Management
```bash
# Clean build artifacts
just clean

# Build package for distribution
just build

# Full CI validation pipeline
just ci

# View all available commands
just --list
```

## Package Management

This project uses **uv** for Python package management.

### UV_NO_CONFIG Requirement

**Issue**: Global uv configuration (`~/.config/uv/uv.toml`) contains expired AWS CodeArtifact authentication tokens that interfere with dependency resolution, even when project-level overrides are configured.

**Investigation Results**:
- Project has both `uv.toml` and `[tool.uv]` in `pyproject.toml` configured for PyPI-only access
- uv's configuration precedence doesn't allow project-level settings to fully override global CodeArtifact configurations
- Multiple project-level override attempts failed with same CodeArtifact authentication errors

**Required Workaround**:
```bash
# Always use UV_NO_CONFIG=1 to bypass global configuration
export UV_NO_CONFIG=1
uv sync --all-groups
UV_NO_CONFIG=1 uv run --group test pytest
```

**Alternative Solutions**:
1. Remove or fix `~/.config/uv/uv.toml` (requires updating expired CodeArtifact tokens)
2. Check for pip conflicts: `pip config list`

### Project Setup
```bash
# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install all dependencies including dev tools
UV_NO_CONFIG=1 uv sync --all-groups

# Install pre-commit hooks
uv run --group dev pre-commit install

# Verify setup
uv run python -c "import ponderous; print('✅ Ponderous installed')"
```

## Core Configuration Files

- **pyproject.toml**: Project metadata, dependencies, and tool configuration (Black, Ruff, MyPy, pytest)
- **uv.toml**: Project-specific uv settings to override global CodeArtifact configuration
- **pytest.ini**: Legacy pytest configuration (prefer pyproject.toml settings)
- **.pre-commit-config.yaml**: Git hooks for code quality (Black, Ruff, MyPy, Bandit)

## Hooks Configuration

This project uses Claude Code quality gate hooks for automated code analysis at `.claude/hooks/claude_quality_gate.py`.
