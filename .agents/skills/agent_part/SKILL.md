```markdown
# agent_part Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches you how to contribute to the `agent_part` Python codebase, which focuses on agent-based integration with external provider APIs (e.g., for image or video generation). You'll learn the project's coding conventions, how to add or update provider clients, and how to update fallback/mocking logic for robust agent behavior. The repository uses conventional commits, clear file organization, and a modular, test-driven approach.

## Coding Conventions

- **File Naming:**  
  Use `snake_case` for all Python files.  
  _Example:_  
  ```
  provider_result.py
  quality_reviewer.py
  ```

- **Import Style:**  
  Prefer **relative imports** within the package.  
  _Example:_  
  ```python
  from .provider_result import ProviderResult
  from ..config import settings
  ```

- **Export Style:**  
  Use **named exports**; define what is exported in `__init__.py` files.  
  _Example (`src/clients/__init__.py`):_  
  ```python
  from .provider_result import ProviderResult
  from .my_provider_client import MyProviderClient

  __all__ = ["ProviderResult", "MyProviderClient"]
  ```

- **Commit Messages:**  
  Use [Conventional Commits](https://www.conventionalcommits.org/):  
  - Prefixes: `feat`, `fix`
  - Example:  
    ```
    feat: add support for NewImageProvider client
    fix: handle provider timeout in agent fallback logic
    ```

## Workflows

### Add or Update Provider Client
**Trigger:** When you want to support a new provider API or update an existing provider integration for asset generation.  
**Command:** `/add-provider-client`

1. **Create or update client implementation**  
   - Add a new client in `src/clients/` (e.g., `new_provider_client.py`).
   - Example:
     ```python
     class NewProviderClient:
         def generate(self, params):
             # API call logic here
             pass
     ```
2. **Update agent(s) to use the new/updated client**  
   - Edit relevant agent(s) in `src/agents/` (e.g., `image_generator.py`) to use your client.
   - Example:
     ```python
     from ..clients.new_provider_client import NewProviderClient
     ```
3. **Update provider result handling**  
   - Modify or extend `src/clients/provider_result.py` to support new result types or structures.
4. **Expand or add tests**  
   - Add/modify tests in `tests/test_agents/` (e.g., `test_clients.py`, `test_mock_providers.py`) to cover:
     - Real provider scenarios
     - Mocked responses
     - Failure/error cases
5. **Update documentation**  
   - Edit or add to:
     - `docs/system_design.md`
     - `docs/class-diagram.mermaid`
     - `docs/sequence-diagram.mermaid`
6. **Update dependencies**  
   - If your client needs new packages, update `pyproject.toml`.
7. **Update `__init__.py` files**  
   - Ensure your client is imported/exported as needed.

---

### Mocking and Fallback Policy Update
**Trigger:** When you want to change how the system handles provider unavailability, mock assets, or error/fail-closed policies.  
**Command:** `/update-fallback-policy`

1. **Update agent fallback/error handling logic**  
   - Refactor logic in `src/agents/*_generator.py`, `quality_reviewer.py`, or `rag_quality_reviewer.py`.
   - Example:
     ```python
     try:
         result = provider_client.generate(params)
     except ProviderError:
         if settings.USE_MOCK:
             result = get_mock_asset()
         else:
             raise
     ```
2. **Add or update configuration switches**  
   - Modify `src/config/settings.py` to add toggles for fallback/mocking.
   - Example:
     ```python
     USE_MOCK = True
     ```
3. **Update or remove mock tool implementations**  
   - Edit or clean up `src/tools/__init__.py` as needed.
4. **Update tests**  
   - Add/modify tests in `tests/test_agents/test_mock_providers.py` to cover new scenarios.
5. **Clean up unused code/parameters**  
   - Remove obsolete logic or parameters from agents.

---

## Testing Patterns

- **Test File Naming:**  
  Test files follow the `*.test.*` pattern (e.g., `test_clients.py`, `test_mock_providers.py`).
- **Framework:**  
  The specific test framework is not detected, but standard Python test conventions apply (likely `pytest` or `unittest`).
- **Coverage:**  
  Tests cover real provider integrations, mocks, and failure scenarios.

_Example test:_
```python
def test_new_provider_success():
    client = NewProviderClient()
    result = client.generate({"prompt": "cat"})
    assert result.success
```

## Commands

| Command                | Purpose                                                     |
|------------------------|-------------------------------------------------------------|
| /add-provider-client   | Add or update an external provider client and related logic  |
| /update-fallback-policy| Refactor fallback/mocking/error handling in agents           |
```
