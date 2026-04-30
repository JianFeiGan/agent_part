```markdown
# agent_part Development Patterns

> Auto-generated skill from repository analysis

## Overview

This skill teaches you the core development patterns, coding conventions, and standard workflows for contributing to the `agent_part` Python codebase. The repository focuses on modular agent/service classes, API endpoints, data models, workflow logic, and frontend integration for listing workflows. It emphasizes maintainability, clear structure, and test coverage.

## Coding Conventions

- **File Naming:**  
  Use `snake_case` for all Python files.
  ```
  # Good
  agent_manager.py
  adapter_config.py

  # Bad
  AgentManager.py
  adapterConfig.py
  ```

- **Import Style:**  
  Use aliases for imports where appropriate.
  ```python
  import src.models.listing as listing_model
  from src.api.schema import adapter_config as adapter_schema
  ```

- **Export Style:**  
  Use named exports in `__init__.py` files.
  ```python
  # src/models/__init__.py
  from .listing import ListingModel
  from .user import UserModel

  __all__ = ["ListingModel", "UserModel"]
  ```

- **Commit Messages:**  
  Follow [Conventional Commits](https://www.conventionalcommits.org/) with these prefixes: `feat`, `chore`, `docs`, `fix`, `refactor`.
  ```
  feat(agent): add ShopifyAgent for new platform support
  fix(api): correct listing schema validation
  ```

## Workflows

### Add New Agent or Service Class
**Trigger:** When introducing a new agent/service for a listing workflow step or platform.  
**Command:** `/new-agent`

1. Create a new agent/service class file in `src/agents/`.
2. If needed, add supporting files (e.g., platform specs, rules, config).
3. Add or update a test file in `tests/test_agents/`.
4. Export or register the new agent if required.

**Example:**
```python
# src/agents/shopify_agent.py
class ShopifyAgent:
    def run(self, data):
        # agent logic here
        pass

# tests/test_agents/test_shopify_agent.py
from src.agents.shopify_agent import ShopifyAgent

def test_shopify_agent_runs():
    agent = ShopifyAgent()
    assert agent.run({}) is None
```

---

### Add or Update API Endpoint
**Trigger:** When exposing new functionality or data via the API.  
**Command:** `/new-api-endpoint`

1. Create or update an API route file in `src/api/router/`.
2. Update or add schema in `src/api/schema/`.
3. Add or update API test in `tests/test_api/`.

**Example:**
```python
# src/api/router/listing.py
from src.api.schema.listing import ListingSchema

def create_listing_endpoint():
    # endpoint logic
    pass

# tests/test_api/test_listing.py
def test_create_listing_endpoint():
    # test logic
    pass
```

---

### Add or Update Data Model
**Trigger:** When introducing or modifying data structures for listings, compliance, or config.  
**Command:** `/new-model`

1. Create or update model file in `src/models/` or `src/db/`.
2. Update `__init__.py` to export new models.
3. Add or update model test in `tests/test_models/` or `tests/test_db/`.

**Example:**
```python
# src/models/listing.py
from pydantic import BaseModel

class ListingModel(BaseModel):
    id: int
    name: str

# src/models/__init__.py
from .listing import ListingModel
__all__ = ["ListingModel"]

# tests/test_models/test_listing.py
def test_listing_model():
    model = ListingModel(id=1, name="Test")
    assert model.id == 1
```

---

### Implement or Extend Workflow Logic
**Trigger:** When adding steps, nodes, or logic to the listing workflow engine.  
**Command:** `/new-workflow-node`

1. Create or update workflow/state file in `src/graph/`.
2. Export new workflow/state in `src/graph/__init__.py`.
3. Add or update workflow test in `tests/test_graph/`.

**Example:**
```python
# src/graph/listing_workflow.py
class ListingWorkflow:
    def step(self):
        pass

# src/graph/__init__.py
from .listing_workflow import ListingWorkflow
__all__ = ["ListingWorkflow"]
```

---

### Add or Update Frontend Page or Types
**Trigger:** When exposing new features or data to the frontend UI.  
**Command:** `/new-frontend-page`

1. Create or update Vue component in `frontend/src/views/listing/`.
2. Update TypeScript types in `frontend/src/types/`.
3. Update or add API function in `frontend/src/api/`.
4. Update router or sidebar if needed.

**Example:**
```typescript
// frontend/src/types/listing.ts
export interface Listing {
  id: number;
  name: string;
}
```

---

### Add or Update Adapter Config Manager
**Trigger:** When managing or exposing adapter configuration (credentials, caching, multi-shop).  
**Command:** `/new-adapter-config`

1. Create or update `AdapterConfigManager` in `src/agents/adapter_config.py`.
2. Update or add schema in `src/api/schema/adapter_config.py`.
3. Add or update test in `tests/test_agents/test_adapter_config.py`.

**Example:**
```python
# src/agents/adapter_config.py
class AdapterConfigManager:
    def get_config(self, platform):
        pass
```

## Testing Patterns

- **Test Framework:**  
  The framework is not explicitly specified, but Python test files are located under `tests/` and follow the `test_*.py` naming convention.
- **Test Structure:**  
  Place agent tests in `tests/test_agents/`, API tests in `tests/test_api/`, model tests in `tests/test_models/`, and workflow tests in `tests/test_graph/`.
- **Example:**
  ```python
  # tests/test_models/test_listing.py
  from src.models.listing import ListingModel

  def test_listing_model_fields():
      model = ListingModel(id=1, name="Test")
      assert model.name == "Test"
  ```

## Commands

| Command              | Purpose                                                      |
|----------------------|--------------------------------------------------------------|
| /new-agent           | Scaffold a new agent or service class                        |
| /new-api-endpoint    | Add or update an API endpoint and schema                     |
| /new-model           | Add or update a data model                                   |
| /new-workflow-node   | Implement or extend workflow/state logic                     |
| /new-frontend-page   | Add or update a frontend page, types, or API functions       |
| /new-adapter-config  | Add or update the AdapterConfigManager and related schemas   |
```