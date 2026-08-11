---
task_id: TASK-20260811-deep-audit-cleanup
status: implementing
branch: codex/audit-cleanup-20260811
base_branch: main
created: 2026-08-11
updated: 2026-08-11
related_pr: ""
owned_paths:
  - .github/workflows/ci.yaml
  - docs/quality/STATUS.md
  - docs/release_readiness.md
  - docs/ha_quality_scale_audit.md
  - docs/agents/tasks/TASK-20260811-deep-audit-cleanup.md
required_reads:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/tasks/TASK-20260810-ha-integration-10of10-followup.md
search_first:
  - follow-up
  - CODECOV_TOKEN
optional_reads:
  - docs/real_device_validation.md
---

# Deep audit cleanup after HA hardening

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-08-11T12:45:00Z
head: 62e3cb10894767671c7aeb33a5e62b24c82c07ff
branch: codex/audit-cleanup-20260811
pr: none
status: implementing
context_routes:
  - GitHub connector
owned_paths:
  - .github/workflows/ci.yaml
  - docs/quality/STATUS.md
  - docs/release_readiness.md
  - docs/ha_quality_scale_audit.md
  - docs/agents/tasks/TASK-20260811-deep-audit-cleanup.md
proven:
  - main has no open pull requests or issues and no non-main branches before this task
  - TASK-20260810-ha-integration-10of10-followup.md is status done and PR #1763 is merged
  - main@62e3cb1 has nine successful GitHub Actions checks
  - the Tests job reports total coverage 90.78 percent
  - the Codecov upload in the successful Tests job is rejected because no valid tokenless authentication is available
  - current quality/release docs still describe the already-green follow-up CI as pending
  - manifest.json and pyproject.toml require pymodbus>=3.6.1,<4.0
  - physical AirPack post-hardening validation remains an external acceptance gate
derived:
  - use Codecov OIDC rather than introducing a long-lived repository upload secret
unknown:
  - post-hardening behavior on a physical AirPack during reconnect and 24-72 hour soak
conflicts: []
first_failure:
  marker: Codecov upload
  evidence: Tests job 93778480635 reports 'Token required - not valid tokenless upload'
rejected_hypotheses:
  - an unfinished implementation branch exists
  - an open PR or issue is waiting to be completed
changed_paths:
  - docs/agents/tasks/TASK-20260811-deep-audit-cleanup.md
validation:
  - command: main GitHub Actions check-runs inspection
    result: PASS_WITH_NONBLOCKING_CODECOV_UPLOAD_FAILURE
    evidence: main@62e3cb1, Tests job 93778480635
blockers: []
next_action: enable Codecov OIDC in the Tests job and synchronize current quality/release documentation
```
