---
task_id: TASK-20260811-deep-audit-cleanup
status: ready
branch: main
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
updated_at: 2026-08-11T13:25:10Z
head: 025a36f78b3629e47421afe1d06b372c1df3aafb
branch: main
pr: 1765
status: ready
context_routes:
  - GitHub connector
  - Home Assistant connector read-only audit
  - docs/audits/deep_audit_2026-08-11.md
  - docs/quality/STATUS.md
owned_paths:
  - .github/workflows/ci.yaml
  - docs/audits/deep_audit_2026-08-11.md
  - docs/quality/STATUS.md
  - docs/release_readiness.md
  - docs/ha_quality_scale_audit.md
  - docs/agents/tasks/TASK-20260811-deep-audit-cleanup.md
proven:
  - PR #1765 was merged to main as 025a36f78b3629e47421afe1d06b372c1df3aafb.
  - No unfinished implementation branch, open pull request, or open issue existed at the start of the audit.
  - Baseline main Tests job 93778480635 kept a non-blocking failed Codecov upload green.
  - PR #1765 Tests job 93786147158 obtained a GitHub OIDC token and Codecov returned Repository not found.
  - The non-functional Codecov upload was removed while the blocking local pytest coverage gate was retained.
  - PR #1765 pre-merge Actions run 31494460377 passed the complete repository matrix after Codecov removal.
  - Final main Actions run 31496065204 passed and the Python 3.13 suite reported 1402 tests passing.
  - Current main and package metadata require pymodbus>=3.6.1,<4.0 while published v2.8.3 requires >=3.6.0,<4.0.
  - Physical AirPack post-hardening validation remains an external acceptance gate.
derived:
  - Removing the non-blocking Codecov step eliminates a false-green external signal without weakening the local coverage gate.
  - Hardware-sensitive polling and startup restructuring should remain measurement-driven and separately gated.
unknown:
  - Post-hardening behavior on a physical AirPack during reconnect and a 24-72 hour soak.
  - Whether removing redundant sensor translation loading eliminates the historical sensor-platform setup warning.
conflicts: []
first_failure:
  marker: none-after-final-validation
  evidence: PR #1765 is merged and final main Actions run 31496065204 completed successfully.
rejected_hypotheses:
  - An unfinished implementation branch existed before this audit.
  - An open pull request or issue was waiting to be completed before this audit.
  - GitHub OIDC token issuance was the remaining Codecov blocker.
changed_paths:
  - .github/workflows/ci.yaml
  - docs/audits/deep_audit_2026-08-11.md
  - docs/quality/STATUS.md
  - docs/release_readiness.md
  - docs/ha_quality_scale_audit.md
  - docs/agents/tasks/TASK-20260811-deep-audit-cleanup.md
validation:
  - command: inspect baseline main Tests job 93778480635
    result: PASS
    evidence: Inspection confirmed the Codecov upload failed non-blockingly while the Tests job remained green.
  - command: inspect PR #1765 Tests job 93786147158
    result: PASS
    evidence: Inspection confirmed successful OIDC token issuance followed by Codecov Repository not found.
  - command: inspect PR #1765 Actions run 31494460377 after Codecov removal
    result: PASS
    evidence: Complete pre-merge repository matrix passed on the audited cleanup head.
  - command: inspect final main Actions run 31496065204
    result: PASS
    evidence: Complete main matrix passed and the Python 3.13 suite reported 1402 passing tests.
blockers: []
next_action: Complete the repository-local A3 and checkpoint-governance follow-ups tracked in TASK-20260811-post-audit-closure.md, then use physical AirPack reconnect and soak evidence for the remaining hardware gate.
```
