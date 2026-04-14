"""Plugin to detect unclosed event loops by forcing GC and checking warnings."""
import asyncio
import gc
import warnings

import pytest

_open_loop_ids_before = set()
_leaking_tests = []


@pytest.fixture(autouse=True)
def track_event_loops(request):
    # Collect IDs of currently open loops before the test
    gc.collect()
    gc.collect()
    gc.collect()
    before = set()
    for obj in gc.get_objects():
        try:
            if isinstance(obj, asyncio.AbstractEventLoop) and not obj.is_closed():
                before.add(id(obj))
        except Exception:
            pass

    yield

    # After the test, check for new unclosed loops
    gc.collect()
    gc.collect()
    gc.collect()
    new_loops = []
    for obj in gc.get_objects():
        try:
            if isinstance(obj, asyncio.AbstractEventLoop) and not obj.is_closed():
                if id(obj) not in before:
                    new_loops.append(obj)
        except Exception:
            pass

    if new_loops:
        _leaking_tests.append(request.node.nodeid)
        # Force the warning to be emitted now
        for loop in new_loops:
            warnings.warn(
                f"[LOOP_LEAK] Test '{request.node.nodeid}' left unclosed loop: {loop!r}",
                ResourceWarning,
                stacklevel=1,
            )


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if _leaking_tests:
        terminalreporter.write_sep("=", "UNCLOSED EVENT LOOP LEAKS")
        for t in _leaking_tests:
            terminalreporter.write_line(f"  LEAK: {t}")
