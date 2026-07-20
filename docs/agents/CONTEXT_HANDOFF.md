# Agent Context Handoff

Chat history is disposable. Git state, the active task checkpoint, the live PR and deterministic validation evidence are durable state.

For every substantial task: keep one compact `## Context checkpoint`, update it after material changes, validate with `python tools/agents/checkpoint.py <task-path> --require-checkpoint`, then generate the next-agent prompt with `python tools/agents/resume.py --task <task-path>`.

The next agent verifies only live state that can invalidate `next_action`, then continues from that action. Never pass the previous chat transcript as the handoff.

Checkpoint v1 carries branch/head/PR/status, `PROVEN`, `DERIVED`, `UNKNOWN`, `CONFLICT`, first failure, changed paths, validation, blockers, and exactly one concrete `next_action`.

Do not repeat a full preflight when checkpoint and live state agree. Do not store full logs, diffs, source files, old chat, repeated CI history or whole-repository inventories. `tools/agents/checkpoint.py` enforces compactness ceilings.
