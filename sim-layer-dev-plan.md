# BizSim — Simulation Layer Development Plan

> **Purpose**: Step-by-step guide for AI-assisted implementation of the BizSim simulation layer.
> Each session loads only the spec slices it needs, keeping context small and focused.

---

## 1. Monorepo Structure

```
bizsim/                          ← Python simulation package
  __init__.py
  domain.py                      ← TenantContext, EventEmitter
  events.py                      ← ActionEvent, ReadPattern, WritePattern
  channels.py                    ← Ch2Message type
  engine.py                      ← Tick loop, channel orchestration
  product_system.py              ← SQLite schema, SKU catalog, BOM
  agents/
    __init__.py
    _sandbox.py                  ← Import blocker (P1 enforcement)
    runner.py                    ← Agent entry point (activates sandbox)
    base.py                      ← BaseAgent, scheduler, inbox drain
    consumer.py
    seller.py
    supplier.py
    transport.py
    government.py
  community/
    __init__.py
    subsystem.py                 ← Independent Cascade, graph init
  tests/
    test_domain.py
    test_engine.py
    test_agents.py
    test_community.py
    test_product_system.py

go-translator/                   ← Go workload translator
  go.mod
  main.go
  operations/                    ← Domain-partitioned YAML catalog
    store.yaml
    consumer.yaml
    supplier.yaml
    transport.yaml
    government.yaml
    community.yaml
  pkg/
    catalog/                     ← Catalog, OperationDef, Validate()
      catalog.go
      catalog_test.go
    executor/                    ← Executor, TenantScope, unexported *sql.DB
      executor.go
      tenant.go
      executor_test.go
    handler/                     ← Agent-facing handler (no database/sql import)
      handler.go
      handler_test.go
    internal/
      db/                        ← Connection setup (only executor imports)
        db.go
    reducers/                    ← Reducer implementations
      reducers.go
      reducers_test.go

specs/                           ← Spec slices (14 files, 2501 lines total)
  ARCHITECTURE.md    (183 lines)
  CONTRACTS.md       (305 lines)
  GO_TRANSLATOR.md   (314 lines)
  PRODUCT_SYSTEM.md  (118 lines)
  AGENT_BASE.md      (167 lines)
  CONSUMER.md        (481 lines)
  SELLER.md          (340 lines)
  SUPPLIER.md        (113 lines)
  TRANSPORT.md       ( 98 lines)
  GOVERNMENT.md      ( 78 lines)
  COMMUNITY.md       (146 lines)
  MESSAGES.md        ( 46 lines)
  EVENTS.md          ( 77 lines)
  QUERIES.md         ( 35 lines)

.github/
  workflows/
    arch-guard.yml               ← CI guardrail checks (G1–G6)
```

---

## 2. Implementation Layers

Components are ordered by dependency. Each layer can begin once all prior layers are complete. Within a layer, sessions can run in parallel.

```
Layer 0 — Schemas (reference-only, loaded by every session)
  MESSAGES.md + EVENTS.md + QUERIES.md  (158 lines combined)

Layer 1 — Foundation (must build first)
  Session 1: CONTRACTS.md   → Python types, protocols, inbox contract
  Session 2: ARCHITECTURE.md → Tick loop, engine core
  Session 3: PRODUCT_SYSTEM.md → SQLite schema (parallel with Sessions 1–2)

Layer 2 — Infrastructure (after Layer 1)
  Session 4: GO_TRANSLATOR.md → Go translator, YAML catalog, reducers
  Session 5: AGENT_BASE.md   → Python base class, scheduler, inbox drain
  (Sessions 4 and 5 can run in parallel)

Layer 3 — Agents (after Layer 2)
  Session 6: TRANSPORT.md    → Transport agent (fewest dependencies)
  Session 7: SUPPLIER.md     → Supplier agent (after Transport)
  Session 8: SELLER.md       → Seller agent (after Transport + Supplier)
  Session 9: CONSUMER.md     → Consumer agent (after Seller)
  Session 10: GOVERNMENT.md  → Government agent (anytime after Layer 2)
  (Session 10 has no dependencies on Sessions 6–9)

Layer 4 — Subsystems (after Layer 3)
  Session 11: COMMUNITY.md   → Community subsystem (after Consumer)
```

### Critical Path

```
CONTRACTS → ARCHITECTURE → GO_TRANSLATOR → AGENT_BASE → TRANSPORT → SELLER → CONSUMER
```

This is the "Minimum Viable Purchase" path — the shortest route to a running end-to-end purchase flow. GOVERNMENT and COMMUNITY are not on the critical path and can be deferred.

### Parallelization Opportunities

| Parallel Group         | Sessions          | Prerequisite        |
|------------------------|-------------------|---------------------|
| Foundation             | 1, 2, 3           | None (all independent) |
| Infrastructure         | 4, 5              | Sessions 1, 2       |
| Off-critical agents    | 10 (Government)   | Sessions 4, 5       |

---

## 3. Token Budget

Each session loads a **primary spec** (to implement) plus **reference specs** (for type signatures and contracts). Estimated token counts assume ~3.5 tokens per line of Markdown.

| Session | Primary Spec           | Lines | Reference Specs                             | Ref Lines | Total Lines | ~Tokens |
|---------|------------------------|-------|---------------------------------------------|-----------|-------------|---------|
| 1       | CONTRACTS.md           | 305   | EVENTS.md, MESSAGES.md, QUERIES.md          | 158       | 463         | ~1,600  |
| 2       | ARCHITECTURE.md        | 183   | CONTRACTS.md, EVENTS.md, MESSAGES.md        | 428       | 611         | ~2,100  |
| 3       | PRODUCT_SYSTEM.md      | 118   | —                                           | 0         | 118         | ~400    |
| 4       | GO_TRANSLATOR.md       | 314   | CONTRACTS.md, EVENTS.md, QUERIES.md         | 417       | 731         | ~2,600  |
| 5       | AGENT_BASE.md          | 167   | CONTRACTS.md, EVENTS.md, MESSAGES.md        | 428       | 595         | ~2,100  |
| 6       | TRANSPORT.md           | 98    | AGENT_BASE.md, CONTRACTS.md, EVENTS.md, MESSAGES.md | 595 | 693       | ~2,400  |
| 7       | SUPPLIER.md            | 113   | AGENT_BASE.md, CONTRACTS.md, EVENTS.md, MESSAGES.md | 595 | 708       | ~2,500  |
| 8       | SELLER.md              | 340   | AGENT_BASE.md, CONTRACTS.md, EVENTS.md, MESSAGES.md, QUERIES.md | 630 | 970 | ~3,400  |
| 9       | CONSUMER.md            | 481   | AGENT_BASE.md, CONTRACTS.md, EVENTS.md, MESSAGES.md, QUERIES.md | 630 | 1,111 | ~3,900  |
| 10      | GOVERNMENT.md          | 78    | AGENT_BASE.md, CONTRACTS.md, EVENTS.md      | 549       | 627         | ~2,200  |
| 11      | COMMUNITY.md           | 146   | CONTRACTS.md, EVENTS.md                     | 382       | 528         | ~1,800  |

**Largest session**: Session 9 (Consumer) at ~3,900 tokens of spec — well within context limits even with code and conversation overhead.

---

## 4. Session Prompt Templates

Each session follows the same structure. Copy the template, fill in the specifics, and paste into a fresh Sisyphus conversation.

### Template

```
## Session N: [Component Name]

### Specs to Load
- **Primary** (implement this): specs/[PRIMARY].md
- **Reference** (for type signatures only): specs/[REF1].md, specs/[REF2].md
- **Schema reference** (always): specs/EVENTS.md, specs/MESSAGES.md, specs/QUERIES.md

### What Exists (from prior sessions)
[List files/modules already implemented that this session depends on]

### Deliverables
[List output files this session must produce]

### Constraints
- Match types and protocols defined in CONTRACTS.md exactly
- Use event_type strings from EVENTS.md — do not invent new ones
- Use msg_type strings from MESSAGES.md — do not invent new ones
- Use query templates from QUERIES.md — do not invent new ones

### Exit Criteria
Write tests. Run tests. All tests must pass.
Run lsp_diagnostics on all changed files — no errors.
```

---

### Session 1: Python Domain Types & Contracts

```
## Session 1: Python Domain Types & Contracts

### Specs to Load
- **Primary**: specs/CONTRACTS.md
- **Reference**: specs/EVENTS.md, specs/MESSAGES.md, specs/QUERIES.md

### What Exists
Nothing — this is the first session. Start from scratch.

### Deliverables
- bizsim/__init__.py
- bizsim/domain.py          — TenantContext, EventEmitter
- bizsim/events.py          — ActionEvent, ReadPattern, WritePattern dataclasses
- bizsim/channels.py        — Ch2Message dataclass
- bizsim/tests/test_domain.py

### Constraints
- All dataclasses must be frozen=True
- EventEmitter.emit() must bake tenant_id from TenantContext — caller never passes tenant_id
- ActionEvent.params must be dict[str, int | float | str | bool] (scalar values only)
- Ch2Message must NOT be a subclass of ActionEvent
- Implement __post_init__ SQL keyword guard on ActionEvent

### Exit Criteria
Write tests. Run tests. All tests must pass.
Run lsp_diagnostics on all changed files — no errors.
```

---

### Session 2: Engine Core & Tick Loop

```
## Session 2: Engine Core & Tick Loop

### Specs to Load
- **Primary**: specs/ARCHITECTURE.md
- **Reference**: specs/CONTRACTS.md, specs/EVENTS.md, specs/MESSAGES.md

### What Exists (from Session 1)
- bizsim/domain.py (TenantContext, EventEmitter)
- bizsim/events.py (ActionEvent, ReadPattern, WritePattern)
- bizsim/channels.py (Ch2Message)

### Deliverables
- bizsim/engine.py           — TickEngine, channel orchestration, agent scheduling
- bizsim/tests/test_engine.py

### Constraints
- Tick loop must follow the exact phase order from ARCHITECTURE.md:
  1. Schedule agents for this tick
  2. Each agent: drain inbox → decide → emit events
  3. Collect all Ch.1 events → batch to Go translator
  4. Deliver Ch.2 messages to recipient inboxes
  5. Process Ch.3 read queries
  6. Advance tick counter
- Engine must support dual-mode reads (Ch.3): agents read via query templates, never raw SQL
- Engine must not import or depend on any agent implementation

### Exit Criteria
Write tests. Run tests. All tests must pass.
Run lsp_diagnostics on all changed files — no errors.
```

---

### Session 3: Product System (SQLite)

```
## Session 3: Product System (SQLite)

### Specs to Load
- **Primary**: specs/PRODUCT_SYSTEM.md

### What Exists
Nothing agent-related needed — this is a standalone data layer.

### Deliverables
- bizsim/product_system.py   — SQLite schema creation, SKU catalog, BOM, sku_supplier_mapping
- bizsim/tests/test_product_system.py

### Constraints
- All tables must include tenant_id column for multi-tenant isolation
- Use sqlite3 from stdlib — no ORM
- Schema must match PRODUCT_SYSTEM.md exactly (table names, column names, types)
- Provide helper functions for: create_tables(), seed_catalog(), lookup_sku(), lookup_bom()

### Exit Criteria
Write tests. Run tests. All tests must pass.
Run lsp_diagnostics on all changed files — no errors.
```

---

### Session 4: Go Translator

```
## Session 4: Go Translator

### Specs to Load
- **Primary**: specs/GO_TRANSLATOR.md
- **Reference**: specs/CONTRACTS.md, specs/EVENTS.md, specs/QUERIES.md

### What Exists (from Sessions 1–3)
- Python domain types (for understanding the event shape that arrives via JSON)
- Product system schema (for writing correct SQL in YAML operations)

### Deliverables
- go-translator/go.mod
- go-translator/main.go
- go-translator/pkg/catalog/catalog.go      — Catalog, OperationDef, Validate()
- go-translator/pkg/catalog/catalog_test.go
- go-translator/pkg/executor/executor.go    — Executor, unexported *sql.DB
- go-translator/pkg/executor/tenant.go      — TenantScope (unexported constructor)
- go-translator/pkg/executor/executor_test.go
- go-translator/pkg/handler/handler.go      — Agent-facing handler
- go-translator/pkg/handler/handler_test.go
- go-translator/pkg/internal/db/db.go       — Connection setup
- go-translator/pkg/reducers/reducers.go    — Reducer implementations
- go-translator/operations/*.yaml           — Domain-partitioned operation catalog

### Constraints
- handler/ must NOT import database/sql
- *sql.DB must be unexported in executor
- TenantScope constructor must be unexported — only executor creates scopes
- NewExecutor must require a validated catalog (Validate() must have been called)
- Unknown event types must be rejected at runtime
- All SQL lives in YAML — no SQL string literals in Go code outside catalog expansion

### Exit Criteria
Write tests. Run tests (go test ./...). All tests must pass.
Verify: grep -rn '"database/sql"' pkg/handler/ returns nothing.
Verify: grep -rn 'db\.\(Query\|Exec\)' pkg/ shows hits only in pkg/executor/.
```

---

### Session 5: Agent Base Class

```
## Session 5: Agent Base Class

### Specs to Load
- **Primary**: specs/AGENT_BASE.md
- **Reference**: specs/CONTRACTS.md, specs/EVENTS.md, specs/MESSAGES.md

### What Exists (from Sessions 1–2)
- bizsim/domain.py (TenantContext, EventEmitter)
- bizsim/events.py (ActionEvent, ReadPattern, WritePattern)
- bizsim/channels.py (Ch2Message)
- bizsim/engine.py (TickEngine — for understanding scheduling interface)

### Deliverables
- bizsim/agents/__init__.py
- bizsim/agents/_sandbox.py   — Import blocker (P1 enforcement)
- bizsim/agents/runner.py     — Agent entry point (activates sandbox before imports)
- bizsim/agents/base.py       — BaseAgent with scheduling, inbox drain, pipeline correlation
- bizsim/tests/test_agents.py — Tests for base agent, sandbox, scheduling

### Constraints
- _sandbox.py must block: sqlalchemy, sqlite3, psycopg2, pymysql, mysql.connector,
  bizsim.translator, bizsim.db, subprocess
- runner.py must call activate() BEFORE importing any agent module
- BaseAgent must implement the inbox ordering from AGENT_BASE.md
- Pipeline correlation must handle failure → retry and failure → dead-letter
- Scheduling must support both tick-interval and event-triggered modes

### Exit Criteria
Write tests. Run tests. All tests must pass.
Test that importing sqlite3 inside an agent raises ImportError after sandbox activation.
Run lsp_diagnostics on all changed files — no errors.
```

---

### Session 6: Transport Agent

```
## Session 6: Transport Agent

### Specs to Load
- **Primary**: specs/TRANSPORT.md
- **Reference**: specs/AGENT_BASE.md, specs/CONTRACTS.md, specs/EVENTS.md, specs/MESSAGES.md

### What Exists (from Sessions 1–5)
- All domain types, engine, base agent class, sandbox

### Deliverables
- bizsim/agents/transport.py
- Tests for transport agent (shipment state machine)

### Constraints
- Must extend BaseAgent
- Shipment state machine: pending → in_transit → delivered
- ShipRequest uses shipment_type discriminator: "consumer_order" or "restock"
- On delivery: emit DeliveryComplete event + send Ch.2 message to originator
- For consumer_order: notify Seller (who forwards to Consumer)
- For restock: notify Supplier (who forwards to Seller with RestockDelivered)

### Exit Criteria
Write tests. Run tests. All tests must pass.
Run lsp_diagnostics on all changed files — no errors.
```

---

### Session 7: Supplier Agent

```
## Session 7: Supplier Agent

### Specs to Load
- **Primary**: specs/SUPPLIER.md
- **Reference**: specs/AGENT_BASE.md, specs/CONTRACTS.md, specs/EVENTS.md, specs/MESSAGES.md

### What Exists (from Sessions 1–6)
- All domain types, engine, base agent, transport agent

### Deliverables
- bizsim/agents/supplier.py
- Tests for supplier agent (restock pipeline)

### Constraints
- Must extend BaseAgent
- Restock pipeline: receive RestockRequest → emit SupplierShipment event → send ShipRequest to Transport
- On DeliveryComplete from Transport: forward RestockDelivered to the requesting Seller
- Must validate sku_supplier_mapping before accepting restock requests

### Exit Criteria
Write tests. Run tests. All tests must pass.
Run lsp_diagnostics on all changed files — no errors.
```

---

### Session 8: Seller Agent

```
## Session 8: Seller Agent

### Specs to Load
- **Primary**: specs/SELLER.md
- **Reference**: specs/AGENT_BASE.md, specs/CONTRACTS.md, specs/EVENTS.md,
  specs/MESSAGES.md, specs/QUERIES.md

### What Exists (from Sessions 1–7)
- All domain types, engine, base agent, transport, supplier

### Deliverables
- bizsim/agents/seller.py
- Tests for seller agent (pricing pipeline, order processing, restock trigger)

### Constraints
- Must extend BaseAgent
- LLM strategy interface: Seller.decide_pricing() is the LLM integration point
- Pricing pipeline: read market data (Ch.3) → LLM decides → emit PriceUpdate event
- Order processing: receive PurchaseRequest → validate inventory → accept/reject
  - Accept: emit OrderAccepted + send ShipRequest to Transport
  - Reject: send OrderRejected to Consumer
- Restock trigger: when inventory < threshold → send RestockRequest to Supplier
- On RestockDelivered from Supplier: update inventory

### Exit Criteria
Write tests. Run tests. All tests must pass.
Run lsp_diagnostics on all changed files — no errors.
```

---

### Session 9: Consumer Agent

```
## Session 9: Consumer Agent

### Specs to Load
- **Primary**: specs/CONSUMER.md
- **Reference**: specs/AGENT_BASE.md, specs/CONTRACTS.md, specs/EVENTS.md,
  specs/MESSAGES.md, specs/QUERIES.md

### What Exists (from Sessions 1–8)
- All domain types, engine, base agent, transport, supplier, seller

### Deliverables
- bizsim/agents/consumer.py
- Tests for consumer agent (purchase + cancel pipelines, funnel)

### Constraints
- Must extend BaseAgent
- Purchase pipeline:
  1. Browse (Ch.3 query) → Evaluate → send PurchaseRequest to Seller
  2. On OrderAccepted: update order status to accepted
  3. On DeliveryConfirmed: update order status to delivered, emit satisfaction event
  4. On OrderRejected: update status, optionally retry with different seller
- Cancel pipeline:
  1. Send CancelRequest to Seller
  2. On CancelConfirmed: update order status to cancelled
- Consumer funnel: awareness → interest → consideration → purchase → loyalty
- Community influence affects funnel progression (read from community subsystem)
- Order status lifecycle: requested → accepted → delivered (or cancel_requested → cancelled)

### Exit Criteria
Write tests. Run tests. All tests must pass.
Run lsp_diagnostics on all changed files — no errors.
```

---

### Session 10: Government Agent

```
## Session 10: Government Agent

### Specs to Load
- **Primary**: specs/GOVERNMENT.md
- **Reference**: specs/AGENT_BASE.md, specs/CONTRACTS.md, specs/EVENTS.md

### What Exists (from Sessions 1–5)
- All domain types, engine, base agent (no dependency on other agents)

### Deliverables
- bizsim/agents/government.py
- Tests for government agent (statistics pipeline)

### Constraints
- Must extend BaseAgent
- Statistics pipeline: collect aggregate events → compute market metrics → emit StatisticsPublished
- Operates on fixed tick interval (not event-triggered)
- Reads aggregate data via Ch.3 queries
- Does not send Ch.2 messages to other agents

### Exit Criteria
Write tests. Run tests. All tests must pass.
Run lsp_diagnostics on all changed files — no errors.
```

---

### Session 11: Community Subsystem

```
## Session 11: Community Subsystem

### Specs to Load
- **Primary**: specs/COMMUNITY.md
- **Reference**: specs/CONTRACTS.md, specs/EVENTS.md

### What Exists (from Sessions 1–9)
- All domain types, engine, all agents (especially Consumer for influence interface)

### Deliverables
- bizsim/community/__init__.py
- bizsim/community/subsystem.py  — Independent Cascade model, social graph
- bizsim/tests/test_community.py

### Constraints
- Community is NOT an agent — it is a subsystem called by the engine
- Uses enqueue_activation() direct function call, NOT Ch.2 messages
- Social graph initialization: random graph with configurable density
- Independent Cascade: activation spreads probabilistically through edges
- Influence affects Consumer funnel (awareness → interest transition probability)
- Must be deterministic given the same random seed

### Exit Criteria
Write tests. Run tests. All tests must pass.
Run lsp_diagnostics on all changed files — no errors.
```

---

## 5. CI Guardrails (Session 12)

After all components are implemented, set up the CI workflow that enforces architectural invariants.

```
## Session 12: CI Guardrails

### Specs to Load
- **Reference**: specs/ARCHITECTURE.md (principles P1, P4, P9 and channel isolation)

### What Exists
- All components from Sessions 1–11

### Deliverables
- .github/workflows/arch-guard.yml

### Guardrail Checks (G1–G6)
G1: P1 — No SQL imports in bizsim/agents/ (grep check)
G1: P1 — Sandbox integrity (AST check: _BLOCKED_MODULES contains required entries)
G2: P4 — Tenant sovereignty structural check
G3: P9 — No database/sql outside go-translator/pkg/executor/ and pkg/internal/db/
G3: P9 — No raw db.Query calls outside executor.go
G4: P9 — Operation catalog validation (go test includes catalog.Validate())
G5: Ch.2 — No inter-agent message handling in Go code
G6: Meta — Test count floor (Python ≥ 20, Go ≥ 15; ratchet upward as tests grow)

### Exit Criteria
Run the workflow locally (act or manual grep commands). All checks pass.
```

---

## 6. Integration Test (Session 13)

```
## Session 13: End-to-End Integration Test

### Specs to Load
- **Reference**: specs/ARCHITECTURE.md, specs/CONTRACTS.md

### What Exists
- All components from Sessions 1–12

### Deliverables
- bizsim/tests/test_integration.py — End-to-end purchase flow test

### Test Scenario: Minimum Viable Purchase
1. Initialize engine with 1 tenant, 1 consumer, 1 seller, 1 supplier, 1 transport
2. Seed product catalog with 1 SKU
3. Run simulation for N ticks
4. Assert: Consumer browses → sends PurchaseRequest → Seller accepts →
   Transport delivers → Consumer receives → satisfaction event emitted
5. Assert: Seller inventory drops → RestockRequest → Supplier ships →
   Transport delivers → Seller inventory restored
6. Assert: All events have correct tenant_id (P4 sovereignty)
7. Assert: No SQL-like strings in any event params (P1 guard)

### Exit Criteria
Integration test passes end-to-end with deterministic seed.
Full simulation completes without errors for 50 ticks.
```

---

## 7. Session Dependency Graph (Visual)

```
         ┌──────────┐  ┌──────────────┐  ┌────────────────┐
         │ Session 1 │  │  Session 2   │  │   Session 3    │
         │ Contracts │  │   Engine     │  │ Product System │
         └─────┬─────┘  └──────┬───────┘  └────────────────┘
               │               │               (standalone)
               └───────┬───────┘
                       │
              ┌────────┴────────┐
              │                 │
        ┌─────┴─────┐   ┌──────┴──────┐
        │ Session 4  │   │  Session 5  │
        │ Go Transl. │   │ Agent Base  │
        └─────┬──────┘   └──────┬──────┘
              └────────┬────────┘
                       │
           ┌───────────┼────────────┐
           │           │            │
     ┌─────┴─────┐    │    ┌───────┴───────┐
     │ Session 6  │    │    │  Session 10   │
     │ Transport  │    │    │  Government   │
     └─────┬──────┘    │    └───────────────┘
           │           │
     ┌─────┴─────┐    │
     │ Session 7  │    │
     │ Supplier   │    │
     └─────┬──────┘    │
           │           │
     ┌─────┴─────┐    │
     │ Session 8  │    │
     │  Seller    │    │
     └─────┬──────┘    │
           │           │
     ┌─────┴─────┐    │
     │ Session 9  │    │
     │ Consumer   │    │
     └─────┬──────┘    │
           │           │
     ┌─────┴─────┐    │
     │ Session 11 │    │
     │ Community  │    │
     └─────┬──────┘    │
           └─────┬─────┘
                 │
          ┌──────┴──────┐
          │  Session 12  │
          │ CI Guardrails│
          └──────┬───────┘
                 │
          ┌──────┴──────┐
          │  Session 13  │
          │  Integration │
          └─────────────┘
```

---

## 8. How to Use This Plan

### Starting a Session

1. Open a fresh Sisyphus conversation
2. Copy the session prompt from Section 4
3. If prior sessions produced code, tell Sisyphus what exists:
   - "The following files exist from prior sessions: [list]"
4. Paste the session prompt

### Between Sessions

- Verify each session's output before starting the next
- Run tests from prior sessions to confirm nothing broke
- If a session produces output that doesn't match CONTRACTS.md, fix it before proceeding

### Skipping Sessions

- Sessions 10 (Government) and 11 (Community) can be deferred indefinitely
- Session 3 (Product System) can run anytime — it has no dependencies
- Don't skip Sessions 1–2 or 4–5 — everything else depends on them

### Adjusting the Plan

- If a session gets too large, split the primary spec and create sub-sessions
- If you discover a spec gap, update the relevant spec file in `specs/` first, then implement
- The token budget column helps decide if a session needs splitting (>5K spec tokens → consider splitting)
