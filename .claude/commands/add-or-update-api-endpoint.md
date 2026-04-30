---
name: add-or-update-api-endpoint
description: Workflow command scaffold for add-or-update-api-endpoint in agent_part.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /add-or-update-api-endpoint

Use this workflow when working on **add-or-update-api-endpoint** in `agent_part`.

## Goal

Adds or updates API endpoints, schemas, and corresponding tests for listing features.

## Common Files

- `src/api/router/*.py`
- `src/api/schema/*.py`
- `tests/test_api/*.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Create or update API route file in src/api/router/
- Update or add schema in src/api/schema/
- Add or update API test in tests/test_api/

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.