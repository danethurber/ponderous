#!/usr/bin/env python3
"""
Claude Code Quality Gate Hook for Ponderous

This hook runs automatically when files change to perform quality checks.
It integrates with Claude Code for intelligent code analysis and suggestions.

Usage:
    python .claude/hooks/claude_quality_gate.py [file_path...]
    python .claude/hooks/claude_quality_gate.py src/ponderous/domain/models/card.py
    python .claude/hooks/claude_quality_gate.py --quick-check  # Quick check mode

Environment Variables:
    CLAUDE_HOOK_ENABLED: Enable/disable the hook (default: true)
    CLAUDE_HOOK_STRICT: Fail on any issues (default: false)
    PONDEROUS_LOG_LEVEL: Logging level for hook output
"""

import argparse
import ast
import os
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

# Modern Python type hints used throughout

# TOML checking removed per user preference


@dataclass
class QualityIssue:
    """Represents a quality issue found in code."""

    file_path: Path
    line_number: int | None
    severity: str  # "error", "warning", "info"
    category: str  # "style", "security", "performance", "documentation", "complexity"
    message: str
    suggestion: str | None = None


class QualityChecker(ABC):
    """Abstract base class for quality checkers."""

    @abstractmethod
    def check_file(self, file_path: Path) -> list[QualityIssue]:
        """Check a file and return quality issues."""
        pass


class PythonQualityChecker(QualityChecker):
    """Python-specific quality checker using AST analysis."""

    def __init__(self) -> None:
        """Initialize Python quality checker with default thresholds."""
        self.max_function_length = 50
        self.max_class_length = 300
        self.max_complexity = 10
        self.required_docstring_types = {"FunctionDef", "ClassDef", "AsyncFunctionDef"}

    def check_file(self, file_path: Path) -> list[QualityIssue]:
        """Check Python file for quality issues."""
        issues = []

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as e:
            issues.append(
                QualityIssue(
                    file_path=file_path,
                    line_number=e.lineno,
                    severity="error",
                    category="syntax",
                    message=f"Syntax error: {e.msg}",
                    suggestion="Fix syntax error before proceeding",
                )
            )
            return issues
        except Exception as e:
            issues.append(
                QualityIssue(
                    file_path=file_path,
                    line_number=None,
                    severity="error",
                    category="parsing",
                    message=f"Failed to parse file: {e}",
                    suggestion="Check file encoding and syntax",
                )
            )
            return issues

        # Run AST-based checks
        issues.extend(self._check_docstrings(tree, file_path))
        issues.extend(self._check_function_length(tree, file_path))
        issues.extend(self._check_class_length(tree, file_path))
        issues.extend(self._check_complexity(tree, file_path))
        issues.extend(self._check_imports(tree, file_path))
        issues.extend(self._check_type_annotations(tree, file_path))

        return issues

    def _check_docstrings(self, tree: ast.AST, file_path: Path) -> list[QualityIssue]:
        """Check for missing or inadequate docstrings."""
        issues = []

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
                and type(node).__name__ in self.required_docstring_types
            ):
                if not ast.get_docstring(node):
                    issues.append(
                        QualityIssue(
                            file_path=file_path,
                            line_number=node.lineno,
                            severity="warning",
                            category="documentation",
                            message=f"Missing docstring for {type(node).__name__} '{node.name}'",
                            suggestion="Add comprehensive docstring with description, args, and returns",
                        )
                    )
                else:
                    # Check docstring quality
                    docstring = ast.get_docstring(node)
                    if docstring and len(docstring.split()) < 3:
                        issues.append(
                            QualityIssue(
                                file_path=file_path,
                                line_number=node.lineno,
                                severity="info",
                                category="documentation",
                                message=f"Brief docstring for {type(node).__name__} '{node.name}'",
                                suggestion="Consider expanding docstring with more detail",
                            )
                        )

        return issues

    def _check_function_length(
        self, tree: ast.AST, file_path: Path
    ) -> list[QualityIssue]:
        """Check for overly long functions."""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                # Calculate function length using end_lineno if available, otherwise approximate
                if hasattr(node, "end_lineno") and node.end_lineno:
                    length = node.end_lineno - node.lineno + 1
                else:
                    # Fallback: count lines by finding nodes with line numbers within function
                    function_lines = set()
                    for child in ast.walk(node):
                        if hasattr(child, "lineno"):
                            function_lines.add(child.lineno)
                    if function_lines:
                        length = max(function_lines) - min(function_lines) + 1
                    else:
                        length = 1  # Single line function

                if length > self.max_function_length:
                    issues.append(
                        QualityIssue(
                            file_path=file_path,
                            line_number=node.lineno,
                            severity="warning",
                            category="complexity",
                            message=f"Function '{node.name}' is {length} lines (max: {self.max_function_length})",
                            suggestion="Consider breaking into smaller, focused functions",
                        )
                    )

        return issues

    def _check_class_length(self, tree: ast.AST, file_path: Path) -> list[QualityIssue]:
        """Check for overly long classes."""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Calculate class length using end_lineno if available, otherwise approximate
                if hasattr(node, "end_lineno") and node.end_lineno:
                    length = node.end_lineno - node.lineno + 1
                else:
                    # Fallback: count lines by finding nodes with line numbers within class
                    class_lines = set()
                    for child in ast.walk(node):
                        if hasattr(child, "lineno"):
                            class_lines.add(child.lineno)
                    if class_lines:
                        length = max(class_lines) - min(class_lines) + 1
                    else:
                        length = 1  # Single line class

                if length > self.max_class_length:
                    issues.append(
                        QualityIssue(
                            file_path=file_path,
                            line_number=node.lineno,
                            severity="warning",
                            category="complexity",
                            message=f"Class '{node.name}' is {length} lines (max: {self.max_class_length})",
                            suggestion="Consider splitting into smaller, focused classes",
                        )
                    )

        return issues

    def _check_complexity(self, tree: ast.AST, file_path: Path) -> list[QualityIssue]:
        """Check cyclomatic complexity."""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                complexity = self._calculate_complexity(node)
                if complexity > self.max_complexity:
                    issues.append(
                        QualityIssue(
                            file_path=file_path,
                            line_number=node.lineno,
                            severity="warning",
                            category="complexity",
                            message=f"Function '{node.name}' has complexity {complexity} (max: {self.max_complexity})",
                            suggestion="Reduce branching and nesting complexity",
                        )
                    )

        return issues

    def _calculate_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity of a function."""
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            if isinstance(
                child, ast.If | ast.While | ast.For | ast.AsyncFor | ast.ExceptHandler
            ):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1

        return complexity

    def _check_imports(self, tree: ast.AST, file_path: Path) -> list[QualityIssue]:
        """Check import organization and style."""
        issues = []

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import | ast.ImportFrom):
                imports.append((node.lineno, node))

        # Check if imports are at the top of the file
        non_import_lines = []
        for node in ast.walk(tree):
            if not isinstance(
                node, ast.Import | ast.ImportFrom | ast.Module
            ) and hasattr(node, "lineno"):
                non_import_lines.append(node.lineno)

        if imports and non_import_lines:
            first_non_import = min(non_import_lines)
            late_imports = [imp for line, imp in imports if line > first_non_import]

            for imp in late_imports:
                issues.append(
                    QualityIssue(
                        file_path=file_path,
                        line_number=imp.lineno,
                        severity="info",
                        category="style",
                        message="Import not at top of file",
                        suggestion="Move imports to the top of the file",
                    )
                )

        return issues

    def _check_type_annotations(
        self, tree: ast.AST, file_path: Path
    ) -> list[QualityIssue]:
        """Check for missing type annotations."""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                # Skip dunder methods and test functions
                if node.name.startswith("__") or node.name.startswith("test_"):
                    continue

                # Check return annotation
                if not node.returns:
                    issues.append(
                        QualityIssue(
                            file_path=file_path,
                            line_number=node.lineno,
                            severity="info",
                            category="typing",
                            message=f"Function '{node.name}' missing return type annotation",
                            suggestion="Add return type annotation for better type safety",
                        )
                    )

                # Check parameter annotations
                for arg in node.args.args:
                    if not arg.annotation and arg.arg != "self" and arg.arg != "cls":
                        issues.append(
                            QualityIssue(
                                file_path=file_path,
                                line_number=node.lineno,
                                severity="info",
                                category="typing",
                                message=f"Parameter '{arg.arg}' in function '{node.name}' missing type annotation",
                                suggestion="Add type annotation for better type safety",
                            )
                        )

        return issues


class TestFileQualityChecker(PythonQualityChecker):
    """Quality checker specifically for test files."""

    def __init__(self) -> None:
        """Initialize test file quality checker with more lenient thresholds."""
        super().__init__()
        # More lenient for test files
        self.max_function_length = 80
        self.max_complexity = 15
        self.required_docstring_types = {
            "ClassDef"
        }  # Only require docstrings for test classes

    def check_file(self, file_path: Path) -> list[QualityIssue]:
        """Check test file with test-specific rules."""
        issues = super().check_file(file_path)

        # Add test-specific checks
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
            issues.extend(self._check_test_patterns(tree, file_path))
        except Exception as e:
            # AST parsing issues already caught by parent
            print(f"Warning: Failed to parse {file_path} for test patterns: {e}")

        return issues

    def _check_test_patterns(
        self, tree: ast.AST, file_path: Path
    ) -> list[QualityIssue]:
        """Check for good test patterns."""
        issues = []

        test_functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                test_functions.append(node)

        # Check for at least one assertion in test functions
        for func in test_functions:
            has_assertion = any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id.startswith("assert")
                for call in ast.walk(func)
            )

            if not has_assertion:
                issues.append(
                    QualityIssue(
                        file_path=file_path,
                        line_number=func.lineno,
                        severity="warning",
                        category="testing",
                        message=f"Test function '{func.name}' contains no assertions",
                        suggestion="Add assertions to verify expected behavior",
                    )
                )

        return issues


class ClaudeQualityGate:
    """Enhanced Claude Code integration for automated quality checks."""

    def __init__(
        self, strict_mode: bool = False, enabled: bool = True, quick_mode: bool = False
    ):
        """Initialize quality gate.

        Args:
            strict_mode: Fail on any issues found
            enabled: Whether hook is enabled
            quick_mode: Run only essential checks (errors and critical warnings)
        """
        self.strict_mode = strict_mode
        self.enabled = enabled
        self.quick_mode = quick_mode
        self.issues_found: list[QualityIssue] = []
        self.checkers: dict[str, QualityChecker] = {
            "python": PythonQualityChecker(),
            "test": TestFileQualityChecker(),
        }

    def check_file(self, file_path: Path) -> bool:
        """Check a single file for quality issues.

        Args:
            file_path: Path to file to check

        Returns:
            True if file passes checks, False otherwise
        """
        if not self.enabled:
            return True

        if not file_path.exists():
            self.issues_found.append(
                QualityIssue(
                    file_path=file_path,
                    line_number=None,
                    severity="error",
                    category="file",
                    message="File not found",
                    suggestion="Ensure file path is correct",
                )
            )
            return False

        print(f"🔍 Checking {file_path}")

        # Determine file type and run appropriate checker
        if file_path.suffix == ".py":
            return self._check_python_file(file_path)
        elif file_path.suffix in [".md", ".rst"]:
            return self._check_documentation_file(file_path)
        elif file_path.suffix in [".yml", ".yaml"]:
            return self._check_yaml_file(file_path)
        # TOML checking removed per user preference
        else:
            print(f"✅ {file_path} (unknown type, skipped)")
            return True

    def _check_python_file(self, file_path: Path) -> bool:
        """Check a Python file for quality issues."""
        if self._is_test_file(file_path):
            checker = self.checkers["test"]
        else:
            checker = self.checkers["python"]

        issues = checker.check_file(file_path)
        self.issues_found.extend(issues)

        # Run external tools
        self._run_external_checks(file_path)

        # Determine if file passed
        return self._evaluate_check_results(file_path, issues)

    def _evaluate_check_results(
        self, file_path: Path, issues: list[QualityIssue]
    ) -> bool:
        """Evaluate check results and print appropriate message."""
        error_count = sum(1 for issue in issues if issue.severity == "error")
        warning_count = sum(1 for issue in issues if issue.severity == "warning")
        info_count = sum(1 for issue in issues if issue.severity == "info")

        if error_count > 0:
            print(f"❌ {file_path} ({error_count} errors)")
            return False
        elif self.quick_mode and warning_count == 0:
            # In quick mode, only report if there are warnings or errors
            return True
        else:
            if warning_count > 0 or info_count > 0:
                if self.quick_mode:
                    print(f"⚠️  {file_path} ({warning_count} warnings)")
                else:
                    print(
                        f"⚠️  {file_path} ({warning_count} warnings, {info_count} suggestions)"
                    )
            else:
                print(f"✅ {file_path}")
            return True

    def _is_test_file(self, file_path: Path) -> bool:
        """Check if file is a test file."""
        return (
            "test" in file_path.parts
            or file_path.name.startswith("test_")
            or file_path.name.endswith("_test.py")
        )

    def _run_external_checks(self, file_path: Path) -> None:
        """Run external quality tools."""
        # External tools disabled for hook simplicity
        # Run manually: UV_NO_CONFIG=1 uv run ruff check <file>
        # Run manually: UV_NO_CONFIG=1 uv run mypy <file>
        _ = file_path  # Explicitly mark as intentionally unused

    def _check_documentation_file(self, file_path: Path) -> bool:
        """Check documentation file for basic issues."""
        try:
            content = file_path.read_text(encoding="utf-8")
            if len(content.strip()) == 0:
                self.issues_found.append(
                    QualityIssue(
                        file_path=file_path,
                        line_number=None,
                        severity="warning",
                        category="documentation",
                        message="Empty documentation file",
                        suggestion="Add content to the documentation file",
                    )
                )
                return False
            print(f"✅ {file_path}")
            return True
        except Exception as e:
            self.issues_found.append(
                QualityIssue(
                    file_path=file_path,
                    line_number=None,
                    severity="error",
                    category="file",
                    message=f"Failed to read file: {e}",
                    suggestion="Check file encoding and permissions",
                )
            )
            return False

    def _check_yaml_file(self, file_path: Path) -> bool:
        """Check YAML file for syntax issues."""
        try:
            import yaml

            content = file_path.read_text(encoding="utf-8")
            yaml.safe_load(content)
            print(f"✅ {file_path}")
            return True
        except yaml.YAMLError as e:
            self.issues_found.append(
                QualityIssue(
                    file_path=file_path,
                    line_number=getattr(e, "problem_mark", {}).get("line"),
                    severity="error",
                    category="syntax",
                    message=f"YAML syntax error: {e}",
                    suggestion="Fix YAML syntax errors",
                )
            )
            return False
        except ImportError:
            print(f"⚠️  {file_path} (yaml module not available)")
            return True
        except Exception as e:
            self.issues_found.append(
                QualityIssue(
                    file_path=file_path,
                    line_number=None,
                    severity="error",
                    category="file",
                    message=f"Failed to parse YAML: {e}",
                    suggestion="Check file format and encoding",
                )
            )
            return False

    # TOML checking method removed per user preference

    def run_checks(self, file_paths: list[Path]) -> bool:
        """Run quality checks on multiple files."""
        if not self.enabled:
            print("🔕 Claude quality gate disabled")
            return True

        print("🚀 Running Claude quality gate checks...")

        all_passed = True

        for file_path in file_paths:
            if not self.check_file(file_path):
                all_passed = False

        self._print_summary()

        return all_passed or not self.strict_mode

    def _print_summary(self) -> None:
        """Print summary of quality check results."""
        if not self.issues_found:
            print("\n✨ All quality checks passed!")
            return

        # Group issues by severity
        errors = [i for i in self.issues_found if i.severity == "error"]
        warnings = [i for i in self.issues_found if i.severity == "warning"]
        info = [i for i in self.issues_found if i.severity == "info"]

        self._print_summary_header(errors, warnings, info)
        self._print_issues(errors, "❌ Errors:", show_suggestions=True)
        self._print_warnings(warnings)
        self._print_suggestions(info)

    def _print_summary_header(self, errors: list, warnings: list, info: list) -> None:
        """Print the summary header with counts."""
        print("\n📊 Quality Check Summary:")
        print(f"   Errors: {len(errors)}")
        print(f"   Warnings: {len(warnings)}")
        print(f"   Suggestions: {len(info)}")

    def _print_issues(
        self, issues: list[QualityIssue], header: str, show_suggestions: bool = False
    ) -> None:
        """Print a list of issues with optional suggestions."""
        if not issues:
            return
        print(f"\n{header}")
        for issue in issues:
            location = f":{issue.line_number}" if issue.line_number else ""
            print(f"   {issue.file_path}{location}: {issue.message}")
            if show_suggestions and issue.suggestion:
                print(f"      💡 {issue.suggestion}")

    def _print_warnings(self, warnings: list[QualityIssue]) -> None:
        """Print warnings with truncation for large lists."""
        if not warnings:
            return
        if len(warnings) <= 10:
            self._print_issues(warnings, "⚠️  Warnings:")
        else:
            print(f"\n⚠️  {len(warnings)} warnings found (use --verbose to see all)")

    def _print_suggestions(self, info: list[QualityIssue]) -> None:
        """Print suggestions if few in number."""
        if info and len(info) <= 5:
            self._print_issues(info, "💡 Suggestions:")


def _create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="Claude Code Quality Gate Hook for Ponderous",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python .claude/hooks/claude_quality_gate.py src/ponderous/domain/models/card.py
    python .claude/hooks/claude_quality_gate.py --strict src/ponderous/
    CLAUDE_HOOK_STRICT=true python .claude/hooks/claude_quality_gate.py src/
        """,
    )
    parser.add_argument(
        "files", nargs="*", help="Files to check (default: check git staged files)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on any issues found (warnings treated as errors)",
    )
    parser.add_argument(
        "--disable", action="store_true", help="Disable quality gate checks"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Show all warnings and suggestions"
    )
    parser.add_argument(
        "--quick-check",
        action="store_true",
        help="Quick check mode for hooks (check only critical issues)",
    )
    return parser


def _determine_files_to_check(args: argparse.Namespace) -> list[Path] | int:
    """Determine which files to check based on arguments and context.

    Returns:
        List of file paths to check, or exit code if should exit early.
    """
    if args.quick_check:
        # Quick check mode - check specified files or CLAUDE_FILE_PATHS env var
        if args.files:
            file_paths = [Path(f) for f in args.files if Path(f).exists()]
        else:
            claude_files = os.getenv("CLAUDE_FILE_PATHS")
            if claude_files:
                file_paths = [
                    Path(f.strip())
                    for f in claude_files.split()
                    if Path(f.strip()).exists()
                ]
            else:
                file_paths = []
        if not file_paths:
            return 0  # No valid files to check in quick mode
        return file_paths
    elif args.files:
        file_paths = []
        for file_arg in args.files:
            file_path = Path(file_arg)
            if file_path.is_dir():
                # If directory specified, check all Python files in it
                py_files = list(file_path.rglob("*.py"))
                file_paths.extend(py_files)
            elif file_path.exists():
                file_paths.append(file_path)
            else:
                print(f"⚠️  File not found: {file_path}")

        if not file_paths:
            print("❌ No valid files specified")
            return 1
        return file_paths
    else:
        return _check_git_staged_files()


def _check_git_staged_files() -> list[Path] | int:
    """Check git staged files if available.

    Returns:
        List of staged file paths, or exit code if should exit early.
    """
    try:
        result = subprocess.run(
            [
                "/usr/bin/git",
                "diff",
                "--cached",
                "--name-only",
                "--diff-filter=ACM",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            staged_files = result.stdout.strip().split("\n")
            file_paths = [Path(f) for f in staged_files if Path(f).exists()]
            if file_paths:
                print(f"🔄 Checking {len(file_paths)} staged files...")
                return file_paths
            else:
                print("💡 No staged files to check")
                return 0
        else:
            # Fallback: suggest usage
            if Path(".git").exists():
                print(
                    "💡 No staged files found. Stage files with 'git add' or specify files to check:"
                )
                print(
                    "   Example: python .claude/hooks/claude_quality_gate.py src/ponderous/domain/models/card.py"
                )
                return 0
            else:
                print("💡 Specify files to check:")
                print(
                    "   Example: python .claude/hooks/claude_quality_gate.py src/ponderous/domain/models/card.py"
                )
                return 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("💡 Specify files to check:")
        print(
            "   Example: uv run python scripts/claude_quality_gate.py src/ponderous/domain/models/card.py"
        )
        return 0


def main() -> int:
    """Main entry point for the quality gate hook."""
    parser = _create_argument_parser()
    args = parser.parse_args()

    # Check environment variables
    enabled = (
        not args.disable and os.getenv("CLAUDE_HOOK_ENABLED", "true").lower() == "true"
    )
    strict_mode = (
        args.strict or os.getenv("CLAUDE_HOOK_STRICT", "false").lower() == "true"
    )

    # Create quality gate instance
    quality_gate = ClaudeQualityGate(
        strict_mode=strict_mode, enabled=enabled, quick_mode=args.quick_check
    )

    # Determine which files to check
    file_paths_result = _determine_files_to_check(args)
    if isinstance(file_paths_result, int):
        return file_paths_result  # Early return with exit code
    file_paths = file_paths_result

    # Run quality checks
    success = quality_gate.run_checks(file_paths)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
