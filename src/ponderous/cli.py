"""
CLI interface for Ponderous - MTG Commander deck recommendation tool.

This module provides the command-line interface for analyzing MTG collections
and discovering buildable Commander decks using Click framework and Rich output.

This is the new refactored version that imports from the presentation layer.
"""

# Import the new CLI structure
from ponderous.presentation.cli.base import PonderousContext, handle_exception
from ponderous.presentation.cli.main import cli, main

# Export the main functions for backward compatibility
__all__ = ["cli", "main", "PonderousContext", "handle_exception"]
