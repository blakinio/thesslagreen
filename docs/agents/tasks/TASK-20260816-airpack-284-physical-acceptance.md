---
task_id: TASK-20260816-airpack-284-physical-acceptance
status: investigating
branch: test/airpack-284-acceptance-20260816
base_branch: main
created: 2026-08-16
updated: 2026-08-16
related_pr: ""
owned_paths:
  - .github/workflows/airpack-284-ha-mcp-probe.yml
  - docs/agents/tasks/TASK-20260816-airpack-284-physical-acceptance.md
  - docs/agents/tasks/TASK-20260812-quality-scale-closeout.md
  - docs/agents/tasks/TASK-20260810-ha-integration-10of10-followup.md
  - docs/real_device_validation.md
  - docs/audits/deep_audit_2026-08-11.md
required_reads:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/real_device_validation.md
search_first: []
optional_reads: []
---

# AirPack 2.8.4 physical acceptance

## Context checkpoint

```yaml
checkpoint_version: 1
updated_at: 2026-08-16T06:50:00Z
head: b198c626d20797978bb78dbbab1fe2934fc1dc32
branch: test/airpack-284-acceptance-20260816
pr: none
status: investigating
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/real_device_validation.md
owned_paths:
  - .github/workflows/airpack-284-ha-mcp-probe.yml
  - docs/agents/tasks/TASK-20260816-airpack-284-physical-acceptance.md
  - docs/agents/tasks/TASK-20260812-quality-scale-closeout.md
  - docs/agents/tasks/TASK-20260810-ha-integration-10of10-followup.md
  - docs/real_device_validation.md
  - docs/audits/deep_audit_2026-08-11.md
proven:
  - main b198c626d20797978bb78dbbab1fe2934fc1dc32 contains the version bump to integration 2.8.4 and is the v2.8.4 release target.
  - Push CI 31688676604 completed successfully on main@b198c626d20797978bb78dbbab1fe2934fc1dc32.
  - Release workflow 31688676652 completed successfully for the same exact main SHA and published v2.8.4.
  - Repository quality-scale closeout is merged: total coverage 98.21 percent, every integration Python module above 95 percent, config_flow.py plus _config_flow at 100 percent, and the threshold is enforced in CI.
  - The current ChatGPT session does not expose the previously configured HA-MCP connector as an invokable connector namespace.
  - The local execution container cannot resolve homeassistant.molehill.cloud, so it cannot directly invoke the authenticated HA-MCP endpoint.
derived:
  - Physical acceptance must use a network-capable already-authorized execution path and must not copy an owner credential into repository content or workflow inputs.
  - A temporary branch-only GitHub Actions probe can safely test whether repository-managed HA credentials/URL already exist without printing their values.
unknown:
  - Whether this repository already has a usable HA-MCP token/URL secret under a conventional secret name.
  - Exact HA Core/OS identity and installed 2.8.4 runtime identity visible from the live Home Assistant instance.
  - Fresh setup, scan, polling, reconnect/restart, firmware major.minor, safe write/read-back and soak results on the physical AirPack with 2.8.4.
conflicts: []
first_failure:
  marker: interactive-ha-mcp-unavailable
  evidence: api_tool exposes only GitHub/Gmail/Calendar/Contacts/Plugin Management; list_resources for HA-MCP returns no tool namespace, and direct local curl cannot resolve the HA endpoint.
rejected_hypotheses:
  - repository CI is sufficient evidence for physical AirPack acceptance.
  - an owner token may be copied into a public workflow, repository file or workflow_dispatch input to bypass connector availability.
changed_paths:
  - docs/agents/tasks/TASK-20260816-airpack-284-physical-acceptance.md
validation:
  - command: inspect main/release/CI state
    result: PASS
    evidence: main@b198c626d20797978bb78dbbab1fe2934fc1dc32, CI 31688676604 success, Release 31688676652 success, v2.8.4 published.
  - command: interactive HA-MCP connector discovery and direct endpoint probe
    result: BLOCKED
    evidence: no invokable HA-MCP connector namespace in this session; local runtime DNS cannot resolve homeassistant.molehill.cloud.
blockers: []
next_action: Run a branch-only secret-safe GitHub Actions HA-MCP probe to discover whether an already-configured repository credential can reach the live Home Assistant endpoint without exposing credential values.
```
