from pathlib import Path

from tools.check_maintainability import (
    DEFAULT_MAX_FILE_LINES,
    DEFAULT_MAX_FUNCTION_LINES,
    STRICT_PATH_LIMITS,
    _limits_for_path,
)


def test_limits_for_current_hotspots_match_strict_limits() -> None:
    assert (
        _limits_for_path(
            Path("custom_components/thessla_green_modbus/coordinator/coordinator.py"),
            DEFAULT_MAX_FILE_LINES,
            DEFAULT_MAX_FUNCTION_LINES,
        )
        == STRICT_PATH_LIMITS[
            "custom_components/thessla_green_modbus/coordinator/coordinator.py"
        ]
    )
    assert (
        _limits_for_path(
            Path("custom_components/thessla_green_modbus/scanner/io_read.py"),
            DEFAULT_MAX_FILE_LINES,
            DEFAULT_MAX_FUNCTION_LINES,
        )
        == STRICT_PATH_LIMITS[
            "custom_components/thessla_green_modbus/scanner/io_read.py"
        ]
    )


def test_limits_for_path_supports_repo_absolute_paths() -> None:
    repo_absolute = Path.cwd() / "custom_components/thessla_green_modbus/scanner/io_read.py"
    assert _limits_for_path(
        repo_absolute,
        DEFAULT_MAX_FILE_LINES,
        DEFAULT_MAX_FUNCTION_LINES,
    ) == STRICT_PATH_LIMITS["custom_components/thessla_green_modbus/scanner/io_read.py"]


def test_limits_for_non_strict_path_returns_defaults() -> None:
    assert _limits_for_path(
        Path("custom_components/thessla_green_modbus/__init__.py"),
        100,
        10,
    ) == (100, 10)
