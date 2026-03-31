# V2 Subsystem Refactor — Market + Society Architecture Reorganization

## TL;DR

> **Quick Summary**: Reorganize the BizSim codebase from flat module layout into the 5-subsystem architecture defined in `docs/design/vision.v2.md`. Move product/catalog code into `bizsim/markets/`, rename `community/` to `society/`, create facade modules (`market.py`, `social.py`), split the monolithic `ProductCatalog` into B2C/B2B interfaces, and rewire all imports across the codebase.
> 
> **Deliverables**:
> - `bizsim/markets/` directory with `consumer_market.py`, `industrial_market.py`, `schema.py`
> - `bizsim/market.py` facade with `MarketFactory` + `ConsumerMarket`/`IndustrialMarket` Protocols
> - `bizsim/society/` directory (renamed from `community/`) with `community.py`, `media.py`
> - `bizsim/social.py` facade
> - All imports rewired across agents, engine, and tests
> - Old files deleted (`product_catalog.py`, `product_system.py`, `community/`)
> - All 57 existing tests passing
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: YES — 3 waves
> **Critical Path**: Task 1 (schema) → Task 2 (market facade) → Task 5 (import rewiring) → Task 8 (delete old files) → Task 9 (final verification)

---

## Context

### Original Request
Refactor the BizSim codebase into the 5-subsystem architecture per `docs/design/vision.v2.md`. This is a pure code reorganization — no new business logic, no behavior changes. "Just make the breaking change, and make the naming meaningful."

### Interview Summary
**Key Discussions**:
- Markets are passive state containers (observable state), not matching engines
- `bizsim/markets/` holds implementation, `bizsim/market.py` is the facade with `MarketFactory` + Protocol interfaces
- `bizsim/society/` holds implementation, `bizsim/social.py` is the facade
- The monolithic `ProductCatalog` Protocol splits into `ConsumerMarket` (B2C) and `IndustrialMarket` (B2B)
- The monolithic `SqliteProductCatalog` implementation stays as one class internally but exposes two protocol-conforming views through `MarketFactory`
- Media is a V2 placeholder — empty `society/media.py` with stub class
- Government updates market state (feedback loop) — conceptual, no code change needed now
- Breaking changes are OK — make naming meaningful

**Research Findings**:
- Complete import dependency map traced across 15 files (see detailed references in tasks)
- Current `ProductCatalog` Protocol has 7 methods mixing B2C and B2B concerns
- `SqliteProductCatalog` implements all 7 in one class — needs to back both Protocol views
- `product_system.py` has 3 distinct concerns: DDL (schema), seeding, and lookups
- `community/subsystem.py` imports only from `bizsim.domain` — clean dependency
- `bizsim/__init__.py` does NOT export any product/community types — minimal change needed

### Metis Review
**Self-Identified Gaps** (addressed in plan):
- **SqliteProductCatalog split strategy**: The single impl class must satisfy both `ConsumerMarket` and `IndustrialMarket` Protocols. Resolution: Keep one implementation class internally, have `MarketFactory` return it cast to each Protocol type. The class already has all methods.
- **`product_system.py` lookup functions**: `lookup_sku()`, `lookup_bom()`, `lookup_sku_supplier_mapping()` are standalone utility functions not part of any Protocol. Resolution: Move to `markets/schema.py` alongside DDL since they're low-level DB utilities.
- **`seed_catalog()` placement**: Used by tests and integration. Resolution: Move to `markets/schema.py` with DDL — it's schema-level infrastructure.
- **Test file renaming**: Tests like `test_product_catalog.py` and `test_product_system.py` test the market subsystem. Resolution: Rename to `test_consumer_market.py` and `test_market_schema.py` to match new module names.
- **CI guardrails in `.github/workflows/arch-guard.yml`**: May reference old paths. Resolution: Include in import update task.
- **`README.md` and `AGENTS.md`**: Reference old file paths. Resolution: Include documentation update task.

---

## Work Objectives

### Core Objective
Reorganize the BizSim Python package from a flat layout with `product_catalog.py`, `product_system.py`, and `community/` into the subsystem architecture: `markets/` + `market.py` facade, `society/` + `social.py` facade — matching `docs/design/vision.v2.md` §2.

### Concrete Deliverables
- `bizsim/markets/__init__.py` — barrel exports
- `bizsim/markets/consumer_market.py` — `SqliteConsumerMarket` (B2C impl, moved from `product_catalog.py`)
- `bizsim/markets/industrial_market.py` — `SqliteIndustrialMarket` (B2B impl, extracted from `product_catalog.py`)
- `bizsim/markets/schema.py` — DDL (`create_tables`), seeding (`seed_catalog`), lookups (`lookup_sku`, etc.) — moved from `product_system.py`
- `bizsim/market.py` — Facade: `ConsumerMarket` Protocol, `IndustrialMarket` Protocol, `MarketFactory`
- `bizsim/society/__init__.py` — barrel exports
- `bizsim/society/community.py` — moved from `community/subsystem.py`
- `bizsim/society/media.py` — V2 placeholder stub
- `bizsim/social.py` — Facade: re-exports `CommunitySubsystem`, `CommunityConfig`, `SharePurchaseData`; placeholder `MediaSubsystem`
- All imports in `engine.py`, `agents/base.py`, `agents/consumer.py`, `agents/seller.py`, `agents/supplier.py` updated
- All test imports updated (8 test files)
- Old files `product_catalog.py`, `product_system.py`, `community/` deleted
- `README.md`, `AGENTS.md` updated for new paths

### Definition of Done
- [ ] `pytest tests/` — all tests pass (57 tests, 0 failures)
- [ ] `mypy --strict bizsim/` — no new type errors
- [ ] `ruff check bizsim/ tests/` — no lint errors
- [ ] No imports of `bizsim.product_catalog` or `bizsim.product_system` or `bizsim.community` anywhere in codebase
- [ ] `bizsim/product_catalog.py` and `bizsim/product_system.py` do not exist
- [ ] `bizsim/community/` directory does not exist
- [ ] `bizsim/markets/` directory exists with 4 files
- [ ] `bizsim/society/` directory exists with 3 files
- [ ] `bizsim/market.py` and `bizsim/social.py` exist

### Must Have
- All existing test behavior preserved — zero test logic changes, only import path changes
- `ConsumerMarket` and `IndustrialMarket` as separate Protocol interfaces in `market.py`
- `MarketFactory` class that creates both market views from shared SQLite connection
- `markets/schema.py` containing all DDL, seeding, and low-level lookup utilities
- `society/media.py` as explicit V2 placeholder (not just empty file — should have docstring + stub class)

### Must NOT Have (Guardrails)
- **No new business logic** — this is a pure refactoring. No behavioral changes to any agent, market, or community code
- **No test logic changes** — only import paths change in test files. No assertion modifications, no fixture restructuring
- **No premature abstraction** — don't add abstract base classes, factory patterns beyond MarketFactory, or dependency injection frameworks
- **No over-documentation** — don't add JSDoc/docstrings everywhere. Keep existing docstrings, add minimal ones only for new facade modules
- **No scope creep into Go translator** — the translator subsystem is untouched
- **No changes to `bizsim/domain.py`, `bizsim/events.py`, `bizsim/channels.py`** — framework layer stays frozen
- **No new dependencies** — no pip packages added

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest)
- **Automated tests**: Tests-after (verify existing tests pass after each wave)
- **Framework**: pytest
- **No new tests needed** — this is a pure refactoring with full test preservation

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Python modules**: Use Bash (`python -c "from bizsim.market import ..."`) — verify imports resolve
- **Test suite**: Use Bash (`pytest tests/ -v`) — verify all tests pass
- **File structure**: Use Bash (`ls`, `find`) — verify directory structure matches spec
- **Import cleanliness**: Use Bash (`grep -r "product_catalog\|product_system\|bizsim.community" bizsim/ tests/`) — verify zero old imports

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — create new modules, no old files touched yet):
├── Task 1: Create bizsim/markets/ directory + schema.py [quick]
├── Task 2: Create bizsim/market.py facade + markets/consumer_market.py + markets/industrial_market.py [unspecified-high]
├── Task 3: Create bizsim/society/ directory + community.py + media.py [quick]
├── Task 4: Create bizsim/social.py facade [quick]

Wave 2 (After Wave 1 — rewire all imports to new modules):
├── Task 5: Update all bizsim/ source imports (engine.py, agents/*.py) [unspecified-high]
├── Task 6: Update all test file imports + rename test files [unspecified-high]

Wave 3 (After Wave 2 — cleanup + verification):
├── Task 7: Update bizsim/__init__.py if needed [quick]
├── Task 8: Delete old files (product_catalog.py, product_system.py, community/) [quick]
├── Task 9: Update documentation (README.md, AGENTS.md) [quick]

Wave FINAL (After ALL tasks — independent review):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Full test suite QA (unspecified-high)
├── Task F4: Scope fidelity check (deep)

Critical Path: Task 1 → Task 2 → Task 5 → Task 8 → F1-F4
Parallel Speedup: ~50% faster than sequential
Max Concurrent: 4 (Wave 1)
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|-----------|--------|
| 1 | — | 2 |
| 2 | 1 | 5, 6 |
| 3 | — | 4, 6 |
| 4 | 3 | 6 |
| 5 | 2, 4 | 7, 8 |
| 6 | 2, 4 | 8 |
| 7 | 5 | 8 |
| 8 | 5, 6, 7 | 9 |
| 9 | 8 | F1-F4 |

### Agent Dispatch Summary

- **Wave 1**: **4 tasks** — T1 → `quick`, T2 → `unspecified-high`, T3 → `quick`, T4 → `quick`
- **Wave 2**: **2 tasks** — T5 → `unspecified-high`, T6 → `unspecified-high`
- **Wave 3**: **3 tasks** — T7 → `quick`, T8 → `quick`, T9 → `quick`
- **FINAL**: **4 tasks** — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

> Implementation + Verification = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.

 - [x] 1. Create `bizsim/markets/` directory + `schema.py`

  **What to do**:
  - Create directory `bizsim/markets/`
  - Create `bizsim/markets/__init__.py` (empty or minimal barrel exports — just a docstring for now, exports will be finalized after all market modules exist)
  - Create `bizsim/markets/schema.py` by moving ALL content from `bizsim/product_system.py`:
    - `create_tables(conn)` — DDL for all 5 tables + indexes (unchanged)
    - `seed_catalog(conn, tenant_id, skus, ...)` — seeding function (unchanged)
    - `lookup_sku(conn, tenant_id, sku_id)` — standalone lookup (unchanged)
    - `lookup_bom(conn, tenant_id, sku_id)` — standalone lookup (unchanged)
    - `lookup_sku_supplier_mapping(conn, tenant_id, sku_id)` — standalone lookup (unchanged)
  - The content is a direct copy from `product_system.py` — no logic changes, no renaming of functions
  - The empty `ProductSystem(Protocol)` class in `product_system.py` should NOT be copied (it's an unused stub)

  **Must NOT do**:
  - Do NOT delete `product_system.py` yet (that happens in Task 8)
  - Do NOT modify any function signatures or SQL queries
  - Do NOT add new abstractions or wrapper classes

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple file creation with copy-paste content, no complex logic
  - **Skills**: []
    - No special skills needed for file copying

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Task 2
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `bizsim/product_system.py` (entire file, 211 lines) — The COMPLETE source to copy into `markets/schema.py`. Copy everything EXCEPT the empty `ProductSystem(Protocol)` class (lines 5-6). Keep all imports (`sqlite3`, `typing.Any`, `typing.Protocol` can be removed since Protocol class is dropped).

  **WHY Each Reference Matters**:
  - `product_system.py` is the single source file. The executor copies its content verbatim (minus the unused Protocol stub) into the new location. No interpretation needed.

  **Acceptance Criteria**:

  - [ ] File `bizsim/markets/__init__.py` exists
  - [ ] File `bizsim/markets/schema.py` exists
  - [ ] `python -c "from bizsim.markets.schema import create_tables, seed_catalog, lookup_sku, lookup_bom, lookup_sku_supplier_mapping; print('OK')"` → prints "OK"
  - [ ] `bizsim/markets/schema.py` does NOT contain a `ProductSystem` class

  **QA Scenarios**:

  ```
  Scenario: Schema module imports resolve correctly
    Tool: Bash
    Preconditions: bizsim/markets/ directory and schema.py created
    Steps:
      1. Run: python -c "from bizsim.markets.schema import create_tables, seed_catalog, lookup_sku, lookup_bom, lookup_sku_supplier_mapping; print('ALL_IMPORTS_OK')"
      2. Assert stdout contains "ALL_IMPORTS_OK"
    Expected Result: Exit code 0, output "ALL_IMPORTS_OK"
    Failure Indicators: ImportError, ModuleNotFoundError, or non-zero exit code
    Evidence: .sisyphus/evidence/task-1-schema-imports.txt

  Scenario: Schema module creates tables in SQLite
    Tool: Bash
    Preconditions: schema.py created with create_tables function
    Steps:
      1. Run: python -c "
         import sqlite3
         from bizsim.markets.schema import create_tables
         conn = sqlite3.connect(':memory:')
         create_tables(conn)
         cursor = conn.cursor()
         cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
         tables = sorted([r[0] for r in cursor.fetchall()])
         print(tables)
         assert 'sku_catalog' in tables
         assert 'parts' in tables
         assert 'bill_of_materials' in tables
         assert 'sku_seller_mapping' in tables
         assert 'sku_supplier_mapping' in tables
         print('TABLES_OK')
         "
      2. Assert stdout contains "TABLES_OK"
    Expected Result: 5 tables created, exit code 0
    Failure Indicators: Missing tables, SQL errors
    Evidence: .sisyphus/evidence/task-1-schema-tables.txt
  ```

  **Commit**: YES (groups with Wave 1: Tasks 1-4)
  - Message: `refactor(markets,society): scaffold new subsystem directories and facade modules`
  - Files: `bizsim/markets/__init__.py`, `bizsim/markets/schema.py`

- [ ] 2. Create `bizsim/market.py` facade + `markets/consumer_market.py` + `markets/industrial_market.py`

  **What to do**:
  
  **Step A — Create `bizsim/market.py` (facade)**:
  - Define `ConsumerMarket(Protocol)` with B2C methods:
    - `browse_skus(category: str | None = None, limit: int = 100) -> list[dict[str, Any]]`
    - `get_sku(sku_id: int) -> dict[str, Any] | None`
    - `get_sellers_for_sku(sku_id: int) -> list[dict[str, Any]]`
    - `get_skus_for_seller(seller_id: int) -> list[dict[str, Any]]`
  - Define `IndustrialMarket(Protocol)` with B2B methods:
    - `get_suppliers_for_sku(sku_id: int) -> list[dict[str, Any]]`
    - `get_bom(sku_id: int) -> list[dict[str, Any]]`
    - `get_parts_for_supplier(supplier_id: int) -> list[dict[str, Any]]`
  - Define `MarketFactory` class:
    - `__init__(self, conn: sqlite3.Connection, tenant_id: int) -> None`
    - `consumer_market(self) -> ConsumerMarket` — returns `SqliteConsumerMarket(self.conn, self.tenant_id)`
    - `industrial_market(self) -> IndustrialMarket` — returns `SqliteIndustrialMarket(self.conn, self.tenant_id)`
  - Import `SqliteConsumerMarket` and `SqliteIndustrialMarket` inside the factory methods (lazy import to avoid circular deps) or at module level from `bizsim.markets.consumer_market` and `bizsim.markets.industrial_market`

  **Step B — Create `bizsim/markets/consumer_market.py`**:
  - Define `SqliteConsumerMarket` class with ONLY the B2C methods from `SqliteProductCatalog`:
    - `__init__(self, conn, tenant_id)` — same as SqliteProductCatalog
    - `_execute_query(self, query, params)` — same helper
    - `browse_skus(self, category, limit)` — copy from SqliteProductCatalog
    - `get_sku(self, sku_id)` — copy from SqliteProductCatalog
    - `get_sellers_for_sku(self, sku_id)` — copy from SqliteProductCatalog
    - `get_skus_for_seller(self, seller_id)` — copy from SqliteProductCatalog

  **Step C — Create `bizsim/markets/industrial_market.py`**:
  - Define `SqliteIndustrialMarket` class with ONLY the B2B methods from `SqliteProductCatalog`:
    - `__init__(self, conn, tenant_id)` — same as SqliteProductCatalog
    - `_execute_query(self, query, params)` — same helper (duplicated — acceptable for clean separation)
    - `get_suppliers_for_sku(self, sku_id)` — copy from SqliteProductCatalog
    - `get_bom(self, sku_id)` — copy from SqliteProductCatalog
    - `get_parts_for_supplier(self, supplier_id)` — copy from SqliteProductCatalog

  **Step D — Update `bizsim/markets/__init__.py`**:
  - Re-export key types: `SqliteConsumerMarket`, `SqliteIndustrialMarket`

  **CRITICAL DESIGN DECISION**: The current `SqliteProductCatalog` has 7 methods. These are split into two classes (4 B2C + 3 B2B). The `_execute_query` helper is duplicated in both — this is intentional to keep the classes independent. An alternative is a shared base class, but that adds unnecessary abstraction for this refactoring.

  **Must NOT do**:
  - Do NOT delete `product_catalog.py` yet (Task 8)
  - Do NOT change any SQL queries or method signatures
  - Do NOT add complex inheritance hierarchies — keep it simple
  - Do NOT add `ProductCatalog` as a compatibility alias — breaking changes are OK per user decision

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Requires careful splitting of one class into two + creating a facade with factory pattern. Needs precision with Protocol definitions matching exact method signatures.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 3, 4 but after Task 1)
  - **Parallel Group**: Wave 1 (starts after Task 1 provides `markets/` directory)
  - **Blocks**: Tasks 5, 6
  - **Blocked By**: Task 1

  **References**:

  **Pattern References**:
  - `bizsim/product_catalog.py:5-21` — The existing `ProductCatalog(Protocol)` with all 7 methods. Split these into `ConsumerMarket` (lines 6-10, 18: `browse_skus`, `get_sku`, `get_sellers_for_sku`, `get_skus_for_seller`) and `IndustrialMarket` (lines 14, 16, 20: `get_suppliers_for_sku`, `get_bom`, `get_parts_for_supplier`).
  - `bizsim/product_catalog.py:23-89` — The `SqliteProductCatalog` implementation. Split into `SqliteConsumerMarket` (lines 23-34 init+helper, 35-61 B2C methods, 75-82 get_skus_for_seller) and `SqliteIndustrialMarket` (lines 23-34 init+helper, 62-89 B2B methods).

  **API/Type References**:
  - `docs/design/vision.v2.md:404-423` — The target `ConsumerMarket`, `IndustrialMarket` Protocol definitions and `MarketFactory` class. These are the EXACT signatures to implement.

  **WHY Each Reference Matters**:
  - `product_catalog.py` is the source being split — executor needs to read it to copy methods correctly
  - `vision.v2.md` defines the target API — executor must match these Protocol signatures exactly

  **Acceptance Criteria**:

  - [ ] `bizsim/market.py` exists with `ConsumerMarket`, `IndustrialMarket`, `MarketFactory` classes
  - [ ] `bizsim/markets/consumer_market.py` exists with `SqliteConsumerMarket` class
  - [ ] `bizsim/markets/industrial_market.py` exists with `SqliteIndustrialMarket` class
  - [ ] `python -c "from bizsim.market import ConsumerMarket, IndustrialMarket, MarketFactory; print('OK')"` → "OK"
  - [ ] `python -c "from bizsim.markets.consumer_market import SqliteConsumerMarket; print('OK')"` → "OK"
  - [ ] `python -c "from bizsim.markets.industrial_market import SqliteIndustrialMarket; print('OK')"` → "OK"

  **QA Scenarios**:

  ```
  Scenario: MarketFactory creates both market types from shared connection
    Tool: Bash
    Preconditions: All market modules created, schema.py exists from Task 1
    Steps:
      1. Run: python -c "
         import sqlite3
         from bizsim.markets.schema import create_tables, seed_catalog
         from bizsim.market import MarketFactory
         conn = sqlite3.connect(':memory:')
         create_tables(conn)
         seed_catalog(conn, 1, [{'sku_id': 1, 'name': 'Test', 'category': 'C', 'base_price': 10, 'price_floor': 5, 'price_ceiling': 15}],
           seller_mappings=[{'sku_id': 1, 'seller_id': 100, 'is_primary': True}],
           supplier_mappings=[{'sku_id': 1, 'supplier_id': 200}])
         factory = MarketFactory(conn, 1)
         cm = factory.consumer_market()
         im = factory.industrial_market()
         skus = cm.browse_skus()
         assert len(skus) == 1, f'Expected 1 SKU, got {len(skus)}'
         sellers = cm.get_sellers_for_sku(1)
         assert len(sellers) == 1
         suppliers = im.get_suppliers_for_sku(1)
         assert len(suppliers) == 1
         print('FACTORY_OK')
         "
      2. Assert stdout contains "FACTORY_OK"
    Expected Result: Exit code 0, both market views work from same connection
    Failure Indicators: ImportError, AttributeError, assertion failure
    Evidence: .sisyphus/evidence/task-2-market-factory.txt

  Scenario: ConsumerMarket Protocol has exactly 4 methods
    Tool: Bash
    Preconditions: market.py facade created
    Steps:
      1. Run: python -c "
         import inspect
         from bizsim.market import ConsumerMarket
         methods = [m for m in dir(ConsumerMarket) if not m.startswith('_')]
         expected = ['browse_skus', 'get_sellers_for_sku', 'get_sku', 'get_skus_for_seller']
         assert sorted(methods) == sorted(expected), f'Methods mismatch: {methods} != {expected}'
         print('CONSUMER_PROTOCOL_OK')
         "
      2. Assert stdout contains "CONSUMER_PROTOCOL_OK"
    Expected Result: Exactly 4 B2C methods on ConsumerMarket Protocol
    Failure Indicators: Extra or missing methods
    Evidence: .sisyphus/evidence/task-2-consumer-protocol.txt

  Scenario: IndustrialMarket Protocol has exactly 3 methods
    Tool: Bash
    Preconditions: market.py facade created
    Steps:
      1. Run: python -c "
         import inspect
         from bizsim.market import IndustrialMarket
         methods = [m for m in dir(IndustrialMarket) if not m.startswith('_')]
         expected = ['get_bom', 'get_parts_for_supplier', 'get_suppliers_for_sku']
         assert sorted(methods) == sorted(expected), f'Methods mismatch: {methods} != {expected}'
         print('INDUSTRIAL_PROTOCOL_OK')
         "
      2. Assert stdout contains "INDUSTRIAL_PROTOCOL_OK"
    Expected Result: Exactly 3 B2B methods on IndustrialMarket Protocol
    Failure Indicators: Extra or missing methods
    Evidence: .sisyphus/evidence/task-2-industrial-protocol.txt
  ```

  **Commit**: YES (groups with Wave 1: Tasks 1-4)
  - Message: `refactor(markets,society): scaffold new subsystem directories and facade modules`
  - Files: `bizsim/market.py`, `bizsim/markets/consumer_market.py`, `bizsim/markets/industrial_market.py`, `bizsim/markets/__init__.py`

- [ ] 3. Create `bizsim/society/` directory + `community.py` + `media.py`

  **What to do**:
  - Create directory `bizsim/society/`
  - Create `bizsim/society/__init__.py` with barrel exports: `CommunitySubsystem`, `CommunityConfig`, `SharePurchaseData`, `ConsumerProtocol`
  - Create `bizsim/society/community.py` by copying the ENTIRE content of `bizsim/community/subsystem.py` — no changes to any logic, imports, or class/function signatures. The file content is identical.
  - Create `bizsim/society/media.py` as a V2 placeholder:
    ```python
    """Media subsystem — V2 placeholder.

    The media subsystem will provide public broadcast channels (advertising, news,
    aggregated reviews) for one-to-many agent influence, distinct from community's
    peer-to-peer propagation. See docs/design/vision.v2.md §6.
    """


    class MediaSubsystem:
        """V2 placeholder — not implemented."""
        pass
    ```

  **Must NOT do**:
  - Do NOT delete `bizsim/community/` yet (Task 8)
  - Do NOT modify any logic in `community/subsystem.py` — pure copy
  - Do NOT implement any real media functionality — placeholder only

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: File copy + simple placeholder creation, no complex logic
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Task 4, Task 6
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `bizsim/community/subsystem.py` (entire file, 159 lines) — Copy verbatim to `society/community.py`. The file imports `ActionEvent` and `WritePattern` from `bizsim.domain` — these imports remain unchanged since `bizsim.domain` doesn't move.
  
  **API/Type References**:
  - `docs/design/vision.v2.md:440-491` — Target architecture for society subsystem, describing community.py and media.py roles.

  **WHY Each Reference Matters**:
  - `community/subsystem.py` is the exact source to copy — no interpretation needed
  - `vision.v2.md` explains the media placeholder purpose for the docstring

  **Acceptance Criteria**:

  - [ ] `bizsim/society/__init__.py` exists with barrel exports
  - [ ] `bizsim/society/community.py` exists with identical content to `community/subsystem.py`
  - [ ] `bizsim/society/media.py` exists with `MediaSubsystem` placeholder class
  - [ ] `python -c "from bizsim.society.community import CommunitySubsystem, CommunityConfig, SharePurchaseData; print('OK')"` → "OK"
  - [ ] `python -c "from bizsim.society.media import MediaSubsystem; print('OK')"` → "OK"

  **QA Scenarios**:

  ```
  Scenario: Society community module imports resolve correctly
    Tool: Bash
    Preconditions: society/community.py created
    Steps:
      1. Run: python -c "from bizsim.society.community import CommunitySubsystem, CommunityConfig, SharePurchaseData, ConsumerProtocol; print('SOCIETY_IMPORTS_OK')"
      2. Assert stdout contains "SOCIETY_IMPORTS_OK"
    Expected Result: Exit code 0, all 4 types importable
    Failure Indicators: ImportError
    Evidence: .sisyphus/evidence/task-3-society-imports.txt

  Scenario: Media placeholder is importable and minimal
    Tool: Bash
    Preconditions: society/media.py created
    Steps:
      1. Run: python -c "
         from bizsim.society.media import MediaSubsystem
         m = MediaSubsystem()
         assert m is not None
         print('MEDIA_PLACEHOLDER_OK')
         "
      2. Assert stdout contains "MEDIA_PLACEHOLDER_OK"
    Expected Result: MediaSubsystem instantiable (trivially)
    Failure Indicators: ImportError, instantiation error
    Evidence: .sisyphus/evidence/task-3-media-placeholder.txt

  Scenario: Community subsystem logic works from new location
    Tool: Bash
    Preconditions: society/community.py copied from community/subsystem.py
    Steps:
      1. Run: python -c "
         from bizsim.society.community import CommunitySubsystem, CommunityConfig, SharePurchaseData
         config = CommunityConfig(avg_degree=2)
         sub = CommunitySubsystem([1, 2, 3], config)
         sub.enqueue_activation(SharePurchaseData(1, 'test', 1.0))
         assert len(sub._activation_queue) == 1
         print('COMMUNITY_LOGIC_OK')
         "
      2. Assert stdout contains "COMMUNITY_LOGIC_OK"
    Expected Result: Community subsystem works identically from new path
    Failure Indicators: Logic errors, missing imports
    Evidence: .sisyphus/evidence/task-3-community-logic.txt
  ```

  **Commit**: YES (groups with Wave 1: Tasks 1-4)
  - Message: `refactor(markets,society): scaffold new subsystem directories and facade modules`
  - Files: `bizsim/society/__init__.py`, `bizsim/society/community.py`, `bizsim/society/media.py`

- [ ] 4. Create `bizsim/social.py` facade

  **What to do**:
  - Create `bizsim/social.py` as the society subsystem facade:
    - Re-export from `bizsim.society.community`: `CommunitySubsystem`, `CommunityConfig`, `SharePurchaseData`, `ConsumerProtocol`
    - Re-export from `bizsim.society.media`: `MediaSubsystem`
    - Add a module docstring explaining this is the public API for the society subsystem
    - Include `__all__` listing all exported names
  - This is a thin re-export layer — no new logic

  **Must NOT do**:
  - Do NOT add wrapper functions or additional abstraction
  - Do NOT create a factory class (unlike market.py — society doesn't need one)
  - Do NOT add any behavior beyond re-exports

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Trivial re-export module, ~15 lines
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (needs Task 3 first)
  - **Parallel Group**: Wave 1 (starts after Task 3)
  - **Blocks**: Task 6
  - **Blocked By**: Task 3

  **References**:

  **Pattern References**:
  - `bizsim/__init__.py` (17 lines) — Pattern for how BizSim does barrel re-exports with `__all__`. Follow this same style for `social.py`.
  - `bizsim/society/community.py` — Source of types to re-export: `CommunitySubsystem`, `CommunityConfig`, `SharePurchaseData`, `ConsumerProtocol`
  - `bizsim/society/media.py` — Source of `MediaSubsystem` to re-export

  **API/Type References**:
  - `docs/design/vision.v2.md:440-451` — Describes `social.py` facade role: "access to community and media"

  **WHY Each Reference Matters**:
  - `__init__.py` shows the project's re-export convention to follow
  - Community and media modules define what to re-export
  - vision.v2.md is the architectural spec

  **Acceptance Criteria**:

  - [ ] `bizsim/social.py` exists
  - [ ] `python -c "from bizsim.social import CommunitySubsystem, CommunityConfig, SharePurchaseData, ConsumerProtocol, MediaSubsystem; print('OK')"` → "OK"
  - [ ] `bizsim/social.py` has `__all__` defined

  **QA Scenarios**:

  ```
  Scenario: Social facade re-exports all society types
    Tool: Bash
    Preconditions: social.py and society/ modules exist
    Steps:
      1. Run: python -c "
         from bizsim.social import CommunitySubsystem, CommunityConfig, SharePurchaseData, ConsumerProtocol, MediaSubsystem
         assert CommunitySubsystem is not None
         assert MediaSubsystem is not None
         print('SOCIAL_FACADE_OK')
         "
      2. Assert stdout contains "SOCIAL_FACADE_OK"
    Expected Result: All 5 types importable from bizsim.social
    Failure Indicators: ImportError, missing re-exports
    Evidence: .sisyphus/evidence/task-4-social-facade.txt

  Scenario: Social facade has __all__ with correct entries
    Tool: Bash
    Preconditions: social.py created
    Steps:
      1. Run: python -c "
         import bizsim.social as s
         assert hasattr(s, '__all__'), 'Missing __all__'
         expected = {'CommunitySubsystem', 'CommunityConfig', 'SharePurchaseData', 'ConsumerProtocol', 'MediaSubsystem'}
         assert set(s.__all__) == expected, f'__all__ mismatch: {s.__all__}'
         print('ALL_EXPORTS_OK')
         "
      2. Assert stdout contains "ALL_EXPORTS_OK"
    Expected Result: __all__ contains exactly 5 entries
    Failure Indicators: Missing __all__ or wrong entries
    Evidence: .sisyphus/evidence/task-4-social-all.txt
  ```

  **Commit**: YES (groups with Wave 1: Tasks 1-4)
  - Message: `refactor(markets,society): scaffold new subsystem directories and facade modules`
  - Files: `bizsim/social.py`

- [ ] 5. Update all `bizsim/` source imports (engine.py, agents/*.py)

  **What to do**:

  **IMPORTANT CONTEXT**: The old `ProductCatalog` Protocol combined B2C and B2B methods. Agents used it as a single type. In the new design, agents that need BOTH B2C and B2B access should reference `MarketFactory` (which provides both views). Agents that only need B2C should reference `ConsumerMarket`. Agents that only need B2B should reference `IndustrialMarket`.

  However, for this refactoring, agents currently receive a single `catalog` attribute. The simplest approach: agents continue receiving a single object that satisfies both protocols. Since `SqliteConsumerMarket` only has B2C methods and `SqliteIndustrialMarket` only has B2B methods, agents that call mixed methods need the `MarketFactory`. 

  **PRACTICAL APPROACH**: Replace `ProductCatalog` TYPE_CHECKING imports with `MarketFactory` from `bizsim.market`. Agents receive a `MarketFactory` and call `self.catalog.consumer_market().browse_skus()` or `self.catalog.industrial_market().get_bom()`. This is a breaking API change but aligns with vision.v2.md §8 and user said "just make the breaking change."

  **ALTERNATIVE (simpler, less refactoring)**: Keep agents receiving a single concrete object and use Union type or Protocol that combines both. But this defeats the purpose of the split.

  **DECISION**: Use `MarketFactory`. Update agent code to call through the factory. This means:
  - `self.catalog.browse_skus()` → `self.catalog.consumer_market().browse_skus()`
  - `self.catalog.get_bom()` → `self.catalog.industrial_market().get_bom()`
  - etc.

  **File-by-file changes**:

  **A. `bizsim/engine.py`** (line 8):
  - Change: `from bizsim.product_catalog import ProductCatalog` → `from bizsim.market import MarketFactory`
  - Change type annotation: `catalog: "ProductCatalog | None" = None` → `catalog: "MarketFactory | None" = None`
  - No changes to `community_hook` parameter — it's already `Any` typed

  **B. `bizsim/agents/base.py`** (line 6):
  - Change: `from bizsim.product_catalog import ProductCatalog` → `from bizsim.market import MarketFactory`
  - Change type annotation: `catalog: "ProductCatalog | None" = None` → `catalog: "MarketFactory | None" = None`
  - Change attribute type annotation if present

  **C. `bizsim/agents/consumer.py`** (lines 5-6):
  - Change: `from bizsim.product_catalog import ProductCatalog` → `from bizsim.market import MarketFactory`
  - Update ALL `self.catalog.browse_skus(...)` → `self.catalog.consumer_market().browse_skus(...)`
  - Update ALL `self.catalog.get_sku(...)` → `self.catalog.consumer_market().get_sku(...)`
  - Update ALL `self.catalog.get_sellers_for_sku(...)` → `self.catalog.consumer_market().get_sellers_for_sku(...)`
  - Search the entire file for any other catalog method calls and route through appropriate market

  **D. `bizsim/agents/seller.py`** (lines 8-9):
  - Change: `from bizsim.product_catalog import ProductCatalog` → `from bizsim.market import MarketFactory`
  - Update catalog method calls — seller uses BOTH B2C (pricing) and B2B (supply):
    - B2C calls (e.g., `get_skus_for_seller`, `get_sku`) → `self.catalog.consumer_market().method()`
    - B2B calls (e.g., `get_suppliers_for_sku`) → `self.catalog.industrial_market().method()`
  - Search entire file for ALL `self.catalog.` calls and route each through correct market

  **E. `bizsim/agents/supplier.py`** (lines 8-9):
  - Change: `from bizsim.product_catalog import ProductCatalog` → `from bizsim.market import MarketFactory`
  - Update catalog method calls — supplier uses B2B:
    - `get_bom` → `self.catalog.industrial_market().get_bom()`
    - `get_parts_for_supplier` → `self.catalog.industrial_market().get_parts_for_supplier()`
    - `get_suppliers_for_sku` → `self.catalog.industrial_market().get_suppliers_for_sku()`
  - Search entire file for ALL `self.catalog.` calls

  **Must NOT do**:
  - Do NOT change any business logic — only import paths and catalog accessor patterns
  - Do NOT change method signatures on agents
  - Do NOT modify `domain.py`, `events.py`, or `channels.py`
  - Do NOT rename agent files

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Requires reading through 5 agent files, understanding which catalog methods are B2C vs B2B, and carefully updating each call site. High attention to detail needed.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 6)
  - **Parallel Group**: Wave 2 (with Task 6)
  - **Blocks**: Tasks 7, 8
  - **Blocked By**: Tasks 2, 4

  **References**:

  **Pattern References**:
  - `bizsim/engine.py:7-8` — TYPE_CHECKING import of ProductCatalog that needs updating
  - `bizsim/engine.py:25` — `catalog: "ProductCatalog | None" = None` parameter to change
  - `bizsim/agents/base.py:5-6` — TYPE_CHECKING import of ProductCatalog
  - `bizsim/agents/base.py:40` — `catalog: "ProductCatalog | None" = None` parameter
  - `bizsim/agents/consumer.py:5-6` — TYPE_CHECKING import of ProductCatalog
  - `bizsim/agents/seller.py:8-9` — TYPE_CHECKING import of ProductCatalog
  - `bizsim/agents/supplier.py:8-9` — TYPE_CHECKING import of ProductCatalog

  **API/Type References**:
  - `bizsim/market.py` (created in Task 2) — `MarketFactory`, `ConsumerMarket`, `IndustrialMarket` types
  - `docs/design/vision.v2.md:580-596` — §8 showing how agents use markets through factory: `self.market.consumer_market().browse_skus()`

  **WHY Each Reference Matters**:
  - Each source file needs its import changed — executor must read EVERY line referencing `product_catalog` or `ProductCatalog` or `self.catalog.`
  - vision.v2.md shows the target calling convention
  - `market.py` from Task 2 is the import source

  **Acceptance Criteria**:

  - [ ] Zero occurrences of `product_catalog` in `bizsim/engine.py`
  - [ ] Zero occurrences of `product_catalog` in `bizsim/agents/base.py`
  - [ ] Zero occurrences of `product_catalog` in `bizsim/agents/consumer.py`
  - [ ] Zero occurrences of `product_catalog` in `bizsim/agents/seller.py`
  - [ ] Zero occurrences of `product_catalog` in `bizsim/agents/supplier.py`
  - [ ] All `self.catalog.method()` calls routed through `.consumer_market()` or `.industrial_market()`
  - [ ] `grep -r "product_catalog" bizsim/` returns zero matches (excluding `bizsim/product_catalog.py` itself which still exists)

  **QA Scenarios**:

  ```
  Scenario: No old imports remain in bizsim source (excluding old files)
    Tool: Bash
    Preconditions: All source imports updated
    Steps:
      1. Run: grep -rn "product_catalog" bizsim/engine.py bizsim/agents/ || echo "CLEAN"
      2. Assert output is "CLEAN" (no matches)
    Expected Result: Zero occurrences of product_catalog in engine or agents
    Failure Indicators: Any grep match
    Evidence: .sisyphus/evidence/task-5-no-old-imports.txt

  Scenario: All bizsim source modules import successfully
    Tool: Bash
    Preconditions: Imports rewired
    Steps:
      1. Run: python -c "
         from bizsim.engine import TickEngine
         from bizsim.agents.base import BaseAgent
         from bizsim.agents.consumer import ConsumerAgent
         from bizsim.agents.seller import SellerAgent
         from bizsim.agents.supplier import SupplierAgent
         print('ALL_SOURCE_IMPORTS_OK')
         "
      2. Assert stdout contains "ALL_SOURCE_IMPORTS_OK"
    Expected Result: All modules importable without errors
    Failure Indicators: ImportError from stale references
    Evidence: .sisyphus/evidence/task-5-source-imports.txt
  ```

  **Commit**: YES (groups with Wave 2: Tasks 5-6)
  - Message: `refactor(imports): rewire all imports from product_catalog/product_system/community to markets/society`
  - Files: `bizsim/engine.py`, `bizsim/agents/base.py`, `bizsim/agents/consumer.py`, `bizsim/agents/seller.py`, `bizsim/agents/supplier.py`

- [ ] 6. Update all test file imports + rename test files

  **What to do**:

  Update imports in ALL test files that reference old module paths, and rename test files to match new module names.

  **File-by-file changes**:

  **A. Rename `tests/test_product_catalog.py` → `tests/test_consumer_market.py`**:
  - Change import: `from bizsim.product_system import create_tables, seed_catalog` → `from bizsim.markets.schema import create_tables, seed_catalog`
  - Change import: `from bizsim.product_catalog import SqliteProductCatalog` → `from bizsim.markets.consumer_market import SqliteConsumerMarket`
  - Update all references to `SqliteProductCatalog` → `SqliteConsumerMarket` in the file
  - The tests exercise B2C methods (browse_skus, get_sku, get_sellers_for_sku, get_skus_for_seller) — these are consumer market tests
  - BUT this file ALSO tests B2B methods (get_suppliers_for_sku, get_bom, get_parts_for_supplier). These calls should use `SqliteIndustrialMarket` instead. Update the fixture to create both market types or keep tests using whichever class has the method.
  - **PRACTICAL DECISION**: Since the old tests tested all 7 methods through one object, and now they're split, the simplest approach is: keep all tests in `test_consumer_market.py` for B2C tests, and create/move the B2B tests (test_get_suppliers_for_sku, test_get_bom, test_get_parts_for_supplier) to a new `tests/test_industrial_market.py`. Alternatively, add B2B fixture alongside B2C. **Use your judgment — the goal is all tests pass with correct imports.**

  **B. Rename `tests/test_product_system.py` → `tests/test_market_schema.py`**:
  - Change import: `from bizsim.product_system import (create_tables, seed_catalog, lookup_sku, lookup_bom, lookup_sku_supplier_mapping)` → `from bizsim.markets.schema import (create_tables, seed_catalog, lookup_sku, lookup_bom, lookup_sku_supplier_mapping)`
  - No other changes needed — function names are identical

  **C. `tests/test_community.py` → rename to `tests/test_society_community.py`**:
  - Change import: `from bizsim.community.subsystem import CommunitySubsystem, CommunityConfig, SharePurchaseData` → `from bizsim.society.community import CommunitySubsystem, CommunityConfig, SharePurchaseData`
  - No other changes needed — class/function names identical

  **D. `tests/test_integration.py`**:
  - Change: `from bizsim.product_system import create_tables, seed_catalog` → `from bizsim.markets.schema import create_tables, seed_catalog`
  - Change: `from bizsim.product_catalog import SqliteProductCatalog` → `from bizsim.market import MarketFactory` (or from `bizsim.markets.consumer_market import SqliteConsumerMarket`)
  - Update integration test to create `MarketFactory` instead of `SqliteProductCatalog`
  - Update any `catalog` references to use `MarketFactory` instance
  - **READ THE FULL FILE** before making changes — it's 282 lines and may have complex setup

  **E. `tests/test_supplier_catalog.py`**:
  - Change: `from bizsim.product_catalog import ProductCatalog` → `from bizsim.market import IndustrialMarket` (or keep using a mock that satisfies the Protocol)
  - Update MockCatalog to only include B2B methods if it was testing supplier-catalog interaction
  - **READ THE FULL FILE** to understand the mock structure

  **F. `tests/test_seller_catalog.py`**:
  - Change: `from bizsim.product_catalog import ProductCatalog` → `from bizsim.market import ConsumerMarket, IndustrialMarket` (seller uses both)
  - Update mock catalog references

  **G. `tests/test_engine_injection.py`**:
  - Change: `from bizsim.product_catalog import ProductCatalog` → `from bizsim.market import MarketFactory`
  - Update mock/test to use `MarketFactory` type

  **H. `tests/test_consumer_catalog.py`** (if it has product_catalog imports):
  - Check and update any stale imports — this file currently does NOT import product_catalog (confirmed from grep), so likely no changes needed

  **Must NOT do**:
  - Do NOT change test assertions or test logic — only imports and type references
  - Do NOT delete any test cases
  - Do NOT add new test cases (this is a refactoring)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 8 test files to update, some with complex setup. Requires reading each file fully, understanding what's B2C vs B2B, and routing imports correctly. File renames add complexity.
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 5)
  - **Parallel Group**: Wave 2 (with Task 5)
  - **Blocks**: Task 8
  - **Blocked By**: Tasks 2, 4

  **References**:

  **Pattern References**:
  - `tests/test_product_catalog.py` (161 lines) — Full file needs import update + rename + possible B2B test splitting
  - `tests/test_product_system.py` (130 lines) — Import update + rename
  - `tests/test_community.py` (106 lines) — Import update + rename
  - `tests/test_integration.py:13-14` — Two old imports to update
  - `tests/test_supplier_catalog.py:6` — `ProductCatalog` import to update
  - `tests/test_seller_catalog.py:6` — `ProductCatalog` import to update
  - `tests/test_engine_injection.py:4` — `ProductCatalog` import to update

  **API/Type References**:
  - `bizsim/market.py` (from Task 2) — `MarketFactory`, `ConsumerMarket`, `IndustrialMarket`
  - `bizsim/markets/schema.py` (from Task 1) — `create_tables`, `seed_catalog`, `lookup_*`
  - `bizsim/society/community.py` (from Task 3) — `CommunitySubsystem`, `CommunityConfig`, `SharePurchaseData`

  **WHY Each Reference Matters**:
  - Each test file must be read fully to understand which methods it calls and route imports correctly
  - The new module APIs define where each import comes from

  **Acceptance Criteria**:

  - [ ] `tests/test_product_catalog.py` no longer exists (renamed)
  - [ ] `tests/test_product_system.py` no longer exists (renamed)
  - [ ] `tests/test_community.py` no longer exists (renamed)
  - [ ] `tests/test_consumer_market.py` exists (renamed from test_product_catalog.py)
  - [ ] `tests/test_market_schema.py` exists (renamed from test_product_system.py)
  - [ ] `tests/test_society_community.py` exists (renamed from test_community.py)
  - [ ] Zero occurrences of `bizsim.product_catalog` or `bizsim.product_system` or `bizsim.community.subsystem` in any test file
  - [ ] `pytest tests/ -v` — all 57 tests pass

  **QA Scenarios**:

  ```
  Scenario: All tests pass after import rewiring
    Tool: Bash
    Preconditions: All test imports updated, all new modules exist
    Steps:
      1. Run: pytest tests/ -v --tb=short 2>&1 | tail -20
      2. Assert output contains "passed" and does not contain "FAILED" or "ERROR"
      3. Assert test count is >= 57
    Expected Result: 57 passed, 0 failed, 0 errors
    Failure Indicators: Any FAILED or ERROR lines, test count < 57
    Evidence: .sisyphus/evidence/task-6-all-tests.txt

  Scenario: No old import paths remain in test files
    Tool: Bash
    Preconditions: All test imports updated
    Steps:
      1. Run: grep -rn "bizsim.product_catalog\|bizsim.product_system\|bizsim.community" tests/ || echo "TESTS_CLEAN"
      2. Assert output is "TESTS_CLEAN"
    Expected Result: Zero old import paths in tests/
    Failure Indicators: Any grep match
    Evidence: .sisyphus/evidence/task-6-clean-test-imports.txt

  Scenario: Renamed test files exist and old names are gone
    Tool: Bash
    Preconditions: Test files renamed
    Steps:
      1. Run: ls tests/test_consumer_market.py tests/test_market_schema.py tests/test_society_community.py 2>&1 && echo "NEW_FILES_OK"
      2. Run: ls tests/test_product_catalog.py tests/test_product_system.py tests/test_community.py 2>&1 || echo "OLD_FILES_GONE"
      3. Assert "NEW_FILES_OK" and "OLD_FILES_GONE" both appear
    Expected Result: New files exist, old files don't
    Failure Indicators: Missing new files or lingering old files
    Evidence: .sisyphus/evidence/task-6-file-renames.txt
  ```

  **Commit**: YES (groups with Wave 2: Tasks 5-6)
  - Message: `refactor(imports): rewire all imports from product_catalog/product_system/community to markets/society`
  - Files: All renamed/updated test files

- [ ] 7. Update `bizsim/__init__.py` if needed

  **What to do**:
  - Read `bizsim/__init__.py` and check if it needs updates for the new module structure
  - Currently it exports: `TenantContext`, `ActionEvent`, `ReadPattern`, `WritePattern`, `EventEmitter`, `QueryRequest`, `QueryResult`, `InterAgentMessage`, `InboxItem`
  - These are ALL framework-layer types from `domain.py`, `events.py`, `channels.py` — none of them are being moved
  - **Likely no changes needed** — but verify. If any import path references old modules, fix them.
  - Optionally: add convenience re-exports for the new facades (`MarketFactory`, `CommunitySubsystem`) — but this is optional and should be skipped to keep the init clean. Users import from `bizsim.market` and `bizsim.social` directly.

  **Must NOT do**:
  - Do NOT add re-exports of market/society types to `__init__.py` unless there's a clear need
  - Do NOT modify any existing exports

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Likely zero changes needed — just verify and confirm
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 8, 9 — but logically after Task 5)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 8
  - **Blocked By**: Task 5

  **References**:

  **Pattern References**:
  - `bizsim/__init__.py` (17 lines) — Current re-exports. All from framework modules (domain, events, channels). Should need zero changes.

  **Acceptance Criteria**:

  - [ ] `bizsim/__init__.py` imports resolve correctly
  - [ ] `python -c "from bizsim import TenantContext, ActionEvent, EventEmitter; print('OK')"` → "OK"

  **QA Scenarios**:

  ```
  Scenario: Package init imports still work
    Tool: Bash
    Preconditions: __init__.py reviewed/updated
    Steps:
      1. Run: python -c "from bizsim import TenantContext, ActionEvent, ReadPattern, WritePattern, EventEmitter, QueryRequest, QueryResult, InterAgentMessage, InboxItem; print('INIT_OK')"
      2. Assert stdout contains "INIT_OK"
    Expected Result: All existing exports still work
    Failure Indicators: ImportError
    Evidence: .sisyphus/evidence/task-7-init-imports.txt
  ```

  **Commit**: YES (groups with Wave 3: Tasks 7-9)
  - Message: `refactor(cleanup): delete old modules, update __init__.py and documentation`
  - Files: `bizsim/__init__.py` (if changed)

- [ ] 8. Delete old files (`product_catalog.py`, `product_system.py`, `community/`)

  **What to do**:
  - Delete `bizsim/product_catalog.py`
  - Delete `bizsim/product_system.py`
  - Delete `bizsim/community/` directory (contains `__init__.py` and `subsystem.py`)
  - After deletion, run `pytest tests/ -v` to confirm nothing broke
  - Run `grep -r "product_catalog\|product_system\|bizsim\.community" bizsim/ tests/` to confirm zero stale references

  **CRITICAL**: This task MUST run AFTER Tasks 5 and 6 have rewired all imports. If any import still references the old modules, tests will fail.

  **Must NOT do**:
  - Do NOT delete any other files
  - Do NOT delete `bizsim/community/` if any import still references it (verify first)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple file deletion + verification
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (must verify all imports rewired first)
  - **Parallel Group**: Wave 3 (after Tasks 5, 6, 7)
  - **Blocks**: Task 9
  - **Blocked By**: Tasks 5, 6, 7

  **References**:

  **Files to delete**:
  - `bizsim/product_catalog.py` (89 lines) — replaced by `bizsim/market.py` + `bizsim/markets/consumer_market.py` + `bizsim/markets/industrial_market.py`
  - `bizsim/product_system.py` (211 lines) — replaced by `bizsim/markets/schema.py`
  - `bizsim/community/__init__.py` (0 lines, empty) — replaced by `bizsim/society/__init__.py`
  - `bizsim/community/subsystem.py` (159 lines) — replaced by `bizsim/society/community.py`

  **Acceptance Criteria**:

  - [ ] `bizsim/product_catalog.py` does not exist
  - [ ] `bizsim/product_system.py` does not exist
  - [ ] `bizsim/community/` directory does not exist
  - [ ] `pytest tests/ -v` — all 57 tests pass
  - [ ] `grep -r "product_catalog\|product_system\|bizsim\.community" bizsim/ tests/` → zero matches

  **QA Scenarios**:

  ```
  Scenario: Old files are deleted
    Tool: Bash
    Preconditions: All imports rewired in Tasks 5-6
    Steps:
      1. Run: ls bizsim/product_catalog.py 2>&1; echo "---"; ls bizsim/product_system.py 2>&1; echo "---"; ls bizsim/community/ 2>&1
      2. Assert all three produce "No such file or directory" errors
    Expected Result: None of the old files/directories exist
    Failure Indicators: Any file still present
    Evidence: .sisyphus/evidence/task-8-old-files-gone.txt

  Scenario: All tests still pass after deletion
    Tool: Bash
    Preconditions: Old files deleted
    Steps:
      1. Run: pytest tests/ -v --tb=short 2>&1 | tail -20
      2. Assert contains "passed" and no "FAILED" or "ERROR"
    Expected Result: 57 passed
    Failure Indicators: ImportError from deleted modules
    Evidence: .sisyphus/evidence/task-8-tests-after-delete.txt

  Scenario: Zero stale references in codebase
    Tool: Bash
    Preconditions: Old files deleted, all imports updated
    Steps:
      1. Run: grep -rn "product_catalog\|product_system\|bizsim\.community" bizsim/ tests/ || echo "ALL_CLEAN"
      2. Assert output is "ALL_CLEAN"
    Expected Result: Zero matches
    Failure Indicators: Any stale reference found
    Evidence: .sisyphus/evidence/task-8-zero-stale-refs.txt
  ```

  **Commit**: YES (groups with Wave 3: Tasks 7-9)
  - Message: `refactor(cleanup): delete old modules, update __init__.py and documentation`
  - Files: deleted `bizsim/product_catalog.py`, `bizsim/product_system.py`, `bizsim/community/`

- [ ] 9. Update documentation (`README.md`, `AGENTS.md`)

  **What to do**:
  - Update `README.md` project structure section to reflect new directory layout:
    - Remove `product_catalog.py` and `product_system.py` entries
    - Remove `community/subsystem.py` entry
    - Add `markets/` directory with `consumer_market.py`, `industrial_market.py`, `schema.py`
    - Add `market.py` facade entry
    - Add `society/` directory with `community.py`, `media.py`
    - Add `social.py` facade entry
  - Update `AGENTS.md` directory structure section similarly
  - Check for any other references to old file paths in both files and update them
  - Do NOT rewrite the entire README — only update the directory tree and any references to moved files

  **Must NOT do**:
  - Do NOT rewrite documentation prose — only update file path references
  - Do NOT add new documentation sections
  - Do NOT update `docs/design/vision.v2.md` — it already describes the target state

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Targeted path updates in 2 markdown files
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 7, 8 if deletion is concurrent)
  - **Parallel Group**: Wave 3
  - **Blocks**: F1-F4
  - **Blocked By**: Task 8

  **References**:

  **Pattern References**:
  - `README.md` — Contains "Project Structure" section with file tree that references old paths
  - `AGENTS.md` — Contains "Directory Structure" section referencing old paths
  - `docs/design/vision.v2.md:112-160` — The target directory structure to match

  **WHY Each Reference Matters**:
  - README and AGENTS.md have outdated file trees after refactoring
  - vision.v2.md has the correct target layout to copy

  **Acceptance Criteria**:

  - [ ] `README.md` project structure matches actual directory layout
  - [ ] `AGENTS.md` directory structure matches actual directory layout
  - [ ] Zero references to `product_catalog.py`, `product_system.py`, or `community/subsystem.py` in README.md or AGENTS.md
  - [ ] `grep -n "product_catalog\|product_system\|community/subsystem" README.md AGENTS.md` → zero matches

  **QA Scenarios**:

  ```
  Scenario: No stale path references in documentation
    Tool: Bash
    Preconditions: Documentation updated
    Steps:
      1. Run: grep -n "product_catalog\|product_system\|community/subsystem" README.md AGENTS.md || echo "DOCS_CLEAN"
      2. Assert output is "DOCS_CLEAN"
    Expected Result: Zero old path references
    Failure Indicators: Any stale references
    Evidence: .sisyphus/evidence/task-9-docs-clean.txt

  Scenario: README mentions new market and society modules
    Tool: Bash
    Preconditions: README updated
    Steps:
      1. Run: grep -c "markets/" README.md && grep -c "society/" README.md && grep -c "market.py" README.md && grep -c "social.py" README.md && echo "DOCS_UPDATED"
      2. Assert "DOCS_UPDATED" appears (all greps find at least 1 match)
    Expected Result: New paths are mentioned in README
    Failure Indicators: Missing references to new modules
    Evidence: .sisyphus/evidence/task-9-docs-new-paths.txt
  ```

  **Commit**: YES (groups with Wave 3: Tasks 7-9)
  - Message: `refactor(cleanup): delete old modules, update __init__.py and documentation`
  - Files: `README.md`, `AGENTS.md`

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, check imports). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in `.sisyphus/evidence/`. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `mypy --strict bizsim/` + `ruff check bizsim/ tests/` + `pytest tests/ -v`. Review all new/changed files for: unused imports, missing type annotations, inconsistent naming. Check no `as any`/`# type: ignore` was added unnecessarily.
  Output: `Mypy [PASS/FAIL] | Ruff [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Full Test Suite QA** — `unspecified-high`
  Run `pytest tests/ -v --tb=long`. Verify exactly 57 tests pass. Check no tests were silently deleted or skipped. Run `grep -r "product_catalog\|product_system\|bizsim\.community" bizsim/ tests/` to confirm zero old import paths remain.
  Output: `Tests [57/57 pass] | Old Imports [0 found] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", verify actual implementation. Check no business logic was added/changed. Verify `domain.py`, `events.py`, `channels.py` are untouched. Check no new pip dependencies. Verify file structure matches `docs/design/vision.v2.md` §2.
  Output: `Tasks [N/N compliant] | Framework Frozen [YES/NO] | Structure Match [YES/NO] | VERDICT`

---

## Commit Strategy

| After Task(s) | Commit Message | Files |
|---------------|---------------|-------|
| 1-4 (Wave 1) | `refactor(markets,society): scaffold new subsystem directories and facade modules` | `bizsim/markets/`, `bizsim/market.py`, `bizsim/society/`, `bizsim/social.py` |
| 5-6 (Wave 2) | `refactor(imports): rewire all imports from product_catalog/product_system/community to markets/society` | `bizsim/engine.py`, `bizsim/agents/*.py`, `tests/*.py` |
| 7-9 (Wave 3) | `refactor(cleanup): delete old modules, update __init__.py and documentation` | deleted files, `bizsim/__init__.py`, `README.md`, `AGENTS.md` |

---

## Success Criteria

### Verification Commands
```bash
pytest tests/ -v                    # Expected: 57 passed, 0 failed
mypy --strict bizsim/               # Expected: Success (no new errors)
ruff check bizsim/ tests/           # Expected: All checks passed
python -c "from bizsim.market import MarketFactory, ConsumerMarket, IndustrialMarket; print('OK')"
python -c "from bizsim.social import CommunitySubsystem, CommunityConfig; print('OK')"
python -c "from bizsim.markets.schema import create_tables, seed_catalog; print('OK')"
python -c "from bizsim.markets.consumer_market import SqliteConsumerMarket; print('OK')"
python -c "from bizsim.society.community import CommunitySubsystem; print('OK')"
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All 57 tests pass
- [ ] Directory structure matches `docs/design/vision.v2.md` §2
- [ ] Zero references to old module paths in codebase
