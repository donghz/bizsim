# BizSim V2: Economic Ecosystem Simulation for Distributed Database Testing

## Vision & System Architecture

> **One-sentence pitch**: A modular economic ecosystem simulation comprising autonomous agents, structured markets, and social dynamics — generating naturally diverse, temporally realistic, cross-tenant database workloads that bridge the gap between synthetic benchmarks and production traffic patterns.

---

## Table of Contents

1. [Vision](#1-vision)
2. [System Decomposition](#2-system-decomposition)
3. [Simulation Framework](#3-simulation-framework)
4. [Agent Subsystem](#4-agent-subsystem)
5. [Market Subsystem](#5-market-subsystem)
6. [Society Subsystem](#6-society-subsystem)
7. [Translator Subsystem](#7-translator-subsystem)
8. [Cross-Subsystem Interaction Model](#8-cross-subsystem-interaction-model)
9. [Architecture Principles](#9-architecture-principles)
10. [Architectural Guardrails](#10-architectural-guardrails)
11. [Key Design Questions](#11-key-design-questions)
12. [Tension Analysis](#12-tension-analysis)
13. [Capacity Planning](#13-capacity-planning)
- [Appendix A: Key Researchers & Labs](#appendix-a-key-researchers--labs)
- [Appendix B: Landscape — Existing Open Source Projects & Research](#appendix-b-landscape)

---

## 1. Vision

BizSim simulates a complete economic ecosystem:

- **Markets** — consumer markets (B2C) and industrial markets (B2B supply chain), where prices, supply, and demand are observable by all participants
- **Agents** — consumers, sellers, suppliers, transport providers, and government — each with distinct intelligence tiers and behavioral models
- **Society** — social networks where trends propagate and influence consumer behavior; public media channels (V2) for broadcast influence
- **Logistics** — transportation providers moving goods through state-machine-driven shipment lifecycles
- **Government** — a statistical authority that observes the entire economy, publishes aggregate indicators, and updates market conditions

**The original purpose**: build a large and diverse testing system for a **multi-tenant distributed database** like TiDB. The simulation generates realistic, heterogeneous database workloads — not an economics research platform.

### BizSim Unit World

A single BizSim "unit world" is one self-contained economic ecosystem. The diagram below shows the five subsystems and their relationships:

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                          BIZSIM UNIT WORLD                                    │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                    SIMULATION FRAMEWORK                                 │  │
│  │                    (TickEngine, event routing, scheduling)              │  │
│  │                                                                         │  │
│  │  ┌───────────────┐  ┌───────────────┐  ┌────────────────────────────┐   │  │
│  │  │   AGENTS      │  │   MARKETS     │  │       SOCIETY              │   │  │
│  │  │               │  │               │  │                            │   │  │
│  │  │  Consumer     │◄─┤  Consumer Mkt │  │  Social Network            │   │  │
│  │  │  Seller       │◄─┤  (B2C)        │  │  (peer-to-peer influence)  │   │  │
│  │  │  Supplier     │◄─┤               │  │                            │   │  │
│  │  │  Transport    │  │  Industrial   │  │  Media (V2)                │   │  │
│  │  │  Government ──┼─►│  Mkt (B2B)    │  │  (broadcast influence)     │   │  │
│  │  │               │  │               │  │                            │   │  │
│  │  │  (decisions   │  │  (prices,     │  │  (trend propagation,       │   │  │
│  │  │   via Ch.2    │  │   supply/     │  │   purchase sharing,        │   │  │
│  │  │   messages)   │  │   demand)     │  │   network diffusion)       │   │  │
│  │  └───────┬───────┘  └───────────────┘  └────────────────────────────┘   │  │
│  │          │ Ch.1 Action Events + Ch.3 Query Requests                     │  │
│  └──────────┼──────────────────────────────────────────────────────────────┘  │
│             │                                                                 │
│             ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                     TRANSLATOR                                          │  │
│  │          (YAML operation catalog, SQL execution,                        │  │
│  │           result reduction, tenant routing)                             │  │
│  └──────────────────────────────┬──────────────────────────────────────────┘  │
│                                 │ SQL                                         │
│                                 ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                           TiDB                                          │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────────────┘
```

### Tenant Mapping Summary

Each entity group maps to a distinct DB tenant type:

| Entity Group | DB Tenant Type | Access Pattern | Key Tables |
|---|---|---|---|
| Marketplace | Shared-schema | Mixed read/write | products, categories |
| Individual Store | Per-store schema/DB | Inventory hotspot | store_orders, inventory, catalog |
| Supply Chain | Per-supplier-group | Batch updates | suppliers, supply_chain_edges |
| Consumer App | Community platform | High-write social | consumer_orders, consumer_profiles |
| Social Network | Social graph | Graph traversal | community_posts, influence_edges |
| Transport | Logistics provider | Append-heavy | shipments, tracking_events |
| Government | Analytics | Read-heavy agg | gov_records, statistics |
| Payments | Financial ledger | Strict transactional | transactions (double-entry) |

---

## 2. System Decomposition

BizSim is composed of five subsystems with clear boundaries and responsibilities:

| Subsystem | Location | Responsibility | What It Owns |
|---|---|---|---|
| **Simulation Framework** | `bizsim/` (root-level modules) | Tick orchestration, event routing, scheduling, domain types, channels | `engine.py`, `domain.py`, `events.py`, `channels.py`, `scheduling.yaml` |
| **Agent Subsystem** | `bizsim/agents/` | Individual and organizational agent implementations, agent lifecycle, sandbox | `base.py`, `consumer.py`, `seller.py`, `supplier.py`, `transport.py`, `government.py`, `_sandbox.py`, `runner.py` |
| **Market Subsystem** | `bizsim/markets/` (impl) + `bizsim/market.py` (facade) | Product catalogs, SKU management, pricing data, supply chain topology, market state | Consumer market (SKUs, categories), Industrial market (parts, BOM, supplier mappings) |
| **Society Subsystem** | `bizsim/society/` (impl) + `bizsim/social.py` (facade) | Social network graph, influence propagation, trend dynamics; media channels (V2) | Community subsystem (Independent Cascade), media subsystem (V2) |
| **Translator Subsystem** | `go-translator/` | SQL generation, execution, result reduction, tenant routing, connection management | YAML operation catalog, Go executor, reducers |

### Directory Structure

```
bizsim/
  __init__.py                  # Package root — re-exports core types
  engine.py                    # TickEngine — tick loop orchestration
  domain.py                    # Core types (TenantContext, ActionEvent, WritePattern, ReadPattern)
  events.py                    # EventEmitter, QueryRequest, QueryResult, PendingQuery
  channels.py                  # InterAgentMessage, InboxItem
  scheduling.yaml              # Agent scheduling configuration

  agents/                      # Agent subsystem
    __init__.py
    _sandbox.py                # Import blocker (P1 enforcement)
    base.py                    # BaseAgent, AgentProtocol
    runner.py                  # Agent execution entry point
    consumer.py
    seller.py
    supplier.py
    transport.py
    government.py

  markets/                     # Market subsystem (implementation)
    __init__.py
    consumer_market.py         # SKU catalog, categories, pricing — B2C
    industrial_market.py       # Parts, BOM, supplier mappings — B2B supply chain
    schema.py                  # Shared SQLite schema definitions (tables, indexes)

  market.py                    # Market facade — MarketFactory + market interfaces

  society/                     # Society subsystem (implementation)
    __init__.py
    community.py               # Social network graph + Independent Cascade propagation
    media.py                   # V2: public media / broadcast influence

  social.py                    # Society facade — access to community and media

go-translator/                 # Translator subsystem
  operations/                  # YAML operation catalog (domain-partitioned)
  pkg/catalog/                 # Catalog loading & validation
  pkg/executor/                # SQL execution (only DB access point)
  pkg/handler/                 # Agent-facing handler (no DB imports)
  pkg/reducers/                # Result reduction logic
  pkg/internal/db/             # Connection setup

specs/                         # Specification files
tests/                         # Test suite
docs/                          # Design documents
```

### Subsystem Dependency Rules

```
                 ┌──────────────┐
                 │  Simulation  │
                 │  Framework   │
                 └──────┬───────┘
                        │ depends on
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │  Agents  │  │ Markets  │  │ Society  │
    └──────────┘  └──────────┘  └──────────┘
          │                           │
          │     reads from            │
          ├──────► Markets            │
          │     influenced by         │
          ├──────► Society            │
          │                           │
          ▼                           ▼
    ┌─────────────────────────────────────┐
    │            Translator               │
    │  (receives Ch.1 + Ch.3 only)        │
    └─────────────────────────────────────┘
```

**Key dependency rules:**
- **Agents** depend on the **Framework** (for base types, emitters, channels) and read from **Markets** (for product/pricing data) and are influenced by **Society** (trend multipliers).
- **Markets** depend only on the **Framework** (for domain types). Markets do not depend on agents.
- **Society** depends only on the **Framework**. Society does not depend on agents.
- **Translator** is a separate process (Go). It receives Ch.1 and Ch.3 events. It never receives Ch.2 messages, market state, or society state.
- The **TickEngine** (framework) orchestrates all subsystems — it calls into agents, markets, and society during each tick.

---

## 3. Simulation Framework

The framework provides the tick-based execution environment, core domain types, and communication channels that all other subsystems build upon.

### Core Types

```python
@dataclass(frozen=True)
class TenantContext:
    tenant_id: str                   # Immutable — baked into EventEmitter

@dataclass
class ActionEvent:                   # Channel 1: agent → translator → DB
    event_id: UUID
    event_type: str
    agent_id: int
    tenant_id: str
    tick: int
    reads: list[ReadPattern]
    writes: list[WritePattern]
    messages: list[InterAgentMessage]  # Ch.2 messages to route
    queries: list[QueryRequest]        # Ch.3 queries to issue

@dataclass(frozen=True)
class InterAgentMessage:             # Channel 2: agent → agent (in-memory)
    msg_type: str
    from_agent: int
    to_agent: int
    from_tenant: str
    tick_sent: int
    payload: dict

@dataclass
class QueryRequest:                  # Channel 3: agent → translator → DB → agent
    query_id: str
    agent_id: int
    query_template: str
    params: dict
    tick_issued: int
```

### Three Communication Channels

| Channel | Direction | What flows | Crosses translator? | Touches DB? |
|---|---|---|---|---|
| **Ch.1: Action Events** | Agent → Translator → TiDB | Domain events (`order_accepted`, `shipment_created`) | Yes — translated to SQL | Yes — INSERT/UPDATE to agent's **own** tenant |
| **Ch.2: Inter-Agent Messages** | Agent → Agent (via inbox) | Domain requests (`PlaceOrder`, `ShipRequest`, `Charge`) | **No** — stays inside simulation | **No** — pure in-memory |
| **Ch.3: Query Requests** | Agent → Translator → TiDB → Agent | Domain questions + reduced answers | Yes — translated to SQL, results reduced | Yes — SELECT from agent's **own** tenant |

### Tick Loop

The `TickEngine` orchestrates a 7-step sequence per tick:

```
Per tick:
  0. Drain inboxes — each agent processes Ch.2 messages and Ch.3 query results
  1. Process external events (disruptions, policy changes, trend injections)
  2. Run agent decision cycles (consumers browse/buy, sellers reprice, suppliers produce)
  3. Advance transport/logistics state machines
  4. Run society propagation (social influence, batched)
  5. Government aggregation + market state update (every N ticks)
  6. Emit and route:
     — Ch.1 events → Go translator for DB writes
     — Ch.2 messages → target agents' inboxes (available next tick)
     — Ch.3 query requests → Go translator for async DB reads
```

### Dual-Mode Read Path

```
                        ┌─────────────────────────────────────────────────────┐
                        │              Go Translator                          │
                        │                                                     │
  Agent action events ──►  Mode 1: Action-Correlated Reads                    │
  (purchase, reprice)   │    SELECT (correlated to write) → results discarded │──► TiDB
                        │    then INSERT/UPDATE                               │
                        │                                                     │
  Agent query requests ─►  Mode 2: Async Query Pipeline                       │
  (order_history, etc.) │    SELECT (templated) → reduce → domain answer      │──► TiDB
                        │    delivered to agent inbox (future tick)           │
                        │                                                     │
                        └─────────────────────────────────────────────────────┘
```

| Feature | Mode 1: Action-Correlated | Mode 2: Query Pipeline |
|---|---|---|
| **Purpose** | Hot-path transactional reads | Historical lookups, status checks, analytics |
| **Timing** | Synchronous with write | Async (arrival in future tick) |
| **Results used?** | Discarded by translator | Reduced to domain struct for agent |
| **Data accessed** | Current catalog, prices, inventory | Historical orders, shipments, aggregates |
| **DB test value** | Read-write transaction patterns | Read-After-Write isolation, secondary indexes |

### Reproducibility

Same random seed + same tick sequence = identical event stream. Critical for DB benchmarking. Inter-agent message delivery order within a tick is deterministic (sorted by sender ID).

---

## 4. Agent Subsystem

### Agent Intelligence Tiers

| Agent Type | Count | Intelligence Model | Rationale |
|---|---|---|---|
| **Consumer** | 100K–1M | Rule-based + statistical profiles + social influence | Volume matters. Demographics + noise + network effects. |
| **Seller** | 100–10K | Hybrid: rules for routine + occasional LLM for strategy | Pricing, marketing decisions. LLM only for strategic pivots. |
| **Supplier** | 50–5K | Rule-based + stochastic disruption injection | Production capacity, lead times, quality. |
| **Transport** | 10–500 | Discrete state machine | Routes, capacity, delays. Physics + queuing. |
| **Government** | 1 | Aggregate statistics + policy rules | Reads everything, computes statistics, updates market state. |

**Key insight**: Only ~0.1% of agents need LLM reasoning. The rest need behavioral diversity from varied parameter distributions.

### Agent Lifecycle

All agents inherit from `BaseAgent` and follow a common lifecycle:

1. **Inbox draining** — process Ch.2 messages and Ch.3 query results via dispatched handler methods
2. **Scheduled actions** — fire periodic `handle_{action}` methods based on `cycle_ticks` + jitter
3. **Event emission** — produce `ActionEvent`s containing writes, reads, messages, and queries

### Handler Method Patterns

```python
# Inbox handlers (Ch.2 messages)
def on_{msg_type}(self, payload: dict, from_agent: int, tick: int) -> list[ActionEvent]

# Query result handlers (Ch.3 responses)
def on_{template}_result(self, data: dict, context: dict, tick: int) -> list[ActionEvent]

# Scheduled actions
def handle_{action_name}(self, tick: int) -> list[ActionEvent]
```

### Government Agent — Special Responsibilities

The government agent has a unique dual role:

1. **As an agent**: receives messages (order reports, disruption reports), computes aggregate statistics via Ch.3 queries, writes results to its own tenant (`gov_records`, `statistics`)
2. **As a market updater**: after computing statistics, the government feeds aggregate indicators back to the market subsystem — updating price indices, supply/demand balances, and market conditions that all agents can observe

This feedback loop is the mechanism by which individual transactions collectively shape market conditions:

```
Agent transactions ──► Government observes ──► Government computes statistics
                                                        │
                                                        ▼
                                              Market state updated
                                              (price indices, S/D balance)
                                                        │
                                                        ▼
                                              Agents observe new market state
                                              (next tick decisions influenced)
```

### Sandbox Enforcement

Agents are sandboxed via `_sandbox.py` — an import blocker that prevents direct database access. **Forbidden modules**: `sqlite3`, `sqlalchemy`, `psycopg2`, `mysql`, `requests`, `urllib`, `http.client`, `smtplib`, `os`, `subprocess`, `socket`.

---

## 5. Market Subsystem

### Overview

Markets are **observable state containers** — passive data structures that aggregate supply, demand, and pricing information. Agents query markets for intelligence; agent transactions and government statistics update market state. Markets do not mediate transactions — agents transact directly via Ch.2 inter-agent messages.

### Architecture

```
bizsim/market.py                    # Facade: MarketFactory + interfaces
bizsim/markets/                     # Implementation directory
  __init__.py
  consumer_market.py                # B2C: SKU catalog, categories, pricing
  industrial_market.py              # B2B: parts, BOM, supplier mappings
  schema.py                         # Shared SQLite table definitions
```

The facade `bizsim/market.py` exposes:

- **`MarketFactory`** — creates and wires market instances from a shared SQLite database
- **`ConsumerMarket`** (Protocol) — interface for B2C operations: browse SKUs, get product details, query sellers for a SKU, query pricing
- **`IndustrialMarket`** (Protocol) — interface for B2B operations: query parts, look up BOM, find suppliers for a SKU, query supply chain topology

### Consumer Market (B2C)

The consumer market manages the product catalog that agents interact with:

- **SKU Catalog** — product attributes, categories, base prices, price bands
- **SKU-Seller Mapping** — which sellers carry which products, primary seller designation
- **Pricing Data** — current prices (observable by consumers and competing sellers)

Consumer and seller agents read from the consumer market to make purchasing and pricing decisions. The market itself doesn't execute transactions — it provides the information substrate.

### Industrial Market (B2B / Supply Chain)

The industrial market manages the supply side:

- **Parts Catalog** — raw materials and components with categories and unit costs
- **Bill of Materials (BOM)** — hierarchical composition of SKUs from parts across layers (L0 raw → L1 component → L2 assembly → L3 finished)
- **SKU-Supplier Mapping** — which suppliers produce which SKUs/parts, lead times, primary supplier designation

Supplier agents and seller agents query the industrial market to understand production capabilities, sourcing options, and supply chain topology.

### Shared Database, Modular Interface

Both markets share a single SQLite database (schema defined in `markets/schema.py`), but present independent interfaces:

```python
# bizsim/market.py

class ConsumerMarket(Protocol):
    def browse_skus(self, category: str | None = None, limit: int = 100) -> list[dict]: ...
    def get_sku(self, sku_id: int) -> dict | None: ...
    def get_sellers_for_sku(self, sku_id: int) -> list[dict]: ...
    def get_skus_for_seller(self, seller_id: int) -> list[dict]: ...

class IndustrialMarket(Protocol):
    def get_parts_for_supplier(self, supplier_id: int) -> list[dict]: ...
    def get_suppliers_for_sku(self, sku_id: int) -> list[dict]: ...
    def get_bom(self, sku_id: int) -> list[dict]: ...

class MarketFactory:
    """Creates market instances from a shared SQLite database."""
    def __init__(self, conn: sqlite3.Connection, tenant_id: int) -> None: ...
    def consumer_market(self) -> ConsumerMarket: ...
    def industrial_market(self) -> IndustrialMarket: ...
```

### Market State Updates

Market conditions (price indices, supply/demand balance) are updated by the government agent based on aggregate statistics computed from transaction data. This happens during the tick loop as part of the government aggregation step. Individual transactions don't mutate market state directly — the government acts as the statistical authority that synthesizes individual activity into macro-level market signals.

---

## 6. Society Subsystem

### Overview

The society subsystem models how information and influence spread among agents through social connections. It is an **engine-level subsystem** called during the tick loop — not an agent.

### Architecture

```
bizsim/social.py                    # Facade: access to community and media
bizsim/society/                     # Implementation directory
  __init__.py
  community.py                      # Social network + Independent Cascade propagation
  media.py                          # V2: broadcast media channels
```

The facade `bizsim/social.py` exposes:

- **`CommunitySubsystem`** — social network graph with influence propagation
- **`MediaSubsystem`** (V2) — public broadcast channels for agent-to-many influence

### Community (Social Network)

The community models peer-to-peer influence via a **weighted directed graph** with topic-specific edges, using the **Independent Cascade Model**:

1. A consumer purchases or reviews a product → **activates** on that category/topic
2. Each activated consumer has a probability of activating each neighbor (weighted by edge strength × topic affinity)
3. Propagation runs for K hops max per tick (configurable, default 3)
4. Activated consumers receive a **trend multiplier** boost for that category — increasing their purchase probability
5. Successful propagation strengthens the edge weight between source and target (reinforcement)
6. Trend multipliers decay over time toward baseline (mean reversion)

**DB workload impact**: Social propagation creates correlated purchase waves — many consumers buying the same product category within a few ticks. This produces hotspot contention on inventory rows and burst INSERT patterns on order tables.

**Configuration**:

```python
@dataclass
class CommunityConfig:
    k_max_hops: int = 3
    boost_increment: float = 0.3
    trend_max: float = 3.0
    decay_rate: float = 0.98
    edge_strengthen_delta: float = 0.01
    max_edge_weight: float = 0.5
    max_activations_per_tick: int = 10000
    initial_edge_weight_range: tuple[float, float] = (0.01, 0.5)
    avg_degree: int = 6
```

### Media (V2)

The media subsystem provides public broadcast channels where agents can publish messages that influence many other agents simultaneously — distinct from peer-to-peer community propagation. Examples:

- **Advertising** — sellers publish promotions that reach consumers beyond their social network
- **News** — events (supply disruptions, policy changes) are broadcast as public information
- **Reviews/Ratings** — aggregated product sentiment available to all consumers

Media creates a **one-to-many** influence pattern vs. community's **peer-to-peer** pattern. Together they model how real markets work: word-of-mouth (community) amplifies or dampens mass media signals.

**V2 scope** — not implemented in V1. The `bizsim/society/media.py` module is a placeholder.

---

## 7. Translator Subsystem

### Overview

The translator is a Go service that mediates all database access. Agents never write SQL; they emit domain patterns that the translator maps to SQL via a YAML operation catalog.

### What the Translator Encapsulates (Agents Must NOT Know)

- **Schema**: Table names, column names, indexes, partitioning strategy
- **Tenant mapping**: Which schema/database a tenant maps to, key prefixes, routing
- **SQL dialect**: TiDB-specific syntax, optimizer hints, batch sizes
- **Result cardinality**: The translator reduces potentially large result sets to O(1) domain metrics
- **Connection management**: Pools, timeouts, retries, read/write pool separation

### What the Translator Must NOT Do (Simulation's Responsibility)

- Agent decision logic (buy/sell/cancel)
- Simulation state management (agent memory, beliefs)
- Inter-agent communication (Channel 2 is invisible to the translator)
- Market state management
- Social influence computation

### Operation Catalog (P9)

All SQL lives in YAML catalog entries — one file per simulation domain:

```
go-translator/operations/
  store.yaml        ← check_inventory, insert_store_order, sales_analytics
  consumer.yaml     ← insert_consumer_order, order_history
  logistics.yaml    ← insert_shipment, shipment_tracking
  payment.yaml      ← insert_transaction
  government.yaml   ← insert_gov_record, gov_economic_indicators
  supplier.yaml     ← update_capacity, fulfillment_overdue
```

Each operation is one of three modes:

| Mode | Purpose | Example |
|---|---|---|
| `read` | Correlated SELECT inside action events (Mode 1) | `check_inventory` |
| `write` | INSERT/UPDATE inside action events | `insert_store_order` |
| `query` | Async query pipeline (Mode 2) with result reduction | `sales_analytics` |

```yaml
# Example: operations/store.yaml
domain: store
operations:
  - name: check_inventory
    mode: read
    params: { product_id: int }
    sql: "SELECT qty FROM {tenant}.inventory WHERE product_id = :product_id"
    returns: { qty: int }

  - name: insert_store_order
    mode: write
    params: { order_request_id: string, product_id: int, qty: int, price: decimal }
    sql: "INSERT INTO {tenant}.store_orders (...) VALUES (...)"

  - name: sales_analytics
    mode: query
    params: { seller_id: int, window: duration }
    sql: |
      SELECT product_id, SUM(qty), SUM(revenue) FROM {tenant}.store_orders
      WHERE seller_id = :seller_id AND created_at > NOW() - :window
      GROUP BY product_id ORDER BY revenue DESC
    reducer: aggregation_summary
    returns: { revenue: decimal, top_products: list, trend: string }

events:
  - name: store_accept_order
    requires: [check_inventory, insert_store_order, update_inventory]
```

### Standard Reducer Library

| Reducer | Input | Output | Used by |
|---|---|---|---|
| `single_row` | 1 row, N columns | `map[string]any` | shipment_tracking, fulfillment_overdue |
| `list_with_count` | N rows | `{items: [...], count: int}` | order_history |
| `aggregation_summary` | GROUP BY result | `{metrics: {...}, top_N: [...]}` | sales_analytics, gov_economic_indicators |
| `passthrough` | raw rows | `[]map[string]any` | debugging / ad-hoc |

---

## 8. Cross-Subsystem Interaction Model

### How Agents Use Markets

Agents receive a `MarketFactory` instance via dependency injection from the `TickEngine`. They call market interface methods to inform their decisions:

```python
# Consumer agent browsing products
skus = self.market.consumer_market().browse_skus(category="electronics", limit=20)

# Seller checking competitor prices
competitors = self.market.consumer_market().get_sellers_for_sku(sku_id=42)

# Supplier looking up BOM
bom = self.market.industrial_market().get_bom(sku_id=42)
```

Markets are read-only from the agent's perspective. Market state mutations happen through the government statistics feedback loop.

### How Agents Interact with Society

The community subsystem is called by the `TickEngine` during step 4 of the tick loop. Agents don't call the community directly — instead:

1. When a consumer purchases a product, their `ActionEvent` includes activation data (`SharePurchaseData`)
2. The engine collects activations and feeds them to the community subsystem
3. The community runs Independent Cascade propagation
4. Activated consumers receive trend multiplier boosts (mutated on the consumer agent objects)
5. The community emits `ActionEvent`s for edge weight updates (Ch.1 → translator → DB)

### Purchase Flow — Multi-Agent Causal Chain

The most important workload pattern. A single consumer purchase cascades across 4 agent types over 3–4 ticks:

```
Tick N:   Consumer decides to buy
          ├─► Ch.1: INSERT consumer_orders          (Consumer App tenant)
          └─► Ch.2: PlaceOrder → Store's inbox

Tick N+1: Store drains inbox, checks inventory, accepts order
          ├─► Ch.1: INSERT store_orders, UPDATE inventory  (Store tenant)
          ├─► Ch.2: OrderConfirmed → Consumer
          ├─► Ch.2: ShipRequest → Transport
          ├─► Ch.2: Charge → Payment
          └─► Ch.2: OrderReport → Government

Tick N+2: Transport: INSERT shipment, tracking     (Logistics tenant)
          Payment: INSERT transaction               (Payment Ledger tenant)
          Government: INSERT gov_record             (Analytics tenant)

Tick N+3: Consumer: UPDATE consumer_orders status   (Consumer App tenant)
          └─► Ch.2: SharePurchase → Community (triggers social propagation)
```

**DB test value**: 1 logical purchase → 13 SQL statements across 5 tenants over 4+ ticks. No cross-tenant transaction. Temporally staggered, causally dependent single-tenant writes.

### Supply Chain Disruption — Cascade Pattern

```
Tick N:   Supplier: UPDATE capacity=0               (Supplier ERP tenant)
          └─► Ch.2: SupplyDisruption → all downstream Stores

Tick N+1: Stores: UPDATE catalog, UPDATE pricing    (Store tenants)
          └─► Ch.2: DisruptionReport → Government

Tick N+2: Government: INSERT gov_record             (Analytics tenant)
          Government: update market conditions       (market subsystem)
```

### Seasonal/Viral Spike Pattern

A viral trend activates 1000 consumers → 1000 concurrent purchase chains → 1000 `PlaceOrder` messages to the same store in one tick → massive inventory contention at tick N+1. This is the most realistic hotspot stress test.

---

## 9. Architecture Principles

### P1: Two-Layer Architecture — Simulation ≠ Database Layer

The simulation and database are separated by a bidirectional domain boundary — the Workload Translator. Agents never see SQL, rows, or schema. TiDB never sees agent logic.

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            SIMULATION ENGINE                                        │
│                                                                                     │
│   Agent A ──── Ch.2: Inter-Agent Message ────► Agent B's inbox                      │
│      │                (intra-sim, no DB)           │                                │
│      │                                             │                                │
│      ▼                                             ▼                                │
│   Ch.1: Action Events                          Ch.1: Action Events                  │
│   (writes to OWN tenant)                       (writes to OWN tenant)               │
│      │                                             │                                │
│   Ch.3: Query Requests                         Ch.3: Query Requests                 │
│   (reads from OWN tenant)                      (reads from OWN tenant)              │
│      │         ▲                                   │         ▲                      │
└──────┼─────────┼───────────────────────────────────┼─────────┼──────────────────────┘
       │         │                                   │         │
       ▼         │ domain answers                    ▼         │ domain answers
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                          WORKLOAD TRANSLATOR                                         │
│     schema, tenant mapping, query templates, result reduction, connection mgmt       │
└──────────────────┬──────────────────────────────────────────────┬────────────────────┘
                   │ SQL                                          │ SQL
                   ▼                                              ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                                  TiDB                                                │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### P2: Tiered Agent Intelligence — Not Uniform

Only ~0.1% of agents need LLM reasoning. The rest need behavioral diversity from varied parameter distributions, not from AI. Budget: ~50–200 LLM calls per simulated day for strategic decisions.

### P3: Tick-Based Time with Variable Resolution

Discrete ticks with configurable tick duration (e.g., 1 tick = 1 simulated hour). Inter-agent messages have a natural 1-tick delivery delay, creating realistic temporal spread.

### P4: Multi-Tenancy — Tenant Write Sovereignty

**An agent only writes to tables owned by its own tenant. No exceptions.**

Cross-tenant effects happen via Ch.2 inter-agent messages. When Consumer wants to buy from Store, Consumer sends a `PlaceOrder` message. Store processes it next tick and writes to its *own* tables.

```
CORRECT:   Consumer → Ch.2: PlaceOrder → Store → INSERT store_003.store_orders  ✓
ANTI-PATTERN: Consumer → INSERT store_003.store_orders                          ✗
```

**Government Read Exception**: Government reads across all tenants via Ch.3 query pipeline. But writes only to its own tenant.

### P5: Domain-First Schema Design

Every table is owned by exactly one tenant type. The `orders` concept appears in multiple tenants with different semantics:

| Tenant | Tables Owned |
|---|---|
| **Consumer App** | `consumer_profiles`, `consumer_orders` (intents), `consumer_reviews` |
| **Individual Store** | `catalog`, `inventory`, `store_orders` (authoritative), `store_pricing`, `store_reviews` |
| **Supplier ERP** | `suppliers`, `supply_chain_edges`, `purchase_orders` |
| **Logistics Provider** | `shipments`, `tracking_events` |
| **Social Graph** | `community_posts`, `influence_edges` |
| **Payment Ledger** | `transactions` (double-entry bookkeeping) |
| **Government** | `gov_records`, `statistics` |

### P6: Workload Characterization

Each economic interaction produces a causal chain of single-tenant DB operations spread across multiple ticks. See §8 for the full purchase flow.

### P7: Temporal Realism

```python
effective_rate = (base_purchase_rate
    * HOURLY_CURVE[current_hour]       # peak at lunch, evening
    * WEEKLY_CURVE[current_day]        # weekend spike
    * SEASONAL_CURVE[current_month]    # holiday peaks
    * active_trends.boost_factor)      # viral moments from society subsystem
```

### P8: Dual-Mode Read Path

Mode 1 (action-correlated reads) + Mode 2 (async query pipeline). See §3 for details.

### P9: Operation Catalog — One Registry, Two Execution Modes

All SQL lives in YAML catalog entries. One catalog, three operation modes (read, write, query). See §7 for details.

---

## 10. Architectural Guardrails

These mechanisms make violations physically impossible, caught at compile/startup time, or caught by CI.

| Tier | Mechanism | Cannot be bypassed by editing... |
|---|---|---|
| **S — Physically impossible** | Go unexported fields/types, Python import blocker | Single file (requires coordinated multi-file edits caught by CI) |
| **A — Compile/startup time** | `NewExecutor` requires validated catalog; Go package layout blocks `database/sql` import | Application logic (type system rejects it) |
| **B — CI (external)** | grep checks in CI pipeline | Anything — CI is outside edit scope |
| **C — Test floor** | CI enforces minimum test counts | Any single test file (floor prevents silent deletion) |
| **D — Tests** | Unit + integration tests | Test files (weakest — last line of defense) |

### G1: P1 Boundary — Agents Cannot Touch SQL

- **Python**: Import blocker (`_sandbox.py`) + SQL keyword guard in `ActionEvent.__post_init__`
- **Go**: `*sql.DB` is unexported in executor; handler package has no `database/sql` import
- **CI**: grep checks for SQL imports in agent code + sandbox integrity verification

### G2: P4 Tenant Sovereignty — No Cross-Tenant Writes

- **Go**: Unforgeable `TenantScope` capability token with unexported constructor
- **Python**: `TenantContext` is frozen; `EventEmitter` has tenant baked in, no caller override
- **CI**: grep checks for raw `db.Query` calls outside executor

### G3: P9 Operation Catalog — No Ad-Hoc SQL in Go

- **Go**: executor's `run()` method is unexported; `NewExecutor` requires validated catalog
- **CI**: grep checks for `database/sql` and raw SQL calls outside executor

### G4: P9 Event Composition — Undeclared Events Rejected

- **Go**: `Catalog.Validate()` builds event whitelist; unknown events rejected at runtime
- **CI**: Event type consistency checks

### G5: Ch.2 Isolation — Inter-Agent Messages Never Cross the Translator

- **Structural**: `InterAgentMessage` is not a subclass of `ActionEvent`; no Go representation
- **CI**: grep checks for inter-agent message handling in Go code

### G6: Test Floor — Silent Test Deletion Prevention

- **CI**: minimum Python and Go test counts enforced; ratchets upward with codebase growth

---

## 11. Key Design Questions

### Q1: Primary Workload Metric

Optimize for **workload pattern diversity** first. A system producing 20 distinct, reproducible workload patterns is more valuable than one ultra-realistic pattern.

### Q2: Agent Count

For DB testing, concurrent database sessions matter more than simulated agents. Simulate 10K–100K consumers with detailed state. Scale DB workload independently by multiplying event rates.

### Q3: LLM Intelligence Value

| Domain | LLM Needed? | Why |
|---|---|---|
| Seller pricing strategy | **Yes** | Unpredictable UPDATE patterns, competitive cascades |
| Consumer trend emergence | **Yes** | Bursty, correlated READ patterns |
| Individual purchase decisions | **No** | Probability model sufficient, 10,000x cheaper |
| Logistics routing | **No** | Deterministic algorithms |
| Government statistics | **No** | Pure aggregation |

### Q4: Social Influence Mechanics

Independent Cascade Model on a weighted directed graph with topic-specific edges. Creates correlated SELECT bursts (hotspot) → INSERT order waves (write burst).

### Q5: Supply Chain Topology

Layered DAG: Raw materials (L0) → Components (L1) → Assemblies (L2) → Products (L3) → Sellers (L4). Each edge: capacity, lead_time, cost, reliability. Creates cross-tenant JOIN patterns and cascading UPDATE storms during disruptions.

### Q6: Reproducibility

Same config + same seed = same event stream = same DB workload. LLM calls cached by input hash or recorded in event stream for replay without LLM.

### Q7: Entity-Specific DB Operation Patterns

| Entity | OLTP Pattern | OLAP Pattern | Contention Profile |
|---|---|---|---|
| Consumer | Point reads, single-row inserts | — | Low (distributed) |
| Seller | Inventory updates (hot rows), order inserts | Sales reports | **High** (popular products) |
| Supplier | Batch production updates | Capacity planning queries | Medium |
| Transport | Append-only tracking events | Route analytics | Low |
| Government | — | Heavy aggregation, full scans | **Massive read load** |

---

## 12. Tension Analysis: Simulation Fidelity vs. Workload Predictability

### The Spectrum

```
Pure benchmark (TPC-C)                              Pure simulation (AgentSociety)
├── Fully deterministic                              ├── Emergent, unpredictable
├── Statistically characterized                      ├── Behaviorally rich
├── Reproducible by construction                     ├── Reproducible only via replay
└── Boring, uniform patterns                         └── Realistic, diverse patterns
```

### Resolution: Three Modes

**Mode 1 — Controlled Scenarios** (regression testing, benchmarking):
- Pre-defined event sequences: "Black Friday" (10x spike), "Supply chain disruption" (cascade), "New market entrant" (aggressive pricing)
- Parameterized, fully reproducible, statistically characterizable

**Mode 2 — Free Simulation** (chaos testing, discovering unknowns):
- Full agent autonomy, LLM-driven strategic decisions
- Social influence creates emergent patterns
- If interesting pattern found → extract into a Mode 1 scenario

**Mode 3 — Hybrid** (practical default):
- Rule-based baseline + stochastic perturbations + occasional LLM shifts + scheduled scenario injections

### Key Insight

The simulation doesn't need to be predictable — the **event stream** needs to be **replayable**:

```
Simulation (non-deterministic) → Event Stream (recorded) → Replay (deterministic)
```

---

## 13. Capacity Planning

### Per-Agent Database Operation Profiles

| Agent Type | DB Ops/Tick | Operation Breakdown | Avg SQL Stmts/Op |
|---|---|---|---|
| Consumer | 1.5 | 60% browse, 25% purchase, 15% idle | 1.4 |
| Seller | 1.8 | 40% process orders, 30% reprice, 30% idle | 1.5 |
| Supplier | 0.8 | 40% batch update, 60% idle | 2.0 |
| Transport | 2.0 | 80% shipment creation, 20% status check | 1.8 |
| Government | 0.5 | 30% agg query, 20% record, 50% idle | 0.5 |

**Per-agent weighted average**: ~1.43 SQL stmts per agent per tick.

### Scenario 1: Single Node Dev — 50K Agents

| Component | Value |
|---|---|
| **Agents** | 50,000 (25K consumer, 10K seller, 5K supplier, 5K transport, 5K gov) |
| **Sim memory** | ~830 MB |
| **Tick rate** | 0.1 ticks/sec (DB-constrained) |
| **Sustained QPS** | ~7,000 |
| **Connections** | ~40 |
| **Hardware** | MacBook M2 Max or 1 × c7g.2xlarge |
| **DB** | TiDB Essential (~4 vCPU equiv) |
| **Cost** | $50–310/month |

### Scenario 2: Full Scale — 500K QPS / 1M Tables

| Component | Value |
|---|---|
| **Total agents** | ~2.5M across 620 tenants |
| **Active agents** | ~860K (100 active tenants) |
| **Sim cluster** | 10 × c7g.4xlarge (all identical, no coordinator) |
| **Per-node QPS** | ~53K |
| **Per-node connections** | ~107 (75 write + 32 read) |
| **Total connections** | ~1,070 (< 4,000 limit) |
| **TiDB Premium** | 18 TiDB nodes + 24 TiKV nodes + 3 PD nodes |
| **Sustained QPS** | ~529K blended |
| **Tables** | ~1,000,000 |
| **Data volume** | ~17.5 TB |
| **Cost** | $21K–46K/month |

### Scaling Model

Every simulation node is identical and fully self-contained. No centralized coordinator, no shared state. Adding capacity = start another identical node with fresh tenants.

```
Want 250K QPS?  → 5 nodes
Want 500K QPS?  → 10 nodes
Want 750K QPS?  → 15 nodes (add 5 nodes, zero changes to existing)
```

### Bottleneck Analysis

| Rank | Scenario 1 | Scenario 2 |
|---|---|---|
| 1 | TiDB Essential QPS/RU budget | TiKV write throughput |
| 2 | Storage (5 GiB free burns in ~1.5 hr) | PD region scheduling (1.1M regions) |
| 3 | Mesa single-thread (not hit at 0.1 t/s) | TiDB connection headroom |
| 4 | — | Per-node CPU saturation (~88%) |

---

## Tech Stack

| Layer | Language | Rationale |
|---|---|---|
| Simulation Engine | Python | Agent ecosystem, rapid iteration |
| Event Stream | Local Log | Protobuf events, ordered, replayable |
| Workload Translator | Go | TiDB compatibility, performance |
| Database Driver | Go | Leverage go-tpc patterns, TiDB libs |
| LLM Integration | Python | Async, with response caching |
| Configuration | YAML + CLI | Scenario definitions |
| Orchestration | Docker/K8s | Dev compose, scale on K8s |

---

## Watch Out For

- **Scope creep toward economic realism**: Every simulation feature must justify itself by the DB workload patterns it produces. If a feature doesn't create interesting DB operations, cut it.
- **LLM cost explosion**: At $0.01/call, 1000 calls/tick × 10,000 ticks = $100K/run. Budget ruthlessly. Cache aggressively. Default to rule-based.
- **The "demo trap"**: Resist visualization before the event-stream-to-SQL pipeline works end-to-end.
- **Feedback amplification**: Agent sees late order → cancels → cascade. Mitigated by cooldown rate-limiters + probabilistic decisions.
- **Market state staleness is a feature**: Market data is always slightly stale (government updates every N ticks). This mirrors real markets and prevents tight feedback loops.

---

## Appendix A: Key Researchers & Labs

| Researcher / Lab | Affiliation | Focus |
|---|---|---|
| Joon Sung Park | Stanford HCI | Generative Agents architecture |
| Percy Liang | Stanford CRFM | Foundation model evaluation/safety |
| Tsinghua FIB-Lab | Tsinghua University | Large-scale urban + economic simulation |
| CAMEL-AI | Multi-institutional | OASIS, multi-agent coordination |
| Microsoft Research | Microsoft | CompeteAI, MarS, Magentic-Marketplace |
| Salesforce Research | Salesforce | AI Economist (RL economic policy) |

---

## Appendix B: Landscape

### Agent-Based Economic Simulation Frameworks

| Project | Key Strength | Relevance |
|---|---|---|
| **Mesa** | Industry-standard Python ABM framework | Core building block |
| **abcEconomics** | Double-entry bookkeeping, economic domain abstractions | Architecture reference |
| **AI Economist** (Salesforce) | RL-based economic policy optimization | Government agent inspiration |
| **ASSUME** | Market mechanism design and actor behavior evolution | Market mechanism patterns |

### LLM-Driven Economic Agent Research

| Project/Paper | Key Innovation |
|---|---|
| **EconAgent** (Tsinghua) | LLM agents for macroeconomic activities |
| **CompeteAI** (Microsoft) | LLM agents in market competition scenarios |
| **MarS** (Microsoft) | Financial market simulation via Generative Foundation Models |

### Social Simulation & Influence Propagation

| Project | Key Strength |
|---|---|
| **Stanford Generative Agents** | Memory/reflection/planning architecture |
| **AgentSociety** (Tsinghua) | Large-scale (up to 1M agents) urban social simulation |
| **OASIS** (CAMEL-AI) | 1M agent social interaction sim |

### Supply Chain & Logistics Simulation

| Project | Key Strength |
|---|---|
| **SimPy** | Gold standard process-based discrete event simulation |
| **GreaterWMS** | Production WMS, real inventory/supplier structures |
| **Amazon supply-chain-sim** | Enterprise-grade supply chain simulation |

### Database Benchmarks & Workload Generators

| Project | Key Strength |
|---|---|
| **TPC-C/E/DS** | Standard OLTP/brokerage/decision support benchmarks |
| **go-tpc** | TiDB's Go implementation of TPC-C and TPC-H |
| **RetailSynth** | Synthetic retail transactions from agent-based shopper models |
| **HammerDB** | Database load testing with TPC-C/TPC-H support |

---

*Document version: V2*
*Date: 2026-03-31*
