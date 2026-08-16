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
updated_at: 2026-08-16T09:44:00+02:00
head: 61278d4627656cf5a8d83beb9d0edf664f19bd81
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
  - Secret-safe branch-only probe run 31934287819 / job 95133716323 found no repository-managed HA URL/token secret and the temporary probe workflow was removed afterwards.
  - After the owner explicitly selected @Home assistant, the Home_assistant tool namespace became visible in this conversation.
  - Three direct Home_assistant calls were attempted: ha_get_skill_guide twice and ha_get_overview once; every call failed before reaching Home Assistant with the identical platform error FORBIDDEN: This conversation does not support developer MCPs.
  - Because the Home Assistant server instructions require ha_get_skill_guide before matching actions, no live HA read/write acceptance action was performed after that platform-level denial.
derived:
  - The current blocker is no longer connector discovery or HA authentication; it is the ChatGPT conversation capability gate for developer MCP execution.
  - Physical acceptance can resume immediately in a conversation/workspace surface that supports the already-selected Home Assistant developer MCP app.
unknown:
  - Exact HA Core/OS identity and installed 2.8.4 runtime identity visible from the live Home Assistant instance.
  - Fresh setup, polling, service registration, firmware identity, safe writes/read-back, validation scan, reconnect, diagnostics, stability and soak results on the physical AirPack with 2.8.4.
conflicts: []
first_failure:
  marker: developer-mcp-conversation-forbidden
  evidence: @Home assistant surfaced the namespace, but ha_get_skill_guide and ha_get_overview each returned FORBIDDEN: This conversation does not support developer MCPs before any HA call executed.
rejected_hypotheses:
  - repository CI is sufficient evidence for physical AirPack acceptance.
  - selecting @Home assistant alone guarantees that this conversation supports developer MCP execution.
  - an owner token should be copied into repository content or workflow inputs to bypass the conversation capability gate.
changed_paths:
  - docs/agents/tasks/TASK-20260816-airpack-284-physical-acceptance.md
validation:
  - command: main/release/CI identity inspection
    result: PASS
    evidence: v2.8.4 is main@b198c626d20797978bb78dbbab1fe2934fc1dc32; CI 31688676604 and Release 31688676652 succeeded.
  - command: branch-only secret-safe HA-MCP access probe 31934287819 / job 95133716323
    result: BLOCKED
    evidence: HA_MCP_PROBE=BLOCKED_NO_CONFIGURED_SECRET; no repository-managed HA URL/token secret was present.
  - command: direct @Home assistant tool invocation in current conversation
    result: BLOCKED
    evidence: ha_get_skill_guide x2 and ha_get_overview x1 all returned FORBIDDEN: This conversation does not support developer MCPs.
blockers:
  - Owner must continue this task in a ChatGPT conversation/workspace surface where developer MCP apps are supported and select @Home assistant there; current conversation rejects the tool before Home Assistant is contacted.
next_action: In a developer-MCP-capable conversation with @Home assistant selected, read the HA skill guide first, then run the complete docs/real_device_validation.md matrix on installed v2.8.4 and close PR #1772 only after exact hardware evidence is recorded.
```
