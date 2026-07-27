---
name: mocking-and-fallback-policy-update
description: Workflow command scaffold for mocking-and-fallback-policy-update in agent_part.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /mocking-and-fallback-policy-update

Use this workflow when working on **mocking-and-fallback-policy-update** in `agent_part`.

## Goal

Refactor or update fallback logic for provider failures, including mock asset handling, configuration switches, and error handling in agents.

## Common Files

- `src/agents/*_generator.py`
- `src/agents/quality_reviewer.py`
- `src/agents/rag_quality_reviewer.py`
- `src/config/settings.py`
- `src/tools/__init__.py`
- `tests/test_agents/test_mock_providers.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Update agent(s) to change fallback or error handling logic
- Add or update configuration switches in src/config/settings.py
- Update or remove mock tool implementations
- Update tests to cover new fallback/mocking/error scenarios
- Clean up unused code and parameters in agents

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.