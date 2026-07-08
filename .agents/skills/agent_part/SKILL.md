```markdown
# agent_part Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill teaches you the core development patterns, coding conventions, and workflows used in the `agent_part` Python codebase. The repository is organized for backend development without a specific framework, focusing on modularity, clarity, and robust testing. You'll learn how to add or update database models, API endpoints, agents/clients, and cross-cutting features, as well as how to maintain and improve existing code—all following the repository's established conventions.

---

## Coding Conventions

### File Naming

- Use **snake_case** for all Python files.
  - Example: `asset_repository.py`, `listing_models.py`

### Import Style

- Use **alias imports** for clarity and brevity.
  ```python
  import numpy as np
  import pandas as pd
  ```

### Export Style

- Use **named exports**; explicitly define what is exported from a module.
  ```python
  # models.py
  class ProductModel:
      ...

  __all__ = ["ProductModel"]
  ```

### Commit Messages

- Follow **Conventional Commits** with these prefixes: `feat`, `fix`, `chore`, `docs`, `test`
- Average commit message length: ~48 characters
  - Example: `feat(api): add product listing endpoint`

---

## Workflows

### Add or Update Backend Models and Tests

**Trigger:** When introducing or modifying a backend data model  
**Command:** `/new-db-model`

1. Edit or create model files in `src/db/` (e.g., `models.py`, `listing_models.py`, `asset_repository.py`)
2. Optionally, add or update migration scripts in `scripts/migrations/`
3. Create or update repository or related logic files in `src/db/`
4. Write or update tests in `tests/test_db/`

**Example:**
```python
# src/db/models.py
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
```

---

### Add or Update API Endpoint with Tests

**Trigger:** When adding or modifying an API endpoint  
**Command:** `/new-api-endpoint`

1. Edit or create router files in `src/api/router/` (e.g., `products.py`, `dashboard.py`)
2. Edit or create schema files in `src/api/schema/` if needed
3. Update or create service files in `src/api/service/` if needed
4. Write or update tests in `tests/test_api/`

**Example:**
```python
# src/api/router/products.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/products")
def list_products():
    return [{"id": 1, "name": "Widget"}]
```

---

### Add or Update Agent or Client with Tests

**Trigger:** When adding or updating an agent/client (e.g., for image/video generation)  
**Command:** `/new-agent-client`

1. Edit or create agent files in `src/agents/` or client files in `src/clients/`
2. Update related logic in `src/agents/adapter_config.py` or similar
3. Write or update tests in `tests/test_agents/`

**Example:**
```python
# src/agents/image_generator.py
class ImageGenerator:
    def generate(self, prompt: str) -> bytes:
        ...
```

---

### Implement Feature with Tests and Config

**Trigger:** When adding a new cross-cutting feature (e.g., auth, tenant context, storage backend)  
**Command:** `/new-feature`

1. Edit or create core feature files in `src/` (e.g., `src/auth/`, `src/storage/`, `src/config/`)
2. Update or add configuration in `src/config/settings.py` or similar
3. Write or update tests in the relevant `tests/` directory

**Example:**
```python
# src/config/settings.py
STORAGE_BACKEND = "s3"
```

---

### Fix or Improve Existing Feature with Tests

**Trigger:** When fixing a bug or refining an existing feature  
**Command:** `/fix-feature`

1. Edit relevant implementation files (e.g., `src/agents/`, `src/api/`, `src/rag/`, `src/db/`)
2. Update or add tests in the corresponding `tests/` directory

**Example:**
```python
# src/agents/adapter_config.py
def update_adapter_config(new_config):
    # bugfix: ensure config is validated
    ...
```

---

## Testing Patterns

- **Test files** are Python scripts located in `tests/` directories, named according to the module they test (e.g., `test_db/`, `test_api/`, `test_agents/`).
- **Test framework** is not explicitly defined, but standard Python testing conventions apply.
- Each workflow requires tests to be created or updated alongside code changes.

**Example:**
```python
# tests/test_db/test_models.py
def test_user_creation():
    user = User(name="Alice")
    assert user.name == "Alice"
```

---

## Commands

| Command           | Purpose                                                        |
|-------------------|----------------------------------------------------------------|
| /new-db-model     | Add or update a backend database model with corresponding tests |
| /new-api-endpoint | Add or update an API endpoint with corresponding tests          |
| /new-agent-client | Add or update an agent or client with corresponding tests       |
| /new-feature      | Implement a new feature with config and tests                  |
| /fix-feature      | Fix or improve an existing feature with tests                  |
```
