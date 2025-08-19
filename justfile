# Ponderous MTG Collection Analyzer - Development Commands
#
# A modern command runner for the Ponderous project using 'just'
# All commands support argument passing for maximum flexibility
#
# Quick start:
#   just setup           # Complete environment setup
#   just test            # Run all tests
#   just test file.py -v # Run specific test with verbose output
#   just lint --fix      # Run linting with auto-fix
#   just ponderous --help # Run the CLI application

# Default recipe to display help
default:
    @just --list

# === Development Environment ===

# Complete development environment setup
setup *ARGS:
    @echo "🏗️ Setting up development environment..."
    UV_NO_CONFIG=1 uv sync --all-groups {{ARGS}}
    @if [[ "{{ARGS}}" != *"--no-hooks"* ]]; then \
        echo "📦 Installing pre-commit hooks..."; \
        UV_NO_CONFIG=1 uv run --group dev pre-commit install; \
    fi
    @echo "✅ Setup complete!"

# Install dependencies only
install:
    @echo "📦 Installing dependencies..."
    UV_NO_CONFIG=1 uv sync --all-groups
    @echo "✅ Dependencies installed!"

# === Testing Commands ===

# Run tests with full pytest argument support
test *ARGS:
    @if [ -n "{{ARGS}}" ]; then \
        echo "🧪 Running tests with args: {{ARGS}}"; \
    else \
        echo "🧪 Running all tests..."; \
    fi
    @UV_NO_CONFIG=1 uv run --group test pytest {{ARGS}}

# Run tests with coverage report
test-coverage *ARGS:
    @echo "🧪 Running tests with coverage..."
    UV_NO_CONFIG=1 uv run --group test pytest --cov=src/ponderous --cov-report=term-missing --cov-report=html {{ARGS}}

# === Code Quality Commands ===

# Run linting with full ruff check argument support
lint *ARGS:
    @if [ -n "{{ARGS}}" ]; then \
        echo "🔍 Running linting with args: {{ARGS}}"; \
    else \
        echo "🔍 Running linting on all files..."; \
    fi
    @UV_NO_CONFIG=1 uv run --group lint ruff check {{ARGS}}

# Format code with full ruff format argument support
format *ARGS:
    @if [ -n "{{ARGS}}" ]; then \
        echo "🎨 Formatting code with args: {{ARGS}}"; \
    else \
        echo "🎨 Formatting all code..."; \
    fi
    @UV_NO_CONFIG=1 uv run --group lint ruff format {{ARGS}}

# Check code formatting without making changes
format-check *ARGS:
    @echo "🎨 Checking code formatting..."
    UV_NO_CONFIG=1 uv run --group lint ruff format --check {{ARGS}}

# Run type checking with full mypy argument support
typecheck *ARGS:
    @if [ -n "{{ARGS}}" ]; then \
        echo "🔍 Running type checking with args: {{ARGS}}"; \
    else \
        echo "🔍 Running type checking on all files..."; \
    fi
    @UV_NO_CONFIG=1 uv run --group lint mypy src {{ARGS}}

# Security scan with bandit
security-scan *ARGS:
    @echo "🛡️ Running security scan..."
    @UV_NO_CONFIG=1 uv run --group dev bandit -r src/ {{ARGS}}

# === Application Commands ===

# Run the ponderous CLI application with full argument support
ponderous *ARGS:
    @UV_NO_CONFIG=1 uv run ponderous {{ARGS}}

# Alias for ponderous command
run *ARGS:
    @UV_NO_CONFIG=1 uv run ponderous {{ARGS}}

# === Composite Commands ===

# Run all validation checks (lint, format-check, typecheck)
validate *ARGS:
    @echo "🔍 Running all validation checks..."
    @just lint {{ARGS}}
    @just format-check {{ARGS}}
    @just typecheck {{ARGS}}
    @echo "✅ All validation checks complete!"

# Quick development checks (fast subset for development workflow)
quick *ARGS:
    @echo "⚡ Running quick checks..."
    @just lint --select E,W {{ARGS}}
    @just format-check {{ARGS}}
    @echo "✅ Quick checks complete!"

# Full CI validation pipeline
ci:
    @echo "🚀 Running full CI validation..."
    @just lint
    @just format-check
    @just typecheck
    @just test
    @echo "✅ CI validation complete!"

# Run all validation with test coverage (for comprehensive checks)
ci-coverage:
    @echo "🚀 Running CI with coverage..."
    @just validate
    @just test-coverage
    @echo "✅ CI with coverage complete!"

# === Utility Commands ===

# Clean up build artifacts and cache directories
clean:
    @echo "🧹 Cleaning up build artifacts..."
    rm -rf .pytest_cache/
    rm -rf .mypy_cache/
    rm -rf htmlcov/
    rm -rf .coverage
    rm -rf dist/
    rm -rf build/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    @echo "✅ Cleanup complete!"

# Build package for distribution
build *ARGS:
    @echo "📦 Building package..."
    @UV_NO_CONFIG=1 uv build {{ARGS}}
    @echo "✅ Package built successfully!"

# Install pre-commit hooks manually
install-hooks:
    @echo "🪝 Installing pre-commit hooks..."
    UV_NO_CONFIG=1 uv run --group dev pre-commit install
    @echo "✅ Pre-commit hooks installed!"

# Run pre-commit hooks manually on all files
run-hooks *ARGS:
    @echo "🪝 Running pre-commit hooks..."
    UV_NO_CONFIG=1 uv run --group dev pre-commit run --all-files {{ARGS}}

# Diagnose development environment setup
doctor:
    @echo "🏥 Diagnosing development environment..."
    @echo "Python version:"
    @python --version
    @echo ""
    @echo "UV version:"
    @uv --version || echo "UV not found"
    @echo ""
    @echo "Just version:"
    @just --version
    @echo ""
    @echo "Virtual environment:"
    @echo "$VIRTUAL_ENV"
    @echo ""
    @echo "Installed packages:"
    @UV_NO_CONFIG=1 uv pip list | head -10

# Show comprehensive help with examples
help:
    @echo "Ponderous MTG Collection Analyzer - Development Commands"
    @echo ""
    @echo "🏗️  Environment Setup:"
    @echo "  just setup              Complete development setup"
    @echo "  just install            Install dependencies only"
    @echo "  just clean              Clean build artifacts"
    @echo ""
    @echo "🧪 Testing:"
    @echo "  just test               Run all tests"
    @echo "  just test file.py       Run specific test file"
    @echo "  just test -k pattern    Run tests matching pattern"
    @echo "  just test -v --tb=short Run with verbose output and short traceback"
    @echo "  just test --cov         Run with coverage"
    @echo "  just test-coverage      Run with full coverage report"
    @echo ""
    @echo "🔍 Code Quality:"
    @echo "  just lint               Check all files"
    @echo "  just lint src/          Check specific directory"
    @echo "  just lint --fix         Auto-fix issues"
    @echo "  just lint --show-fixes  Preview fixes"
    @echo ""
    @echo "  just format             Format all code"
    @echo "  just format src/        Format specific directory"
    @echo "  just format --check     Check formatting only"
    @echo "  just format --diff      Show formatting changes"
    @echo ""
    @echo "  just typecheck          Check all files"
    @echo "  just typecheck src/     Check specific directory"
    @echo "  just typecheck --strict Enable strict mode"
    @echo ""
    @echo "🚀 Application:"
    @echo "  just ponderous --help   Show CLI help"
    @echo "  just run --help         Alias for ponderous"
    @echo "  just ponderous sync-collection user --force"
    @echo "  just ponderous discover-commanders --user-id 123"
    @echo ""
    @echo "⚡ Quick Commands:"
    @echo "  just validate           Run all quality checks"
    @echo "  just quick              Fast development checks"
    @echo "  just ci                 Full CI validation"
    @echo "  just doctor             Diagnose environment"
    @echo ""
    @echo "💡 Tips:"
    @echo "  - All commands support passing arguments to underlying tools"
    @echo "  - Use 'just --list' to see all available commands"
    @echo "  - Use 'just COMMAND --help' for tool-specific help"
