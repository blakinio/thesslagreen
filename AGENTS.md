# Global Codex Agent Baseline

## Context efficiency

- Work autonomously until the bounded task is complete or a real blocker or required decision is reached.
- Do not narrate routine file reads, searches, tool calls, commands, or unchanged checks.
- Send user-facing progress only for a material milestone, blocker, required decision, or material scope or risk change; keep each update to at most three short sentences.
- Run the full repository or task preflight once per bounded task or continuation session. Afterwards verify only state that may have changed and can invalidate the next action.
- Repeat the full preflight only after a material external repository-state change, a long interruption or session replacement, or evidence that durable task state conflicts with live state.
- Search before reading large indexes or documents in full and load only task-relevant documentation and source evidence.
- Do not paste full logs, diffs, artifacts, or whole source files when exact identifiers and focused excerpts are sufficient.
- Treat chat history as disposable. Keep durable task or handoff state compact and leave exactly one concrete next action when handing work off.
- When the next action is safe and autonomous, continue without waiting for acknowledgement.

## Scope and precedence

- Repository-local and nearest nested `AGENTS.md` instructions remain authoritative for repository-specific safety, branching, ownership, validation, deployment, and merge rules.
- When instructions overlap, follow the more restrictive safety rule.
- Never infer permission to write to a repository, deploy, merge, publish, or perform destructive actions from this baseline alone.
