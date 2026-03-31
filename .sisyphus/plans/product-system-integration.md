# Product System Integration — Wire Real SKU Data Into All Agents

## TL;DR

> **Quick Summary**: Replace all hardcoded/random product data in BizSim agents with real lookups from an in-process SQLite ProductCatalog wrapper. Creates a `ProductCatalog` class (outside `agents/`), injects it into `BaseAgent`, then rewires Consumer, Seller, and Supplier to use real SKU IDs, prices, seller/supplier mappings, and BOM data.
> 
> **Deliverables**:
> - `bizsim/product_catalog.py` — ProductCatalog protocol + SQLite implementation
> - Updated `BaseAgent.__init__` with backward-compatible `catalog` injection
> - Consumer agent using real SKUs, real prices, real seller mappings
> - Seller agent with rule-based pricing (floor/ceiling), real supplier lookups, configurable peer agent IDs
> - Supplier agent with full BOM enrichment and real transport ID lookup
> - TickEngine initializing and injecting ProductCatalog
> - Integration test seeded with real catalog data
> 
> **Estimated Effort**: Medium (7 tasks, ~4-6 hours)
> **Parallel Execution**: YES — 3 waves
> **Critical Path**: Task 1 → Task 2 → Tasks 3/4/5 (parallel) → Task 6 → Task 7

---

## Context

### Original Request
The user identified that all BizSim agents operate on fake data — random SKU IDs, hardcoded prices, hardcoded agent IDs — making the entire economic simulation meaningless. The Product System (in-process read-only SQLite with `sku_catalog`, `sku_seller_mapping`, `sku_supplier_mapping`, `parts`, `bill_of_materials`) must be wired into all agents so they operate on real data.

### Interview Summary
**Key Discussions**:
- **Seller pricing**: Rule-based within `price_floor`/`price_ceiling` bounds from catalog (not pass-through, not LLM)
- **Supplier BOM**: Full enrichment — supplier queries its parts via `sku_supplier_mapping` + BOM tables, production tied to real BOM ratios
- **Agent IDs**: `peer_agents: dict[str, int]` injected at init, separate from ProductCatalog (topology ≠ product data)
- **Schema authority**: Implementation's `tenant_id` in PKs stays, but `ProductCatalog` wrapper binds `tenant_id` at construction time so agents never see it
- **All agents get catalog access**: Yes, but Transport/Government won't use it (pass-through/observer)
- **Sandbox safety**: No modifications needed — `ProductCatalog` is created outside `agents/`, injected as a plain Python object, agents call methods at runtime (no `sqlite3` import in agent code)

**Research Findings**:
- Consumer has 3 critical failures: random SKU IDs (L67-68), hardcoded base_price=100.0 (L119), random seller_id (L143)
- Seller has 4 critical failures: hardcoded transport=5000 (L129), gov=9000 (L160), supplier=2000 (L335), hardcoded pricing (L293-295)
- Supplier has 2 critical failures: hardcoded transport=1000 (L39), zero BOM awareness
- BaseAgent has no `catalog` parameter — no injection mechanism
- TickEngine has no Product System initialization
- `ProductSystem(Protocol): pass` is an empty stub

### Metis Review
**Identified Gaps** (addressed):
- **Architecture**: Place `ProductCatalog` in `bizsim/product_catalog.py` (OUTSIDE `agents/`) to avoid G1 CI violation
- **Backward compatibility**: `catalog: ProductCatalog | None = None` as keyword-only arg to `BaseAgent.__init__`
- **Agent IDs**: `peer_agents: dict[str, int]` config separate from ProductCatalog
- **Sandbox safety**: Use `TYPE_CHECKING` guard for ProductCatalog type import in agent files
- **Risk**: CI G1 will flag sqlite3 imports if ProductCatalog is inside `bizsim/agents/`

---

## Work Objectives

### Core Objective
Wire the in-process Product System into all BizSim agents so they operate on real SKU data — real IDs, real prices with floor/ceiling enforcement, real seller mappings, real supplier mappings with lead times, and real BOM data for the supply chain.

### Concrete Deliverables
- `bizsim/product_catalog.py` — Protocol + `SqliteProductCatalog` class with typed query methods
- Updated `bizsim/agents/base.py` — `catalog` and `peer_agents` keyword args on `BaseAgent.__init__`
- Updated `bizsim/agents/consumer.py` — Real SKU browsing, real prices, real seller selection
- Updated `bizsim/agents/seller.py` — Rule-based pricing, real supplier lookup, configurable peer IDs
- Updated `bizsim/agents/supplier.py` — Full BOM enrichment, real transport ID via `peer_agents`
- Updated `bizsim/engine.py` — ProductCatalog initialization, injection into all agents
- Updated `tests/test_integration.py` — Seeded catalog, deterministic agent IDs, full lifecycle assertions
- `tests/test_product_catalog.py` — Unit tests for ProductCatalog wrapper

### Definition of Done
- [ ] `pytest tests/` → ALL PASS (existing 57 + new tests)
- [ ] `ruff check bizsim/ tests/` → 0 errors
- [ ] `mypy --strict bizsim/` → 0 errors
- [ ] Zero `sqlite3` imports inside `bizsim/agents/`
- [ ] Zero hardcoded SKU IDs, prices, or agent IDs in agent code
- [ ] Integration test runs 100 ticks with catalog-sourced data and completes full purchase + restock lifecycle

### Must Have
- ProductCatalog binds `tenant_id` at construction — agents never pass `tenant_id` to queries
- All SKU IDs come from catalog lookups, never `random.randint()`
- Seller pricing respects `price_floor` and `price_ceiling` from catalog
- Seller finds suppliers via `sku_supplier_mapping`, not hardcoded ID
- Supplier knows its parts via BOM lookups
- Consumer picks sellers from `sku_seller_mapping`, not random
- Backward-compatible: `catalog=None` default means existing tests still pass without catalog

### Must NOT Have (Guardrails)
- **NO `sqlite3` import inside `bizsim/agents/`** — violates P1/G1 CI guard
- **NO LLM integration** — seller strategy is rule-based in V1
- **NO payment agent** — consumer sends payment message directly (existing pattern)
- **NO production constraints** — V1 has unlimited capacity, BOM is for enrichment only
- **NO YAML seed generator** — use programmatic `seed_catalog()` for tests
- **NO changes to `domain.py`, `events.py`, `channels.py`** — core types are frozen
- **NO over-abstraction** — `ProductCatalog` is one file, not a framework
- **NO excessive comments or JSDoc** — code is self-documenting with type hints

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest, 57 existing tests)
- **Automated tests**: TDD (tests first, then implementation)
- **Framework**: pytest
- **Each task follows**: RED (failing test) → GREEN (minimal impl) → REFACTOR

### QA Policy
Every task includes agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Library/Module**: Use Bash (pytest) — run tests, assert pass counts
- **Integration**: Use Bash (pytest) — run integration test, verify lifecycle assertions

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — sequential pair):
├── Task 1: ProductCatalog protocol + SQLite implementation + unit tests [deep]
└── Task 2: BaseAgent catalog/peer_agents injection [quick]

Wave 2 (Agent rewiring — MAX PARALLEL, 3 tasks):
├── Task 3: Consumer agent rewiring (depends: 1, 2) [unspecified-high]
├── Task 4: Seller agent rewiring (depends: 1, 2) [unspecified-high]
└── Task 5: Supplier agent rewiring (depends: 1, 2) [unspecified-high]

Wave 3 (Integration — sequential):
├── Task 6: TickEngine initialization (depends: 1, 2) [quick]
└── Task 7: Integration test update (depends: 3, 4, 5, 6) [deep]

Wave FINAL (Verification — 4 parallel):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)

Critical Path: Task 1 → Task 2 → Tasks 3/4/5 → Task 6 → Task 7 → F1-F4
Parallel Speedup: ~40% faster than sequential (Wave 2 runs 3 tasks in parallel)
Max Concurrent: 3 (Wave 2)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1    | —         | 2, 3, 4, 5, 6 | 1 |
| 2    | 1         | 3, 4, 5, 6 | 1 |
| 3    | 1, 2      | 7 | 2 |
| 4    | 1, 2      | 7 | 2 |
| 5    | 1, 2      | 7 | 2 |
| 6    | 1, 2      | 7 | 3 |
| 7    | 3, 4, 5, 6 | F1-F4 | 3 |
| F1-F4 | 7        | — | FINAL |

### Agent Dispatch Summary

- **Wave 1**: 2 tasks — T1 → `deep`, T2 → `quick`
- **Wave 2**: 3 tasks — T3/T4/T5 → `unspecified-high`
- **Wave 3**: 2 tasks — T6 → `quick`, T7 → `deep`
- **FINAL**: 4 tasks — F1 → `oracle`, F2/F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

- [x] 1. ProductCatalog Protocol + SQLite Implementation + Unit Tests
- [x] 2. Add catalog and peer_agents Injection to BaseAgent
- [x] 3. Wire ProductCatalog into ConsumerAgent
- [x] 4. Wire ProductCatalog into SellerAgent
- [x] 5. Wire ProductCatalog into SupplierAgent — Full BOM Enrichment
- [x] 6. Initialize and Inject ProductCatalog in TickEngine
- [x] 7. Update Integration Test with Catalog-Seeded Data
- [x] F1. **Plan Compliance Audit** — `oracle`
- [x] F2. **Code Quality Review** — `unspecified-high`
- [x] F3. **Real Manual QA** — `unspecified-high`
- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check "Must NOT do" compliance. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

| Commit | Message | Files | Pre-commit Check |
|--------|---------|-------|-----------------|
| 1 | `feat(product): add ProductCatalog protocol and SQLite implementation` | `bizsim/product_catalog.py`, `tests/test_product_catalog.py` | `pytest tests/test_product_catalog.py` |
| 2 | `feat(agents): add catalog and peer_agents injection to BaseAgent` | `bizsim/agents/base.py` | `pytest tests/` |
| 3 | `feat(consumer): wire ProductCatalog for real SKU browsing and seller selection` | `bizsim/agents/consumer.py`, `tests/test_consumer.py` (if exists) | `pytest tests/` |
| 4 | `feat(seller): wire ProductCatalog for rule-based pricing and supplier lookup` | `bizsim/agents/seller.py` | `pytest tests/` |
| 5 | `feat(supplier): wire ProductCatalog for BOM enrichment and peer_agents` | `bizsim/agents/supplier.py` | `pytest tests/` |
| 6 | `feat(engine): initialize and inject ProductCatalog in TickEngine` | `bizsim/engine.py` | `pytest tests/` |
| 7 | `feat(integration): update integration test with catalog-seeded data` | `tests/test_integration.py` | `pytest tests/` |

---

## Success Criteria

### Verification Commands
```bash
pytest tests/ -v                    # Expected: ALL PASS (57+ tests)
ruff check bizsim/ tests/          # Expected: 0 errors
mypy --strict bizsim/              # Expected: 0 errors
grep -r "sqlite3" bizsim/agents/   # Expected: no matches (P1 compliance)
grep -rn "randint" bizsim/agents/consumer.py  # Expected: no SKU-related randint calls
grep -rn "= 5000\|= 9000\|= 2000\|= 1000" bizsim/agents/  # Expected: no hardcoded agent IDs
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All existing tests still pass (backward compatibility)
- [ ] New tests cover ProductCatalog wrapper thoroughly
- [ ] Integration test completes 100-tick lifecycle with real catalog data
- [ ] Zero hardcoded product data remains in agent code
