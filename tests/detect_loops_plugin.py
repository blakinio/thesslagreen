"""Conftest plugin to detect unclosed event loops after each test."""
import asyncio
import gc


def pytest_runtest_teardown(item, nextitem):
    gc.collect()
    gc.collect()
    gc.collect()
    # Check all objects for unclosed event loops
    for obj in gc.get_objects():
        if isinstance(obj, asyncio.BaseEventLoop):
            if not obj.is_closed():
                print(f"\n[LEAK] Unclosed event loop {obj!r} found after test: {item.nodeid}")


