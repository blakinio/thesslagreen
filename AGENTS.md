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

## Durable continuation

- For substantial work, use the checkpoint contract in `docs/agents/CONTEXT_HANDOFF.md`.
- Validate the active task checkpoint with `python tools/agents/checkpoint.py <task-path> --require-checkpoint`.
- Generate a compact next-agent prompt with `python tools/agents/resume.py --task <task-path>`.
- A continuation agent must resume from Git, the task checkpoint and live PR/CI state, not from the previous chat transcript.

## Scope and precedence

- Repository-local and nearest nested `AGENTS.md` instructions remain authoritative for repository-specific safety, branching, ownership, validation, deployment, and merge rules.
- When instructions overlap, follow the more restrictive safety rule.
- Never infer permission to write to a repository, deploy, merge, publish, or perform destructive actions from this baseline alone.

## GitHub connector routing — mandatory

- For GitHub repository, pull request, issue, review, and remote-file tasks, inspect and use the connected GitHub plugin or connector before falling back to local `git` or `gh`.
- Treat an explicit `@GitHub` selection as a request to use the connected GitHub plugin.
- Local `git` may be used for checkout, worktree, diff, branch, and commit operations. Use `gh` only for operations the connector does not support or when repository policy explicitly requires it.
- A missing local checkout, missing `gh` binary, or unauthenticated local `gh` session is not evidence that the GitHub connector is unavailable.

Before claiming that GitHub access is unavailable:

1. Inspect the available GitHub connector tools.
2. Call `github_get_user_login` or the equivalent authenticated-identity operation.
3. Call `github_get_repo` or `github_list_repositories` for the requested repository scope.
4. Attempt the required read operation through the connector when it is safe to do so.

Report a GitHub access blocker only after an actual connector call returns an authentication or permission error. Include the exact failed operation and error.
