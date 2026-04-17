"""Backward compatibility shim for scanner module refactor."""

from __future__ import annotations

import sys

from .scanner import core as _core

# Static re-exports for type-checkers and direct imports.
asdict = _core.asdict
DeviceCapabilities = _core.DeviceCapabilities
ThesslaGreenDeviceScanner = _core.ThesslaGreenDeviceScanner
is_request_cancelled_error = _core.is_request_cancelled_error

# Keep historical import path as an alias to the refactored module.
sys.modules[__name__] = _core
