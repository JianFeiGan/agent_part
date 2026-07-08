---
name: add-or-update-api-endpoint-with-tests
description: Workflow command scaffold for add-or-update-api-endpoint-with-tests in agent_part.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /add-or-update-api-endpoint-with-tests

Use this workflow when working on **add-or-update-api-endpoint-with-tests** in `agent_part`.

## Goal

Adds or updates an API endpoint and ensures corresponding tests are created or updated.

## Common Files

- `src/api/router/*.py`
- `src/api/schema/*.py`
- `src/api/service/*.py`
- `tests/test_api/*.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit or create router files in src/api/router/ (e.g., products.py, dashboard.py, assets.py)
- Edit or create schema files in src/api/schema/ if needed
- Update or create service files in src/api/service/ if needed
- Write or update tests in tests/test_api/

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.