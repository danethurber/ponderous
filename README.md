# Ponderous 🧠⚡

**Thoughtful analysis of your MTG collection to discover buildable Commander decks**

Ponderous analyzes your Magic: The Gathering card collections against EDHREC deck statistics to recommend buildable Commander decks. Named to evoke the careful, deliberate analysis that goes into serious deck construction—like the MTG card "Ponder"—Ponderous helps players optimize their existing collections by identifying which decks they can build with minimal additional investment.

[![Tests](https://github.com/danethurber/ponderous/workflows/Tests/badge.svg)](https://github.com/danethurber/ponderous/actions)
[![Coverage](https://codecov.io/gh/danethurber/ponderous/branch/main/graph/badge.svg)](https://codecov.io/gh/danethurber/ponderous)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## ✨ Features

-   **🎯 Commander Discovery**: Find optimal commanders based on your collection
-   **📊 Deck Analysis**: Calculate completion percentages and buildability scores
-   **💰 Budget Analysis**: Estimate costs to complete deck variants
-   **🔍 Advanced Filtering**: Filter by color identity, budget, archetype, and themes
-   **📋 Missing Cards**: Identify high-impact missing cards for each deck
-   **👥 Multi-User Support**: Manage multiple collections from different sources
-   **⚡ Fast Analysis**: Sub-30 second analysis for 500+ card collections

## 🚀 Quick Start

### Prerequisites

-   Python 3.11
-   Git

### Development Environment Setup

#### 1. Install pyenv (Python version management)

```bash
# macOS
brew install pyenv

# Linux
curl https://pyenv.run | bash

# Add to your shell profile (.bashrc, .zshrc, etc.)
echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc

# Reload shell
source ~/.bashrc
```

#### 2. Install Python 3.11 with pyenv

```bash
# Install Python 3.11
pyenv install 3.11
pyenv global 3.11

# Verify Python version
python --version
```

#### 3. Install uv (Python package manager)

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip
pip install uv

# Verify installation
uv --version
```

#### 4. Clone and setup the project

```bash
# Clone repository
git clone https://github.com/danethurber/ponderous.git
cd ponderous

# Create and activate virtual environment with uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install all dependencies (including dev dependencies)
uv sync --all-groups

# Verify installation
uv run python -c "import ponderous; print('✅ Ponderous installed successfully')"
```

> **Note**: If you encounter dependency resolution errors, you may have global uv configuration interfering with CodeArtifact or other private registries. This project requires PyPI-only dependencies.
>
> **Quick fix**: Use `export UV_NO_CONFIG=1` before running uv commands to bypass global configuration.
>
> **Permanent fix**: Check `~/.config/uv/uv.toml` for expired CodeArtifact tokens and either remove the file or update the tokens. You can also run `pip config list` to check for conflicting pip configuration.

### Alternative: Install from PyPI (coming soon)

```bash
# When published to PyPI
uv add ponderous
```

### Basic Usage

```bash
# Sync your collection from Moxfield
ponderous sync-collection --username your_moxfield_username --source moxfield

# Discover commanders you can build
ponderous discover-commanders --user-id your_moxfield_username \
  --min-completion 0.8 \
  --budget-bracket mid

# Get deck recommendations for a specific commander
ponderous recommend-decks "Meren of Clan Nel Toth" \
  --user-id your_moxfield_username \
  --budget mid \
  --min-completion 0.75

# Analyze your collection strengths
ponderous analyze-collection --user-id your_moxfield_username \
  --show-themes --show-gaps
```

## 🎯 Example Output

```
🔍 Commander Discovery for your_username
Collection: 847 unique cards, $12,450 total value
============================================================

Rank | Commander                  | Colors | Budget  | Archetype | Owned | Completion | Cost  | Pop  | Power
-----|----------------------------|--------|---------|-----------|-------|------------|-------|------|-------
  1  | Meren of Clan Nel Toth     | BG     | Mid     | Combo     | 78/89 | 87.6%      | $67   | 8.2k | 8.5
  2  | Atraxa, Praetors' Voice    | WUBG   | High    | Control   | 84/98 | 85.7%      | $245  | 12k  | 8.9
  3  | The Gitrog Monster         | BG     | Mid     | Combo     | 71/84 | 84.5%      | $89   | 4.1k | 8.1

💡 Analysis Summary:
   • Best Color Identity: Golgai (BG) - 3 top recommendations
   • Optimal Budget Range: Mid ($200-500) - highest completion rates
   • Strongest Archetype: Combo - leverages your graveyard synergies
```

## 🛠️ Development

### Setup Development Environment

Follow the installation steps above, then:

```bash
# Activate the virtual environment (if not already active)
source .venv/bin/activate

# Install pre-commit hooks
uv run pre-commit install

# Verify development setup
uv run pytest --version
uv run black --version
uv run ruff --version
```

### Running Tests

```bash
# Run all tests with coverage (includes pytest-sugar for enhanced output)
uv run --group test pytest

# Run specific test categories
uv run --group test pytest -m unit          # Unit tests only
uv run --group test pytest -m integration   # Integration tests only
uv run --group test pytest -m e2e           # End-to-end tests only

# Run tests in parallel
uv run --group test pytest -n auto

# Run with verbose output
uv run --group test pytest -v
```

### Code Quality

```bash
# Format code
uv run --group lint black src tests

# Lint code
uv run --group lint ruff check src tests

# Type checking
uv run --group lint mypy src

# Run all quality checks
uv run --group dev pre-commit run --all-files
```

## 🏗️ Architecture

Ponderous follows clean architecture principles with clear separation of concerns:

```
src/ponderous/
├── domain/           # Business logic and entities
│   ├── models/       # Domain models (Commander, Deck, Collection)
│   ├── services/     # Domain services (analysis algorithms)
│   └── repositories/ # Abstract repository interfaces
├── infrastructure/   # External services and data access
│   ├── moxfield/     # Moxfield API client
│   ├── edhrec/       # EDHREC scraper
│   ├── database/     # DuckDB implementation
│   └── etl/          # dlt pipelines
├── application/      # Application services and use cases
│   ├── use_cases/    # Business use cases
│   └── services/     # Application services
├── presentation/     # CLI interface
│   ├── cli.py        # Click commands
│   ├── formatters/   # Output formatting
│   └── validators/   # Input validation
└── shared/           # Shared utilities
    ├── config.py     # Configuration management
    ├── exceptions.py # Custom exceptions
    └── utils.py      # Utility functions
```

## 📊 Technology Stack

-   **Language**: Python 3.11
-   **CLI Framework**: Click
-   **Database**: DuckDB (for fast analytical queries)
-   **ETL**: dlt (Data Load Tool)
-   **Web Scraping**: Beautiful Soup 4
-   **HTTP Client**: httpx
-   **Testing**: pytest with comprehensive coverage
-   **Code Quality**: black, ruff, mypy, pre-commit

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Principles

-   **Test-Driven Development**: Write tests first, then implement
-   **Clean Code**: Follow clean code principles and PEP 8
-   **Type Safety**: Use type hints throughout the codebase
-   **Documentation**: Maintain comprehensive documentation

### Quality Standards

-   95%+ test coverage required
-   All tests must pass
-   Code must be formatted with black
-   Must pass ruff linting
-   Must pass mypy type checking

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

-   [EDHREC](https://edhrec.com) for comprehensive Commander statistics
-   [Moxfield](https://moxfield.com) for collection management platform
-   The Magic: The Gathering community for inspiration and feedback

## 📞 Support

-   🐛 **Bug Reports**: [GitHub Issues](https://github.com/danethurber/ponderous/issues)
-   💡 **Feature Requests**: [GitHub Discussions](https://github.com/danethurber/ponderous/discussions)
-   📖 **Documentation**: [GitHub Repository](https://github.com/danethurber/ponderous)
