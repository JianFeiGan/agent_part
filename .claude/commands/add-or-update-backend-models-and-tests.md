---
name: add-or-update-backend-models-and-tests
description: Workflow command scaffold for add-or-update-backend-models-and-tests in agent_part.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /add-or-update-backend-models-and-tests

Use this workflow when working on **add-or-update-backend-models-and-tests** in `agent_part`.

## Goal

Adds or updates backend database models and ensures corresponding tests are created or updated.

## Common Files

- `src/db/models.py`
- `src/db/listing_models.py`
- `src/db/asset_repository.py`
- `scripts/migrations/*.sql`
- `tests/test_db/*.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit or create model files in src/db/ (e.g., models.py, listing_models.py, asset_repository.py)
- Optionally add or update migration scripts in scripts/migrations/
- Create or update repository or related logic files in src/db/
- Write or update tests in tests/test_db/

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.