"""Simple maintainability gate for file/function size limits."""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAX_FILE_LINES = 1300
DEFAULT_MAX_FUNCTION_LINES = 260
DEFAULT_SCAN_ROOTS = ("custom_components/thessla_green_modbus",)

STRICT_PATH_LIMITS: dict[str, tuple[int, int]] = {
    "custom_components/thessla_green_modbus/coordinator/coordinator.py": (1200, 220),
    "custom_components/thessla_green_modbus/config_flow.py": (1000, 220),
    "custom_components/thessla_green_modbus/modbus_transport.py": (930, 210),
    "custom_components/thessla_green_modbus/registers/loader.py": (860, 210),
    "custom_components/thessla_green_modbus/scanner/io_read.py": (820, 210),
    "custom_components/thessla_green_modbus/scanner/core.py": (760, 210),
}


def _limits_for_path(
    path: Path, default_file_lines: int, default_function_lines: int
) -> tuple[int, int]:
    as_posix = path.as_posix()
    for strict_path, limits in STRICT_PATH_LIMITS.items():
        if as_posix.endswith(strict_path):
            return limits
    return default_file_lines, default_function_lines


@dataclass(slots=True)
class Violation:
    """Represents one maintainability gate violation."""

    path: Path
    message: str


def _iter_python_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        files.extend(p for p in root.rglob("*.py") if p.is_file())
    return sorted(files)


def _function_end_line(node: ast.AST) -> int:
    end = getattr(node, "end_lineno", None)
    if isinstance(end, int):
        return end
    return getattr(node, "lineno", 0)


def _collect_function_violations(
    path: Path, tree: ast.AST, max_function_lines: int
) -> list[Violation]:
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = getattr(node, "lineno", 0)
        end = _function_end_line(node)
        if start <= 0 or end < start:
            continue
        length = end - start + 1
        if length > max_function_lines:
            violations.append(
                Violation(
                    path=path,
                    message=(
                        f"function '{node.name}' is {length} lines "
                        f"(limit: {max_function_lines}, lines {start}-{end})"
                    ),
                )
            )
    return violations


def check_limits(
    roots: list[Path], max_file_lines: int, max_function_lines: int
) -> list[Violation]:
    """Return all maintainability violations for configured roots."""
    violations: list[Violation] = []
    for path in _iter_python_files(roots):
        source = path.read_text(encoding="utf-8")
        path_max_file_lines, path_max_function_lines = _limits_for_path(
            path,
            default_file_lines=max_file_lines,
            default_function_lines=max_function_lines,
        )
        line_count = len(source.splitlines())
        if line_count > path_max_file_lines:
            violations.append(
                Violation(
                    path=path,
                    message=f"file has {line_count} lines (limit: {path_max_file_lines})",
                )
            )
        tree = ast.parse(source, filename=str(path))
        violations.extend(_collect_function_violations(path, tree, path_max_function_lines))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Maintainability gate checks for Python source.")
    parser.add_argument(
        "--max-file-lines",
        type=int,
        default=DEFAULT_MAX_FILE_LINES,
        help=f"Maximum number of lines per file (default: {DEFAULT_MAX_FILE_LINES}).",
    )
    parser.add_argument(
        "--max-function-lines",
        type=int,
        default=DEFAULT_MAX_FUNCTION_LINES,
        help=f"Maximum number of lines per function (default: {DEFAULT_MAX_FUNCTION_LINES}).",
    )
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        help=(
            "Root directory to scan (can be repeated). "
            f"Defaults to {', '.join(DEFAULT_SCAN_ROOTS)}."
        ),
    )
    args = parser.parse_args()

    roots = [Path(root) for root in (args.root or list(DEFAULT_SCAN_ROOTS))]
    violations = check_limits(
        roots=roots,
        max_file_lines=args.max_file_lines,
        max_function_lines=args.max_function_lines,
    )
    if not violations:
        print("Maintainability gate passed.")
        return 0

    print("Maintainability gate failed:")
    for violation in violations:
        print(f"- {violation.path}: {violation.message}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
