---
task_id: TASK-20260816-airpack-284-physical-acceptance
status: blocked
branch: test/airpack-284-acceptance-20260816
base_branch: main
created: 2026-08-16
updated: 2026-08-16
related_pr: "1772"
owned_paths:
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
updated_at: 2026-08-16T07:40:00Z
head: 7ba27a311a0428b2a0425e719b4b3198bf82d4cc
branch: test/airpack-284-acceptance-20260816
pr: 1772
status: blocked
context_routes:
  - AGENTS.md
  - docs/agents/CONTEXT_HANDOFF.md
  - docs/agents/GOVERNANCE_CONTRACT.json
  - docs/real_device_validation.md
owned_paths:
  - docs/agents/tasks/TASK-20260816-airpack-284-physical-acceptance.md
  - docs/agents/tasks/TASK-20260812-quality-scale-closeout.md
  - docs/agents/tasks/TASK-20260810-ha-integration-10of10-followup.md
  - docs/real_device_validation.md
  - docs/audits/deep_audit_2026-08-11.md
proven:
  - main b198c626d20797978bb78dbbab1fe2934fc1dc32 is the v2.8.4 release target; push CI 31688676604 and Release 31688676652 succeeded on that exact SHA.
  - Repository quality-scale closeout is merged and enforced: total coverage 98.21 percent, every integration Python module above 95 percent, and config_flow.py plus _config_flow at 100 percent.
  - The current ChatGPT session does not expose the previously configured HA-MCP connector as an invokable connector namespace.
  - The local execution container cannot resolve homeassistant.molehill.cloud and therefore cannot directly invoke the authenticated HA-MCP endpoint.
  - Secret-safe branch-only probe run 31934287819 / job 95133716323 executed successfully enough to inspect repository-provided inputs and failed with marker HA_MCP_PROBE=BLOCKED_NO_CONFIGURED_SECRET.
  - Probe evidence shows HA_MCP_URL, HOME_ASSISTANT_MCP_URL and all six supported HA token secret candidates were empty; no repository-managed HA credential is currently available to GitHub Actions.
  - The temporary probe workflow was removed after evidence capture; PR #1772 effective diff contains only this durable task record.
derived:
  - No currently available execution surface can authenticate to the live Home Assistant instance without transferring an owner credential into an unsafe or unsupported channel.
  - Physical acceptance can resume immediately when the existing HA-MCP connector is re-exposed to this ChatGPT session or an encrypted repository Actions secret is configured outside repository content.
unknown:
  - Exact HA Core/OS identity and installed 2.8.4 runtime identity visible from the live Home Assistant instance.
  - Fresh setup, polling, service registration, firmware identity, safe writes/read-back, validation scan, reconnect, diagnostics, stability and soak results on the physical AirPack with 2.8.4.
conflicts: []
first_failure:
  marker: no-safe-authenticated-ha-execution-surface
  evidence: interactive HA-MCP namespace absent; local DNS unavailable; GitHub Actions probe 31934287819/95133716323 found no configured HA credential.
rejected_hypotheses:
  - repository CI is sufficient evidence for physical AirPack acceptance.
  - the thesslagreen repository already contains a usable encrypted HA token under conventional secret names.
  - an owner token may be committed, printed, or passed through an unprotected workflow input to bypass connector availability.
changed_paths:
  - docs/agents/tasks/TASK-20260816-airpack-284-physical-acceptance.md
validation:
  - command: main/release/CI identity inspection
    result: PASS
    evidence: v2.8.4 is main@b198c626d20797978bb78dbbab1fe2934fc1dc32; CI 31688676604 and Release 31688676652 succeeded.
  - command: interactive HA-MCP connector discovery and local endpoint reachability
    result: BLOCKED
    evidence: no invokable HA-MCP connector namespace; local execution DNS cannot resolve the endpoint.
  - command: branch-only secret-safe HA-MCP access probe 31934287819 / job 95133716323
    result: BLOCKED
    evidence: HA_MCP_PROBE=BLOCKED_NO_CONFIGURED_SECRET; no repository-managed HA URL/token secret was present.
blockers:
  - Owner action is required to re-expose the previously configured HA-MCP connector to this ChatGPT session or securely configure an encrypted HA credential outside repository content; current tools cannot create repository Actions secrets.
next_action: Once a safe authenticated HA execution surface is available, run the complete docs/real_device_validation.md matrix on installed v2.8.4, record exact evidence, update stale closeout checkpoints, and close the final hardware acceptance gate.
```
