## Summary
- [ ] Explain what changed and why.

## Maintainability checklist (required for large refactors)
- [ ] I checked whether changed methods/files exceed maintainability thresholds.
- [ ] For large methods/files, I provided extraction rationale.
- [ ] I documented behavior compatibility / facade/re-export compatibility where applicable.
- [ ] I listed test impact (new/updated tests, including contract tests when retry/error semantics changed).
- [ ] I included a short rollback plan for risky refactors.

## Validation
- [ ] `ruff check ...`
- [ ] `pytest ...`
- [ ] `python tools/check_maintainability.py`

## Notes
- Additional context / migration notes / known limitations.
