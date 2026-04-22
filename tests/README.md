# Tests

To run the test suite locally:

```bash
pip install -r requirements-dev.txt
python -m compileall -q custom_components/thessla_green_modbus tests tools
ruff check custom_components tests tools
python tests/run_tests.py --suite stable
```

Running tests ensures the integration works as expected. Some tests may require optional dependencies; run `pytest -k <pattern>` to execute a subset.

## Recommended suites

Use the helper runner for deterministic local checks:

```bash
python tests/run_tests.py --suite stable
python tests/run_tests.py --suite full
python tests/run_tests.py --suite gate
```

- `stable` runs a focused subset that verifies config-flow, services, and scanner cache compatibility.
- `full` runs the complete test tree.
- `gate` runs `stable` and then `full` only when `stable` passes.

## Suggested merge gate

For larger refactors, run both suites in order:

1. `python tests/run_tests.py --suite stable`
2. `python tests/run_tests.py --suite full`

Use `stable` as a fast pre-check and `full` as the final pre-merge gate.
