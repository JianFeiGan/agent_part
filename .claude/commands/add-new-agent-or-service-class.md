---
name: add-new-agent-or-service-class
description: Workflow command scaffold for add-new-agent-or-service-class in agent_part.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /add-new-agent-or-service-class

Use this workflow when working on **add-new-agent-or-service-class** in `agent_part`.

## Goal

Adds a new Agent or service class (e.g., for a platform or workflow step), usually with corresponding tests.

## Common Files

- `src/agents/*.py`
- `tests/test_agents/*.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Create new agent/service class file in src/agents/
- If needed, add supporting files (e.g., platform specs, rules, config)
- Add or update test file in tests/test_agents/
- Export or register the new agent if required

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.