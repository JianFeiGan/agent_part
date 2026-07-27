---
name: add-or-update-provider-client
description: Workflow command scaffold for add-or-update-provider-client in agent_part.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /add-or-update-provider-client

Use this workflow when working on **add-or-update-provider-client** in `agent_part`.

## Goal

Integrate a new external provider client (e.g., for image/video generation), update agent logic to use the client, and expand tests/documentation accordingly.

## Common Files

- `src/clients/*.py`
- `src/agents/*_generator.py`
- `src/clients/provider_result.py`
- `tests/test_agents/test_clients.py`
- `tests/test_agents/test_mock_providers.py`
- `docs/system_design.md`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Create or update client implementation in src/clients/
- Update agent(s) in src/agents/ to use the new or updated client
- Update or create provider result handling in src/clients/provider_result.py
- Add or update tests in tests/test_agents/ to cover real, mock, and failure scenarios
- Update documentation (system design, diagrams) to reflect new provider/client

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.