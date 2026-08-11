---
task_id: TASK-20260811-deep-audit-cleanup
status: verifying
branch: codex/audit-cleanup-20260811
base_branch: main
created: 2026-08-11
updated: 2026-08-11
related_pr: "#1765"
owned_paths:
  - .github/workflows/ci.yaml
  - docs/audits/deep_audit_2026-08-11.md
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
updated_at: 2026-08-11T12:30:00Z
head: a625380f81599dd07fc2600cbd689d087c661d4e
branch: codex/audit-cleanup-20260811
pr: 1765
status: verifying
context_routes:
  - GitHub connector
  - Home Assistant connector (read-only audit)
owned_paths:
  - .github/workflows/ci.yaml
  - docs/audits/deep_audit_2026-08-11.md
  - docs/quality/STATUS.md
  - docs/release_readiness.md
  - docs/ha_quality_scale_audit.md
  - docs/agents/tasks/TASK-20260811-deep-audit-cleanup.md
proven:
  - main had no open pull requests or issues and no non-main branches before this task
  - TASK-20260810-ha-integration-10of10-followup.md is status done and PR #1763 is merged
  - main@62e3cb1 has nine successful GitHub Actions checks
  - baseline Tests job 93778480635 reports total coverage 90.78 percent
  - baseline Codecov upload failed with 'Token required - not valid tokenless upload' while the Tests job remained green
  - PR #1765 Tests job 93786147158 successfully obtained a GitHub OIDC token but Codecov then failed with 'Repository not found'
  - Codecov upload is therefore not a functioning CI/release signal for this repository today
  - current quality/release docs previously described already-green follow-up CI as pending and had stale dependency/version context
  - manifest.json and pyproject.toml on current main require pymodbus>=3.6.1,<4.0 while tag v2.8.3 requires pymodbus>=3.6.0,<4.0
  - physical AirPack post-hardening validation remains an external acceptance gate
  - read-only live HA diagnostics show the installed v2.8.3 integration connected with 337 successful and 0 failed sampled reads, 336 available registers, about 14.258 seconds average update-cycle duration, about 22.555 seconds scan duration, and about 53.134 seconds config-entry setup duration
  - live runtime is the published v2.8.3 build and is not evidence for post-release main behavior
derived:
  - remove the non-blocking Codecov upload rather than retain a false-green external signal
  - prioritize measured polling/startup optimization over broad speculative refactoring
unknown:
  - post-hardening behavior on a physical AirPack during reconnect and 24-72 hour soak
  - whether removing redundant sensor translation loading alone removes the live >10 second sensor-platform setup warning
conflicts: []
first_failure:
  marker: external Codecov repository availability
  evidence: PR #1765 Tests job 93786147158 obtains OIDC token then receives 'Repository not found'
rejected_hypotheses:
  - an unfinished implementation branch existed before this audit
  - an open PR or issue was waiting to be completed before this audit
  - GitHub OIDC token issuance was the remaining Codecov blocker
changed_paths:
  - .github/workflows/ci.yaml
  - docs/audits/deep_audit_2026-08-11.md
  - docs/quality/STATUS.md
  - docs/release_readiness.md
  - docs/ha_quality_scale_audit.md
  - docs/agents/tasks/TASK-20260811-deep-audit-cleanup.md
validation:
  - command: baseline main GitHub Actions inspection
    result: PASS_WITH_NONBLOCKING_CODECOV_FAILURE
    evidence: main@62e3cb1, Tests job 93778480635
  - command: PR #1765 first Tests job inspection
    result: PASS_WITH_EXTERNAL_CODECOV_REPOSITORY_NOT_FOUND
    evidence: Tests job 93786147158
blockers: []
next_action: verify the latest PR #1765 head with the full GitHub Actions matrix after removal of the Codecov upload, then mark this checkpoint done
```
