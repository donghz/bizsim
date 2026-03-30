# BizSim: Economic Ecosystem Simulation for Distributed Database Testing

## Vision & Architecture Analysis

> **One-sentence pitch**: A coherent economic ecosystem simulation that generates naturally diverse, temporally realistic, cross-tenant database workloads — bridging the gap between synthetic benchmarks and production traffic patterns.

---

## Table of Contents

1. [Vision](#1-vision)
2. [Gap Analysis: Why Build This](#2-gap-analysis-why-build-this)
3. [Architecture Principles](#3-architecture-principles)
4. [Key Design Questions](#4-key-design-questions)
5. [Tension Analysis: Simulation Fidelity vs. Workload Predictability](#5-tension-analysis-simulation-fidelity-vs-workload-predictability)
6. [Building Block Assessment](#6-building-block-assessment)
7. [Recommended Tech Stack](#7-recommended-tech-stack)
8. [Roadmap Sketch](#8-roadmap-sketch)
9. [Capacity Planning](#9-capacity-planning)
- [Appendix A: Key Researchers & Labs](#appendix-a-key-researchers--labs)
- [Appendix B: Landscape — Existing Open Source Projects & Research](#appendix-b-landscape--existing-open-source-projects--research)

---

## 1. Vision

An economic ecosystem simulation comprising:

- **Market** — sellers (e-commerce stores) and buyers (consumers)
- **Supply side** — each seller has a group of suppliers (producers/factories), each supplier has a supply chain network
- **Logistics** — transportation providers for goods transport
- **Social layer** — consumer communities where fashion trends and news propagate, driving demand shifts
- **Government** — entity that tracks every citizen and firm, producing statistics about traffic, flow of goods, and money

**The original purpose**: build a large and diverse testing system for a **multi-tenant distributed database** like TiDB. The simulation is a *means* to generate realistic, heterogeneous database workloads — not an economics research platform.

### BizSim Unit World — Entity & Tenant Relation Diagram

A single BizSim "unit world" is one self-contained economic ecosystem. Each simulation node runs one or more unit worlds. The diagram below shows the entity structure, ownership relationships, interaction flows, and how they map to DB tenants.

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        BIZSIM UNIT WORLD                                  │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                    MARKETPLACE (Platform Tenant)                    │  │
│  │                                                                     │  │
│  │  ┌─────────┐   ┌─────────┐   ┌─────────┐          ┌─────────┐       │  │
│  │  │ Store A │   │ Store B │   │ Store C │  . . .   │ Store N │       │  │
│  │  │ (Seller │   │ (Seller │   │ (Seller │          │ (Seller │       │  │
│  │  │ Tenant) │   │ Tenant) │   │ Tenant) │          │ Tenant) │       │  │
│  │  └────┬────┘   └────┬────┘   └────┬────┘          └────┬────┘       │  │
│  │       │             │             │                    │            │  │
│  └───────┼─────────────┼─────────────┼────────────────────┼────────────┘  │
│          │ catalog,    │             │                    │               │
│          │ inventory,  │             │                    │               │
│          │ pricing     │             │                    │               │
│          ▼             ▼             ▼                    ▼               │
│  ┌─────────────────────────────────────────────────────────────────┐      │
│  │                    PRODUCTS                                     │      │
│  │  (attributes, categories, prices, reviews)                      │      │
│  └─────────────┬─────────────────────────────────┬─────────────────┘      │
│                │ sourced from                    │ browsed/purchased by   │
│                ▼                                 ▼                        │
│  ┌──────────────────────────┐    ┌─────────────────────────────────┐      │
│  │   SUPPLY CHAIN           │    │         CONSUMERS               │      │
│  │   (Supplier ERP Tenants) │    │    (Consumer App Tenant)        │      │
│  │                          │    │                                 │      │
│  │  Raw Mat.  Components    │    │   ┌──────┐ ┌──────┐ ┌──────┐    │      │
│  │  (L0) ──→ (L1) ──→       │    │   │ C_1  │ │ C_2  │ │ C_N  │    │      │
│  │  Assemblies (L2) ──→     │    │   └──┬───┘ └───┬──┘ └───┬──┘    │      │
│  │  Finished Goods (L3) ──→ │    │      │         │        │       │      │
│  │          │               │    │      │influence│        │       │      │
│  │  ┌───────┴───────┐       │    │      ▼         ▼        ▼       │      │
│  │  │ Supplier_1    │       │    │  ┌───────────────────────────┐  │      │
│  │  │ Supplier_2    │       │    │  │     COMMUNITIES           │  │      │
│  │  │   ...         │       │    │  │  (Social Graph Tenant)    │  │      │
│  │  │ Supplier_M    │       │    │  │                           │  │      │
│  │  └───────────────┘       │    │  │  trends, reviews, fashion │  │      │
│  │    capacity, lead_time,  │    │  │  news propagation         │  │      │
│  │    reliability, cost     │    │  └───────────────────────────┘  │      │
│  └───────────┬──────────────┘    └───────────────┬─────────────────┘      │
│              │ ships via                         │ purchases trigger      │
│              ▼                                   ▼                        │
│  ┌──────────────────────────┐    ┌─────────────────────────────────┐      │
│  │   TRANSPORT PROVIDERS    │    │      PURCHASE CAUSAL CHAIN      │      │
│  │   (Logistics Tenant)     │    │    (via inter-agent messages)   │      │
│  │                          │    │                                 │      │
│  │  Carrier_1, Carrier_2 ...│    │  consumer_orders → store_orders │      │
│  │  routes, capacity, ETAs  │    │       → shipment creation       │      │
│  │  tracking events (append)│    │       → payment (debit/credit)  │      │
│  └──────────────────────────┘    │       → gov statistics          │      │
│                                  │  (each write in own tenant,     │      │
│                                  │   spread across 3-4 ticks)      │      │
│          ▲                       └─────────────────────────────────┘      │
│          │ observes all                                                   │
│  ┌───────┴─────────────────────────────────────────────────────────┐      │
│  │                    GOVERNMENT                                   │      │
│  │                    (Analytics Tenant)                           │      │
│  │                                                                 │      │
│  │  tracks: citizens, firms, goods flow, money flow, traffic       │      │
│  │  produces: statistics, policy changes, regulatory events        │      │
│  │  access pattern: read-heavy aggregation, full scans             │      │
│  └─────────────────────────────────────────────────────────────────┘      │
└───────────────────────────────────────────────────────────────────────────┘
```
**Tenant mapping summary** — each entity group maps to a distinct DB tenanttype:

| Entity Group     | DB Tenant Type      | Access Pattern       | Key Tables                          |
|------------------|---------------------|----------------------|-------------------------------------|
| Marketplace      | Shared-schema       | Mixed read/write     | products, categories                |
| Individual Store | Per-store schema/DB | Inventory hotspot    | store_orders, inventory, catalog    |
| Supply Chain     | Per-supplier-group  | Batch updates        | suppliers, supply_chain_edges       |
| Consumer App     | Community platform  | High-write social    | consumer_orders, consumer_profiles  |
| Communities      | Social graph        | Graph traversal      | community_posts, influence_edges    |
| Transport        | Logistics provider  | Append-heavy         | shipments, tracking_events          |
| Government       | Analytics           | Read-heavy agg       | gov_records, statistics             |
| Payments         | Financial ledger    | Strict transactional | transactions (double-entry)         |

**Cross-tenant interaction flow** — a single consumer purchase cascades across tenants **via inter-agent messages**, not direct writes. Each agent only writes to its own tenant's tables (see P4: Tenant Write Sovereignty):

```
Tick N:   Consumer decides to buy
          │
          ├─► ActionEvent: INSERT into consumer_orders      (Consumer App tenant — own table)
          └─► Message → Store: PlaceOrder(product, qty)

Tick N+1: Store drains inbox, checks inventory, accepts order
          │
           ├─► ActionEvent: INSERT store_orders, UPDATE inventory   (Store tenant — own tables)
          ├─► Message → Consumer: OrderConfirmed(order_id)
          ├─► Message → Transport: ShipRequest(order_id, dest)
          ├─► Message → Payment: Charge(amount, consumer_id)
          └─► Message → Government: OrderReport(...)

Tick N+2: Transport creates shipment   → INSERT shipment         (Logistics tenant)
          Payment settles              → INSERT transaction      (Payment Ledger tenant)
          Government records           → INSERT gov_record       (Analytics tenant)
          Consumer gets confirmation   → updates local state     (no DB write)

Tick N+3: Community propagation        → UPDATE influence_edges  (Social Graph tenant)
```

**Key difference from the old model**: Instead of one atomic cross-tenant transaction, a purchase produces a **causal chain** of single-tenant writes spread across 3–4 ticks. Each tick's writes hit a different tenant's tables. This is how real e-commerce works (order → fulfillment → shipping → payment settlement) and creates far more interesting DB test patterns:

- **Temporal spread**: Cross-tenant operations are naturally staggered, not artificially synchronized
- **Causal consistency testing**: Transport writes depend on store writes from a prior tick
- **Rejection paths**: Store can reject (out of stock), creating branching write patterns
- **No cross-tenant transactions**: Each write is a single-tenant transaction — exactly the pattern multi-tenant DBs are optimized for

---

## 2. Gap Analysis: Why Build This

**No existing system combines all five of these:**

| Capability | TPC Benchmarks | Economic Sims (Mesa/ABCE) | Social Sims (AgentSociety) | DB Load Generators (HammerDB) | **BizSim** |
|------------|:-:|:-:|:-:|:-:|:-:|
| Rich economic ecosystem | ◐ (simplified) | ✓ | ✗ | ✗ | ✓ |
| Multi-entity types (consumer, seller, supplier, logistics, gov) | ◐ (TPC-E has some) | ◐ | ◐ | ✗ | ✓ |
| Social influence propagation | ✗ | ✗ | ✓ | ✗ | ✓ |
| Supply chain networks | ✗ | ◐ | ✗ | ✗ | ✓ |
| Database workload as primary output | ✓ | ✗ | ✗ | ✓ | ✓ |
| Multi-tenant awareness | ✗ | ✗ | ✗ | ✗ | ✓ |
| Temporally realistic patterns | ✗ (uniform) | ◐ | ◐ | ✗ (uniform) | ✓ |
| Cross-tenant correlated operations | ✗ | ✗ | ✗ | ✗ | ✓ |

**The unique value**: Naturally heterogeneous multi-tenant workloads from a single coherent simulation. A consumer purchase triggers a causal chain of single-tenant writes — store accepts order (store tenant, tick N+1), transport creates shipment (logistics tenant, tick N+2), payment settles (payment tenant, tick N+2) — spread across ticks via inter-agent messages. These temporally staggered cross-tenant correlations are exactly what distributed databases struggle with and no synthetic benchmark captures.

---

## 3. Architecture Principles

### P1: Two-Layer Architecture — Simulation ≠ Database Layer

The simulation and database are separated by a **bidirectional domain boundary** — the Workload Translator. Agents never see SQL, rows, or schema. TiDB never sees agent logic. The translator speaks both languages. Within the simulation, agents communicate via **inter-agent messages** — an intra-simulation channel that never touches the DB.

#### Three Communication Channels

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

| Channel | Direction | What flows | Crosses translator? | Touches DB? |
|---------|-----------|------------|---------------------|-------------|
| **Ch.1: Action Events** | Agent → Translator → TiDB | Domain events (`order_accepted`, `shipment_created`) | Yes — translated to SQL | Yes — INSERT/UPDATE to agent's **own** tenant |
| **Ch.2: Inter-Agent Messages** | Agent → Agent (via inbox) | Domain requests (`PlaceOrder`, `ShipRequest`, `Charge`) | **No** — stays inside simulation | **No** — pure in-memory |
| **Ch.3: Query Requests** | Agent → Translator → TiDB → Agent | Domain questions + reduced answers | Yes — translated to SQL, results reduced | Yes — SELECT from agent's **own** tenant |

**Channel 2 is new and critical.** It enables the Tenant Write Sovereignty rule (P4): when Consumer wants to buy from Store, it sends an inter-agent message. Store processes it next tick, decides accept/reject, and writes to its *own* tables via Channel 1. No agent ever writes to another tenant's tables.

Channel 2 messages are **local in-memory** — they are Python objects appended to a target agent's inbox `deque`. They do not cross the translator boundary, do not generate SQL, and do not touch TiDB. They are intra-simulation coordination, invisible to the DB layer.

#### The Bidirectional DB Contract (Channels 1 & 3)

The translator mediates **two DB-facing data flows**, and in both directions it translates between domain concepts and SQL:

**Outbound — Ch.1 (agent → DB)**: Agents emit domain events (`order_accepted`, `seller_reprices`). The translator maps each event to SQL statements — schema-aware, tenant-aware, with correlated reads and transaction boundaries. Each event targets only the emitting agent's own tenant. The event stream is the outbound contract and the system's primary artifact. It is ordered, replayable, and DB-agnostic.

**Inbound — Ch.3 (DB → agent)**: Agents request domain answers (`"what are my recent orders?"`, `"what's the unemployment rate?"`). The translator turns these into SQL queries, executes them against TiDB, and **reduces** the result set to a small, fixed-size domain answer. Raw rows never cross the boundary. The agent receives a struct like `{overdue_count: 3, worst_delay_days: 12}`, not 10,000 rows from a GROUP BY.

#### What the Translator Encapsulates (agents must NOT know)

- **Schema**: Table names, column names, indexes, partitioning strategy
- **Tenant mapping**: Which schema/database a tenant maps to, key prefixes, routing
- **SQL dialect**: TiDB-specific syntax, optimizer hints, batch sizes
- **Result cardinality**: A query may scan 100K rows — the translator reduces it to O(1) domain metrics before returning
- **Connection management**: Pools, timeouts, retries, read/write pool separation

#### What the Translator Must NOT Do (simulation's responsibility)

- Agent decision logic (buy/sell/cancel)
- Simulation state management (agent memory, beliefs)
- Inter-agent communication (Channel 2 is invisible to the translator)
- Interpreting what the domain answer *means* — it computes `unemployment_rate: 0.04`, the government agent decides whether that's alarming

#### Interface Granularity

The translator exposes a **template registry** — a fixed set of named operations, each with typed parameters in and a typed domain struct out (see P9 for the unified operation catalog that formalizes this into a data-driven, extensible design):

| Template                | Agent sends (params)     | Translator returns (domain struct)              |
|-------------------------|--------------------------|-------------------------------------------------|
| order_history           | {consumer_id, window}    | {orders: [{id, status, is_late}], count}        |
| shipment_tracking       | {order_id}               | {status, eta, is_delayed, last_location}        |
| sales_analytics         | {seller_id, window}      | {revenue, top_products, trend}                  |
| gov_economic_indicators | {period}                 | {gdp, unemployment, inflation, trade_balance}   |
| order_accepted          | {order_id, product, qty} | (write-only — no return value)                  |

Agents pick a template name and fill in parameters. They never construct queries. The translator owns the full SQL lifecycle: generation → execution → reduction → domain answer. This is the same pattern as a well-designed API layer in a real application — which is exactly the DB access pattern we want to test.

#### Why This Matters

- **Swap simulation models** without touching DB code — both layers only know their side of the contract
- **Replay** the same event stream against different DB configurations — the outbound log is the artifact
- **Test the translator independently** — feed it synthetic events, verify SQL output
- **DB pressure is decoupled from IPC cost** — a government census query scans 100K rows in TiDB (full analytical pressure), but only 200 bytes cross the IPC boundary back to Python
- **Inter-agent messages are free** — Channel 2 is pure in-memory; it adds zero DB load, zero IPC cost, and zero latency within a tick
- **Dual-mode read path** (see P8 for implementation details): Mode 1 fires correlated SELECTs alongside writes — results are consumed by the translator and discarded. Mode 2 runs an async query pipeline — agents request domain answers, translator executes, reduces, and delivers to the agent's inbox next tick

### P2: Tiered Agent Intelligence — Not Uniform

The single biggest trap: thinking all agents need LLM-level intelligence. They don't.

| Agent Type | Count | Intelligence Model | Rationale |
|------------|-------|-------------------|-----------|
| Consumers | 100K–1M | **Rule-based** + statistical profiles + social influence | Volume matters. Use demographics + noise + network effects. |
| Sellers (stores) | 100–10K | **Hybrid**: rules for routine + occasional LLM for strategy | Pricing, marketing decisions. LLM only for strategic pivots. |
| Suppliers | 50–5K | **Rule-based** + stochastic disruption injection | Production capacity, lead times, quality. Disruptions are random events. |
| Transport | 10–500 | **Discrete event / queue-based** (SimPy) | Routes, capacity, delays. No "intelligence" needed — logistics is physics + queuing. |
| Government | 1 | **Aggregate statistics** + policy rules | Reads everything, writes policy changes. Pure computation. |
| Community influence | — | **Graph diffusion model** | Not an "agent" — a propagation mechanism on a network topology. |

**Key insight**: Only ~0.1% of agents need LLM reasoning. The rest need **behavioral diversity** from varied parameter distributions, not from AI.

### P3: Tick-Based Time with Variable Resolution

Use **discrete ticks** with configurable tick duration (e.g., 1 tick = 1 simulated hour):

```
Per tick:
  0. Drain inboxes — each agent processes inter-agent messages (Ch.2) and
     query results (Ch.3) that arrived since last tick
  1. Process external events (disruptions, policy changes, trend injections)
  2. Run agent decision cycles (consumers browse/buy, sellers reprice, suppliers produce)
     — decisions may be influenced by inbox contents from step 0
  3. Advance transport/logistics state machines
  4. Compute community influence propagation (batched)
  5. Government aggregation (every N ticks)
  6. Emit action events (Ch.1) and inter-agent messages (Ch.2) to the event stream
     — Ch.1 events go to the Go translator for DB writes
     — Ch.2 messages are appended to target agents' inboxes (available next tick)
     — Ch.3 query requests go to the Go translator for async DB reads
```

**Step 0 is critical for Tenant Write Sovereignty.** When Consumer sends a `PlaceOrder` message at tick N, Store receives it at tick N+1 step 0. Store decides accept/reject in step 2, then emits its own action events and messages in step 6. This means a purchase spans 3–4 ticks (see §1 cross-tenant interaction flow). The tick delay is not overhead — it's the model of how real async business processes work.

**Why tick-based over discrete-event (SimPy-style)**:
- Discrete-event is elegant for supply chain but hard to synchronize social propagation + market clearing + government observation
- Tick-based gives natural batching for DB workload (one tick = one burst of operations)
- Variable resolution: hourly for normal, daily for fast-forward, minute-level for stress
- Inter-agent messages have a natural 1-tick delivery delay, creating realistic temporal spread of cross-tenant writes

**Reproducibility**: Same random seed + same tick sequence = identical event stream. Critical for DB benchmarking. Inter-agent message delivery order within a tick is deterministic (sorted by sender ID).

### P4: Multi-Tenancy Mapping — Simulation Structure IS Tenant Structure

The economic ecosystem **naturally maps** to multi-tenant schemas:

| Tenant Type          | Simulation Entity    | DB Access Pattern             | Writes to own tables only          |
|----------------------|----------------------|-------------------------------|------------------------------------|
| E-commerce platform  | Marketplace          | Shared-schema multi-tenant    | ✓ catalog, product listings        |
| Individual store     | Seller               | Per-tenant schema/database    | ✓ store_orders, inventory          |
| Logistics provider   | Transport company    | Separate tenant, append-heavy | ✓ shipments, tracking              |
| Government/analytics | Government entity    | Read-heavy analytical         | ✓ gov_records, statistics          |
| Consumer app         | Community platform   | High-write social             | ✓ consumer_orders, preferences     |
| Supplier ERP         | Supplier group       | Mixed OLTP                    | ✓ capacity, purchase_orders        |
| Payment ledger       | Financial service    | Strict transactional          | ✓ transactions (double-entry)      |

Each tenant has **different access patterns** — this is the genuine value. You get **naturally heterogeneous multi-tenant workloads** from a single coherent simulation.

#### Tenant Write Sovereignty

**Rule: An agent only writes to tables owned by its own tenant. No exceptions.**

Cross-tenant effects happen via **inter-agent messages** (Channel 2 in P1). When a consumer wants to buy from a store, the consumer sends a `PlaceOrder` message. The store agent processes it in the next tick, decides accept/reject, and writes to its *own* inventory and order tables. The consumer never touches the store's tables.

This is not just architectural purity — it's the **correct DB workload pattern**:

- **Real multi-tenant applications work this way**: Shopify doesn't let Customer Service write directly to a merchant's inventory table. They call the merchant's API, which writes to the merchant's DB.
- **Cross-tenant transactions are the wrong test**: Multi-tenant databases are optimized for single-tenant transactions. Cross-tenant distributed transactions are a pathological case, not the common one. BizSim should test what real apps do, not what they avoid.
- **Rejection creates workload diversity**: When Store rejects an order (out of stock), the write pattern differs from acceptance. Two consumers buying the last item → one gets rejected. This creates branching write patterns that synthetic benchmarks cannot produce.
- **Temporal spread is realistic**: A purchase produces single-tenant writes across 3–4 ticks (store → transport → payment → government), not one atomic burst. This tests how TiDB handles causally dependent but temporally staggered operations across tenant boundaries.

```
ANTI-PATTERN (violates sovereignty):
  Consumer agent → INSERT INTO store_003.store_orders (...)     ✗ Writing to store's tenant!

CORRECT PATTERN:
  Consumer agent → Message(to=store_003, PlaceOrder(...)) → Channel 2 (in-memory)
  Store agent    → INSERT INTO store_003.store_orders (...)     ✓ Writing to own tenant
```

#### Government: Read Sovereignty Exception

Government agents need to **read** across all tenants (analytical queries, census, statistics). This is allowed — they read via Channel 3 (query pipeline through the translator), which generates realistic analytical read pressure on TiDB. But government **writes** only to its own tenant tables (`gov_records`, `statistics`). Government never modifies another tenant's data.

### P5: Domain-First Schema Design

Under Tenant Write Sovereignty (P4), every table is **owned by exactly one tenant type**. No table is shared. The `orders` concept appears in multiple tenants with different semantics — the consumer records a purchase intent, the store records the authoritative order.

```
Tenant: Consumer App (per community or global)
├── consumer_profiles (demographics, wallet, preferences, community_id)
├── consumer_orders   (purchase intents — consumer's local record of what they asked to buy)
│                     Written by: Consumer agent.  Status: requested → confirmed → delivered
│                     Confirmed/rejected status arrives via Ch.2 message from Store.
└── consumer_reviews  (product reviews written by consumers)

Tenant: Individual Store (per-store schema/DB)
├── catalog           (product attributes, descriptions, images)
├── inventory         (product_id, qty_available — the authoritative stock record)
├── store_orders      (authoritative orders — store decides accept/reject)
│                     Written by: Store agent upon receiving PlaceOrder message.
│                     This is the source of truth for order status and fulfillment.
├── store_pricing     (current prices, discounts, competitive adjustments)
└── store_reviews     (aggregated review metrics per product — written by store's own jobs)

Tenant: Supplier ERP (per-supplier-group)
├── suppliers         (capacity, lead_time, reliability_score, cost)
├── supply_chain_edges (supplier→supplier, supplier→seller linkage)
└── purchase_orders   (supplier's inbound orders from stores — raw material/component orders)

Tenant: Logistics Provider (per-carrier or shared)
├── shipments         (origin, destination, carrier, status, ETA)
└── tracking_events   (append-only tracking log — scanned, in_transit, delivered)

Tenant: Social Graph (per-community or global)
├── community_posts   (author, content_hash, trend_tags, timestamp)
└── influence_edges   (consumer→consumer, weight, topic — social graph structure)

Tenant: Payment Ledger (financial service)
└── transactions      (debit/credit double-entry bookkeeping — immutable append-only)

Tenant: Government / Analytics
├── gov_records       (entity_type, entity_id, period, metrics_json)
└── statistics        (aggregated indicators — GDP, unemployment, trade_balance)
```

**Key design decision**: `consumer_orders` ≠ `store_orders`. The consumer records "I want to buy X" in their own tenant. The store records "I accepted/rejected order for X" in its own tenant. The two records are linked by an `order_request_id` carried in the Ch.2 `PlaceOrder` message. This dual-record pattern:

- Preserves Tenant Write Sovereignty (each agent writes only to own tables)
- Creates interesting Read-After-Write patterns (consumer queries own order status, store queries own inventory)
- Models how real e-commerce works (Shopify merchant has their own order table, distinct from the customer's purchase history)
- Doubles the write diversity for DB testing (two INSERTs in different tenants from one logical purchase)

```
Deliberate Complexity for DB Testing:
├── Secondary indexes on (seller_id, created_at)    → range scan patterns
├── Global indexes on (product_category)             → cross-tenant queries
├── JSON columns in gov_records                      → schema flexibility testing
├── Time-partitioned store_orders/shipments          → partition pruning tests
├── order_request_id linking consumer_orders ↔ store_orders → cross-tenant JOIN patterns
└── Double-entry transactions                        → strict consistency testing
```

### P6: Workload Characterization — Every Event Maps to DB Operations

Each economic interaction produces a **causal chain** of single-tenant DB operations spread across multiple ticks and agents (see P3, P4). The translator expands each agent's action events into Mode 1 reads + writes. Agents also emit Mode 2 query requests for historical read-back.

#### Mode 1 — Action Events by Agent Type

**Single-agent events** (no cross-tenant interaction, complete in one tick):

| Event              | Agent    | Tenant Writes                                          | Correlated Reads (discarded)                          |
|--------------------|----------|--------------------------------------------------------|-------------------------------------------------------|
| consumer_browses   | Consumer | (none — read-only event)                              | SELECT catalog, SELECT reviews                        |
| seller_reprices    | Seller   | UPDATE store_pricing SET price (hotspot potential)    | SELECT competitor_prices, SELECT own sales_analytics  |
| supplier_produces  | Supplier | UPDATE suppliers SET capacity                         | SELECT purchase_orders (pending)                      |
| government_reports | Gov      | INSERT statistics                                     | SELECT ... GROUP BY (analytical)                      |
| trend_propagates   | Social   | Batch UPDATE influence_edges                          | SELECT community_posts (graph)                        |

**Multi-agent causal chain: Purchase Flow** (the most important workload pattern):

A single consumer purchase cascades across 4 agent types over 3–4 ticks. Each tick produces single-tenant writes in a different agent's tables. This is not a design limitation — it's the realistic model and creates the most valuable DB test patterns.

| Tick | Agent    | Trigger               | Ch.1 Action Event → DB Writes                                                                          | Ch.2 Messages Sent                                                    |
|------|----------|-----------------------|--------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| N    | Consumer | wants_to_buy()        | INSERT consumer_orders (Consumer App tenant)<br>Reads: SELECT catalog, SELECT reviews                 | → Store: PlaceOrder(product, qty, price, order_req_id)                |
| N+1  | Store    | inbox: PlaceOrder     | SELECT inventory (check stock)<br>INSERT store_orders<br>UPDATE inventory SET qty -= N (Store tenant) | → Consumer: OrderConfirmed (or OrderRejected)<br>→ Transport: ShipRequest<br>→ Payment: Charge<br>→ Government: OrderReport |
| N+2  | Transport | inbox: ShipRequest   | INSERT shipments<br>INSERT tracking_events (Logistics tenant)                                          | (none initially)                                                      |
| N+2  | Payment  | inbox: Charge         | INSERT transactions (debit + credit) (Payment Ledger tenant)                                           | → Consumer: PaymentConfirmed                                          |
| N+2  | Government | inbox: OrderReport  | INSERT gov_records (Analytics tenant)                                                                  | (none)                                                                |
| N+3  | Consumer | inbox: OrderConfirmed<br>inbox: PaymentConfirmed | UPDATE consumer_orders SET status='confirmed' (Consumer App tenant)<br>(local wallet update — no DB write) | → Community: SharePurchase (triggers social propagation) |

**DB test value of the purchase chain**:

| Tick | Tenants Written | SQL Pattern | What It Tests in TiDB |
|------|----------------|-------------|----------------------|
| N | Consumer App | 1 INSERT | Single-tenant point write |
| N+1 | Store | 1 SELECT + 1 INSERT + 1 UPDATE (txn) | **Read-then-write transaction**, inventory hotspot |
| N+2 | Logistics, Payment, Gov | 3 INSERTs (parallel, different tenants) | Cross-tenant write fan-out, no distributed txn |
| N+3 | Consumer App | 1 UPDATE | Write-after-write on same tenant (status update), eventual consistency |

**Rejection path** (store out of stock): At tick N+1, store sends `OrderRejected` instead. Tick N+2 has no Transport/Payment/Gov writes. Tick N+3 consumer updates status to `rejected`. Different write pattern = different DB workload = valuable test diversity.

**Multi-agent causal chain: Supply Chain Disruption**:

| Tick | Agent      | Trigger                 | Ch.1 Action Event → DB Writes                                                       | Ch.2 Messages Sent                      |
|------|------------|-------------------------|-------------------------------------------------------------------------------------|-----------------------------------------|
| N    | Supplier   | disruption injected     | UPDATE suppliers SET capacity=0 (Supplier ERP tenant)                               | → Stores: SupplyDisruption (all downstream stores) |
| N+1  | Store      | inbox: SupplyDisruption | UPDATE catalog SET available=false<br>UPDATE store_pricing (raise prices) (Store tenant) | → Government: DisruptionReport     |
| N+2  | Government | inbox: DisruptionReport | INSERT gov_records (disruption tracking) (Analytics tenant)                         | (none)                                  |

**Seasonal/viral spike events**: These multiply the purchase chain frequency by 5–10x. A viral trend activates 1000 consumers buying the same product → 1000 concurrent purchase chains → 1000 `PlaceOrder` messages to the same store in one tick → massive inventory contention at tick N+1. This is the most realistic hot-spot stress test.

#### Mode 2 — Async Query Pipeline (Historical Read-Back)

| Query Template           | SQL Pattern                                                                  | Returns (domain struct)                       | TiDB Test Value                                               |
|--------------------------|------------------------------------------------------------------------------|-----------------------------------------------|---------------------------------------------------------------|
| order_history            | SELECT consumer_orders JOIN ...<br>WHERE consumer_id=? AND created_at > ?   | {orders: [{id, status, is_late}], count}      | Secondary index range scan,<br>Read-After-Write on consumer_orders |
| shipment_tracking        | SELECT shipments LEFT JOIN tracking<br>WHERE order_id=? ORDER BY timestamp  | {status, eta, is_delayed, last_location}      | Point lookup + LEFT JOIN on append-heavy table                |
| sales_analytics          | SELECT SUM(qty), SUM(revenue)<br>FROM store_orders JOIN ...<br>WHERE seller_id=? GROUP BY product_id | {revenue, top_products, trend} | Multi-table JOIN, GROUP BY, aggregate (analytical pressure)  |
| fulfillment_overdue      | SELECT purchase_orders<br>WHERE supplier_id=? AND due_date < NOW()          | {overdue_count, worst_delay_days}             | Composite index scan, range on date, status filter            |
| competitor_prices        | SELECT products WHERE category=?<br>ORDER BY price ASC LIMIT 20             | {avg_price, min_price, price_rank}            | Category index scan, sorted read                              |
| gov_economic_indicators  | SELECT COUNT(*), AVG(...), SUM(...)<br>FROM gov_records JOIN statistics<br>GROUP BY sector, region | {gdp, unemployment, inflation, trade_balance} | Full table scans, heavy GROUP BY, multi-table analytical JOINs |

Mode 2 queries hit **real data written by Mode 1 in earlier ticks**, creating Read-After-Write contention — the most valuable pattern for testing TiDB's SI isolation. The translator reduces all result sets to small domain structs before returning to agents (see P1 — Bidirectional Contract).

### P7: Temporal Realism via Modulation Functions

```python
base_purchase_rate = agent.profile.daily_purchases
effective_rate = (base_purchase_rate
    * HOURLY_CURVE[current_hour]       # peak at lunch, evening
    * WEEKLY_CURVE[current_day]        # weekend spike
    * SEASONAL_CURVE[current_month]    # holiday peaks
    * active_trends.boost_factor)      # viral moments
```

This creates realistic temporal workload variation — exactly what tests autoscaling, resource allocation, and load balancing in distributed databases.

### P8: Dual-Mode Read Path — Action-Correlated Reads + Async Query Pipeline

The write path is straightforward: agent decision → event → Go translator → SQL INSERT/UPDATE → TiDB. The **read path** has two complementary modes that together produce a complete, realistic read workload.

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

#### Mode 1: Action-Correlated Reads (Hot-Path Transactional)

When an agent takes an action (purchase, reprice, ship), the event includes **read patterns** that would logically precede the write in a real application. The Go translator fires these SELECTs, consumes the full result set, then **discards** the results. TiDB executes the exact same query plan regardless — index lookups, buffer pool pressure, and coprocessor work are identical whether results are "used" or not.

This is the TPC-C model: the benchmark driver issues `SELECT ... FROM stock` before `UPDATE stock`, but no simulated human reads the screen.

```json
// Consumer's action event (tick N) — writes only to Consumer App tenant
{
  "type": "consumer_purchase_intent",
  "tenant_id": "consumer_app_001",
  "reads": [
    {"pattern": "browse_catalog", "params": {"category": "electronics", "limit": 20}},
    {"pattern": "check_reviews", "params": {"product_id": 7}}
  ],
  "writes": [
    {"pattern": "insert_consumer_order", "params": {"order_request_id": "abc", "product_id": 7, "qty": 2}}
  ],
  "messages": [
    {"to": "store_003", "type": "place_order", "payload": {"product_id": 7, "qty": 2, "order_request_id": "abc"}}
  ]
}

// Store's action event (tick N+1) — writes only to Store tenant
{
  "type": "store_accept_order",
  "tenant_id": "store_003",
  "reads": [
    {"pattern": "check_inventory", "params": {"product_id": 7}}
  ],
  "writes": [
    {"pattern": "insert_store_order", "params": {"order_request_id": "abc", "product_id": 7, "qty": 2, "price": 29.99}},
    {"pattern": "update_inventory", "params": {"product_id": 7, "qty_delta": -2}}
  ],
  "messages": [
    {"to": "consumer_042", "type": "order_confirmed", "payload": {"order_request_id": "abc", "order_id": 7044}},
    {"to": "transport_005", "type": "ship_request", "payload": {"order_id": 7044}},
    {"to": "payment_001", "type": "charge", "payload": {"amount": 59.98}},
    {"to": "gov_001", "type": "order_report", "payload": {"order_id": 7044, "amount": 59.98}}
  ]
}
```

The translator expands this into: SELECTs → think-time delay (50–500ms) → BEGIN; writes; COMMIT.

**Critical rule**: The translator **must read the full result set** (`rows.Next()` through every row). If you close the cursor without consuming rows, TiDB may short-circuit execution.

#### Mode 2: Async Query Pipeline (Historical Read-Back)

Agents periodically request **domain answers about their own historical data** from TiDB — order status, shipment delays, sales performance, economic indicators. These are real queries against real data that the translator wrote in earlier ticks. The translator executes the SQL, reduces the result to a domain struct (per P1), and delivers the struct to the agent's inbox asynchronously.

**This is the most valuable read workload for DB testing.** It creates Read-After-Write contention on the same tables — exactly the pattern that exercises TiDB's SI isolation and secondary indexes. TPC-C's "Order Status" transaction works this way: the driver doesn't track orders in memory, it asks the DB.

```
TICK N                              BETWEEN TICKS                    TICK N+1
──────                              ──────────────                   ────────

Agent 42                            Go Translator                    Agent 42
  │                                      │                              │
  ├─► action: purchase ─────────────────►├─► Mode 1: SELECT+INSERT      │
  │                                      │                              │
  ├─► query: order_history ─────────────►├─► Mode 2: SELECT             │
  │   {consumer_id: 42, window: 30d}     │   FROM consumer_orders       │
  │                                      │   WHERE consumer_id=42       │
  │   (agent does NOT block)             │   AND created_at > ...       │
  │                                      │        │                     │
  │                                      │        ▼                     │
  │                                      │   reduce → domain answer     │
  │                                      │        → inbox ─────────────► drain_inbox()
  │                                      │                              │  update local state
  │                                      │                              │  decide: cancel late order
  │                                      │                              ├─► action: cancel_order
```

**Key invariant**: An agent **never sees the result of a query in the same tick it was issued**. Minimum latency = 1 tick. This preserves tick throughput — agents still decide from local state, they just get periodic domain-level "state refreshes" from TiDB that arrive asynchronously, like reading yesterday's newspaper. The translator reduces all results to small domain structs before delivery (see P1), so inbox memory cost is negligible.

#### Query Request / Result Event Format

Agents emit query requests as events (same channel as actions). Reduced domain answers come back to the agent's inbox. Inter-agent messages (Ch.2) also arrive in the same inbox:

```python
# ── Channel 2: Inter-Agent Messages (in-memory only, never touches DB) ──

@dataclass
class InterAgentMessage:
    msg_type: str              # "place_order", "order_confirmed", "order_rejected",
                               # "ship_request", "charge", "order_report", etc.
    from_agent: int
    to_agent: int
    from_tenant: str           # sender's tenant ID
    tick_sent: int
    payload: dict              # message-type-specific data
    # e.g. PlaceOrder: {product_id, qty, price, order_request_id}
    # e.g. OrderConfirmed: {order_id, order_request_id, eta}
    # e.g. OrderRejected: {order_request_id, reason: "out_of_stock"}

# ── Channel 3: Query Pipeline (DB-backed, async) ──

# Emitted by agent alongside action events
@dataclass
class QueryRequest:
    event_type: str = "query_request"
    query_id: str              # uuid, for correlation
    agent_id: int
    query_template: str        # enum: "order_history", "shipment_tracking", etc.
    params: dict               # template-specific parameters
    tick_issued: int

# Delivered to agent's inbox in a future tick
@dataclass
class QueryResult:
    event_type: str = "query_result"
    query_id: str              # correlates to request
    agent_id: int
    query_template: str        # which template produced this
    tick_issued: int           # when agent asked
    tick_available: int        # earliest tick agent can see this (≥ tick_issued + 1)
    data: dict                 # reduced domain struct (NOT raw rows — see P1)

# ── Inbox: Union type for both channels ──
InboxItem = Union[InterAgentMessage, QueryResult]
```

The `data` field is a **small, fixed-schema domain struct** whose shape is defined per template. The translator executes the full SQL query (100K rows if needed — that's the DB pressure we want), then reduces the result to O(1) domain metrics before crossing the IPC boundary. Examples:

```python
# order_history → translator scans consumer_orders table, reduces to summary
{"orders": [{"id": 7044, "status": "in_transit", "is_late": True}], "count": 3}

# gov_economic_indicators → translator runs heavy GROUP BY, returns 200 bytes
{"gdp": 1.2e9, "unemployment": 0.04, "inflation": 0.02, "trade_balance": 5.3e7}

# sales_analytics → translator aggregates store_orders, returns top-line metrics
{"revenue": 48500.0, "top_products": [12, 45, 78], "trend": "up"}
```

#### Query Template Registry (Go Translator)

Agents pick from a **fixed set of parameterized templates** — they never write SQL. Each template maps to a realistic e-commerce read pattern. The translator executes the full SQL (generating DB pressure) and **reduces** the result to a domain struct before returning it to the agent (see P1). P9 formalizes these templates as entries in the unified operation catalog alongside Mode 1 read/write patterns:

| Template            | SQL (executed in full by translator)                                                                                              | Returns (domain struct)                                  | What It Tests in TiDB                                      |
|---------------------|-----------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------|------------------------------------------------------------|
| order_history       | SELECT ... FROM consumer_orders<br>WHERE consumer_id=? AND created_at > ?<br>ORDER BY created_at DESC LIMIT 50                   | {orders: [{id, status, is_late}], count: int}            | Secondary index range scan (consumer_id, created_at)       |
| shipment_tracking   | SELECT ... FROM shipments LEFT JOIN tracking_events<br>WHERE order_id=? ORDER BY timestamp DESC                                   | {status, eta, is_delayed, last_location}                 | Point lookup by order_id, LEFT JOIN, ORDER BY on append table |
| sales_analytics     | SELECT product_id, SUM(qty), SUM(revenue)<br>FROM store_orders<br>WHERE seller_id=? AND created_at > ?<br>GROUP BY product_id ORDER BY revenue DESC | {revenue, top_products: [id], trend: up/down/flat} | Multi-table JOIN, GROUP BY, aggregate, ORDER BY           |
| fulfillment_overdue | SELECT ... FROM purchase_orders<br>WHERE supplier_id=? AND status='pending'<br>AND due_date < NOW()                               | {overdue_count, worst_delay_days}                        | Composite index scan, range on date, filter on status      |
| competitor_prices   | SELECT product_id, price FROM products<br>WHERE category=? ORDER BY price ASC LIMIT 20                                           | {avg_price, min_price, price_rank}                       | Category index scan, sorted read                           |
| gov_economic_indicators | SELECT COUNT(*), AVG(salary), SUM(revenue) ...<br>FROM gov_records JOIN statistics<br>GROUP BY sector, region                | {gdp, unemployment, inflation, trade_balance, sector_breakdown} | Full table scans, heavy GROUP BY, multi-table analytical JOINs |

Note: the SQL column shows what TiDB executes (this is the DB workload). The Returns column shows what the agent receives (this is the IPC payload). The gap between them — potentially 100K rows scanned → 200 bytes returned — is the translator's reduction responsibility.

#### Rate Limiting: Agents Don't Query Every Tick

```python
QUERY_COOLDOWNS = {
    "order_history":          50,   # consumer checks orders every ~50 ticks
    "shipment_tracking":      20,   # more frequent for active orders
    "sales_analytics":       100,   # seller checks weekly
    "fulfillment_overdue":    30,   # supplier checks regularly
    "competitor_prices":      40,   # seller monitors competition
    "gov_economic_indicators":100,  # government runs census periodically
}
```

With 10K active consumers at avg cooldown 50 ticks: ~200 queries/tick. This is a natural, staggered read workload — not a synchronized burst.

#### Agent-Side Implementation

```python
class ConsumerAgent(Agent):
    def __init__(self, ...):
        self.inbox: deque[InboxItem] = deque()       # receives BOTH Ch.2 messages AND Ch.3 query results
        self.known_orders: dict[int, dict] = {}       # populated from query results
        self.pending_orders: dict[str, dict] = {}     # order_request_id → {product, qty, status}
        self.query_cooldown: dict[str, int] = {}       # last query tick per template

    def step(self):
        # ── Step 0: Drain inbox (both Ch.2 messages and Ch.3 query results) ──
        while self.inbox:
            item = self.inbox.popleft()
            if isinstance(item, InterAgentMessage):
                self._handle_message(item)
            elif isinstance(item, QueryResult):
                self._handle_query_result(item)

        # ── Step 2: React to updated state (e.g., late shipment → cancel) ──
        for order_id, info in self.known_orders.items():
            if info.get("is_late") and random() < self.cancel_probability:
                self.emit_action(CancelOrder(order_id=order_id))

        # ── Step 3: Normal purchasing logic (uses in-memory marketplace) ──
        if self._wants_to_buy():
            product = self._pick_product()
            req_id = uuid4()
            self.pending_orders[req_id] = {"product": product, "status": "requested"}
            # Write to OWN tenant (consumer_orders)
            self.emit_action(InsertConsumerOrder(order_request_id=req_id, product=product))
            # Send Ch.2 message to store (store will process next tick)
            self.send_message(InterAgentMessage(
                msg_type="place_order",
                to_agent=product.store_id,
                payload={"product_id": product.id, "qty": 1, "order_request_id": req_id}
            ))

        # ── Step 4: Periodically request data refresh (NOT every tick) ──
        if self._cooldown_expired("order_history"):
            self.emit_query(QueryRequest(
                query_template="order_history",
                params={"consumer_id": self.unique_id, "window_days": 30}
            ))

    def _handle_message(self, msg: InterAgentMessage):
        """Process Ch.2 inter-agent messages."""
        if msg.msg_type == "order_confirmed":
            req_id = msg.payload["order_request_id"]
            if req_id in self.pending_orders:
                self.pending_orders[req_id]["status"] = "confirmed"
                # Write status update to OWN tenant
                self.emit_action(UpdateConsumerOrder(
                    order_request_id=req_id, status="confirmed"
                ))
        elif msg.msg_type == "order_rejected":
            req_id = msg.payload["order_request_id"]
            if req_id in self.pending_orders:
                self.pending_orders[req_id]["status"] = "rejected"
                self.emit_action(UpdateConsumerOrder(
                    order_request_id=req_id, status="rejected"
                ))
        elif msg.msg_type == "payment_confirmed":
            pass  # update local wallet state, no DB write

    def _handle_query_result(self, result: QueryResult):
        """Process Ch.3 query results (reduced domain structs from translator)."""
        if result.query_template == "order_history":
            for order in result.data["orders"]:
                self.known_orders[order["id"]] = order
                # is_late already computed by translator


class StoreAgent(Agent):
    """Store agent processes PlaceOrder messages and writes to its OWN tenant."""

    def step(self):
        # ── Step 0: Drain inbox ──
        while self.inbox:
            item = self.inbox.popleft()
            if isinstance(item, InterAgentMessage):
                self._handle_message(item)
            elif isinstance(item, QueryResult):
                self._handle_query_result(item)

        # ── Step 2: Normal store operations (repricing, etc.) ──
        ...

    def _handle_message(self, msg: InterAgentMessage):
        if msg.msg_type == "place_order":
            product_id = msg.payload["product_id"]
            qty = msg.payload["qty"]
            req_id = msg.payload["order_request_id"]

            if self.inventory[product_id] >= qty:
                # Accept: write to OWN tenant (store_orders, inventory)
                self.emit_action(InsertStoreOrder(
                    order_request_id=req_id, product_id=product_id, qty=qty
                ))
                self.emit_action(UpdateInventory(product_id=product_id, qty_delta=-qty))
                # Notify downstream agents via Ch.2
                self.send_message(InterAgentMessage(
                    msg_type="order_confirmed", to_agent=msg.from_agent,
                    payload={"order_request_id": req_id, "order_id": self.next_order_id}
                ))
                self.send_message(InterAgentMessage(
                    msg_type="ship_request", to_agent=self.transport_id,
                    payload={"order_id": self.next_order_id, "dest": msg.from_agent}
                ))
                self.send_message(InterAgentMessage(
                    msg_type="charge", to_agent=self.payment_id,
                    payload={"amount": qty * self.prices[product_id], "consumer": msg.from_agent}
                ))
                self.send_message(InterAgentMessage(
                    msg_type="order_report", to_agent=self.gov_id,
                    payload={"order_id": self.next_order_id, "amount": qty * self.prices[product_id]}
                ))
            else:
                # Reject: no DB write for inventory, just notify consumer
                self.send_message(InterAgentMessage(
                    msg_type="order_rejected", to_agent=msg.from_agent,
                    payload={"order_request_id": req_id, "reason": "out_of_stock"}
                ))
```

#### Go Translator: Separate Read Pipeline

The query pipeline uses a **separate connection pool** from the write path. This mirrors real applications where read replicas or follower reads handle analytical queries:

```
Go Translator (per node):
  Write pipeline:  existing event stream → INSERT/UPDATE → write pool (~75 conns)
  Read pipeline:   query requests → SELECT (templated) → reduce to domain struct
                   → read pool (~16-32 conns) → domain answer → agent inbox via IPC
  
  Read pool features:
    - 2-second query timeout (queries that take too long are cancelled)
    - Agent just doesn't get data that tick — decides from existing local state
    - Separate connection pool prevents read contention from starving writes
    - Translator reduces full result set to fixed-size domain struct before IPC
```

#### Concrete Walk-Through: Consumer Purchase → Multi-Tick Causal Chain

```
Tick 1000: Consumer 42 decides to buy product 7 from Store 003
           ├─► Ch.1: INSERT consumer_orders (Consumer App tenant)
           │   Mode 1 reads: SELECT catalog + SELECT reviews (discarded)
           └─► Ch.2: PlaceOrder(product=7, qty=1, req_id=abc) → Store 003's inbox

Tick 1001: Store 003 drains inbox, finds PlaceOrder(abc)
           ├─► Ch.1: SELECT inventory WHERE product_id=7 (check stock)
           │         INSERT store_orders (order_id=7044, req_id=abc)
           │         UPDATE inventory SET qty -= 1  (Store tenant)
           ├─► Ch.2: OrderConfirmed(order_id=7044, req_id=abc) → Consumer 42's inbox
           ├─► Ch.2: ShipRequest(order_id=7044, dest=consumer_42) → Transport 5's inbox
           ├─► Ch.2: Charge(amount=29.99, consumer=42) → Payment's inbox
           └─► Ch.2: OrderReport(order_id=7044, amount=29.99) → Government's inbox

Tick 1002: Transport 5 drains inbox, creates shipment
           ├─► Ch.1: INSERT shipments, INSERT tracking_events (Logistics tenant)
           Payment drains inbox, settles transaction
           ├─► Ch.1: INSERT transactions (debit + credit) (Payment Ledger tenant)
           ├─► Ch.2: PaymentConfirmed → Consumer 42's inbox
           Government drains inbox, records order
           └─► Ch.1: INSERT gov_records (Analytics tenant)

Tick 1003: Consumer 42 drains inbox
           ├─► sees OrderConfirmed(req_id=abc) → marks pending_orders[abc] = "confirmed"
           │   Ch.1: UPDATE consumer_orders SET status='confirmed' (Consumer App tenant)
           ├─► sees PaymentConfirmed → updates local wallet (no DB write)
           └─► Ch.2: SharePurchase → Community (triggers social propagation next tick)

           ... later ...

Tick 1050: Consumer 42's order_history cooldown expires
           └─► emits QueryRequest("order_history", {consumer_id: 42, window: 30d})
               (agent does NOT block — continues with existing local state)

Between ticks: Go translator (read pipeline) executes:
    SELECT o.order_request_id, o.status, o.created_at
    FROM consumer_orders_t003 o
    WHERE o.consumer_id = 42 AND o.created_at > DATE_SUB(NOW(), INTERVAL 30 DAY)
    ORDER BY o.created_at DESC LIMIT 50

    → Translator also joins against shipment data via cross-tenant read (gov has read access)
    → Reduces: {orders: [{id: "abc", status: "confirmed", is_late: true}], count: 1}
    → Delivers domain struct to agent 42's inbox

Tick 1051: Agent 42 drains inbox
           → sees order "abc" is_late=true (translator computed from shipment ETA vs today)
           → cancel_probability triggers → emits CancelOrder
           → Ch.1: UPDATE consumer_orders SET status='cancel_requested' (Consumer App tenant)
           → Ch.2: CancelRequest(order_id=7044) → Store 003's inbox

Tick 1052: Store 003 drains inbox, processes cancellation
           → Ch.1: UPDATE store_orders SET status='cancelled' (Store tenant)
           → Ch.2: CancelConfirmed → Consumer 42's inbox
           → Ch.2: CancelShipment → Transport 5's inbox
```

**TiDB workload from this single purchase** (ticks 1000–1003):

| Tick | Tenant | SQL Operations | TiDB Pattern Tested |
|------|--------|---------------|---------------------|
| 1000 | Consumer App | 1 INSERT + 2 SELECT (correlated) | Point write + catalog scan |
| 1001 | Store | 1 SELECT + 1 INSERT + 1 UPDATE (txn) | **Inventory hotspot**, read-then-write |
| 1002 | Logistics | 2 INSERT | Append-only table |
| 1002 | Payment | 1 INSERT (2 rows: debit+credit) | Double-entry strict consistency |
| 1002 | Government | 1 INSERT | Analytics tenant write |
| 1003 | Consumer App | 1 UPDATE | Status update, write-after-write |
| 1050 | Consumer App | 1 range SELECT + JOIN | **Read-After-Write**, secondary index |
| 1051 | Consumer App | 1 UPDATE | Write-After-Read on same table |
| 1052 | Store | 1 UPDATE | Cross-tenant cancel cascade |

**Total**: 1 logical purchase → 13 SQL statements across 5 tenants over 4+ ticks. No cross-tenant transaction. This is exactly the SI isolation and multi-tenant write-stagger pattern that synthetic benchmarks cannot produce.

#### Why Two Modes, Not One

| | Mode 1: Action-Correlated | Mode 2: Query Pipeline |
|---|---|---|
| **Purpose** | Hot-path transactional reads | Historical lookups, status checks, analytics |
| **Timing** | Synchronous with write (same event) | Async (result arrives in future tick) |
| **Results used?** | Consumed by translator, discarded | Reduced to domain struct, delivered to agent inbox |
| **Data accessed** | Current catalog, prices, inventory | Historical orders, shipments, aggregates |
| **Read pattern** | Point lookups, short scans | Range scans, JOINs, GROUP BY |
| **DB test value** | Read-write transaction patterns | Read-After-Write isolation, secondary index coverage |
| **Frequency** | Every action event | Rate-limited per agent per template |

Together they produce the complete read mix of a real e-commerce system: hot-path transactional reads (browse before buy) + periodic historical lookups (check my orders) + analytical aggregations (seller checks sales). Neither mode alone captures the full workload.

#### Capacity Impact

```
Per node (c7g.4xlarge):
  Write pool:        ~75 connections (unchanged)
  Read pool (new):   ~16–32 connections (separate, for query pipeline)
  Total per node:    ~91–107 connections
  
  Mode 1 read QPS:   ~23K (correlated to ~53K write QPS, ~45% read share)
  Mode 2 read QPS:   ~40–200 (rate-limited by agent cooldowns)
  Total read QPS:    ~23K–24K per node
  
Across 10 nodes:
  Total connections:  ~910–1,070 (< 4,000 limit ✓✓)
  Total read QPS:     ~230K–240K
  Total write QPS:    ~290K
  Total QPS:          ~520K–530K (target met ✓)
```

#### Watch Out For

- **Feedback amplification**: Agent sees late order → cancels → cancel message cascades to store/transport/payment → more agents query → more cancellations → cascade. **Mitigation**: cooldown rate-limiters + probabilistic decisions (`cancel_probability`) naturally dampen cascades. Monitor cancellation rate and adjust probability if runaway.
- **Stale results are a feature, not a bug**: An agent's domain answers from TiDB are always ≥1 tick old. Inter-agent messages also arrive with 1-tick delay. This mirrors real e-commerce (eventual consistency of user-facing dashboards). Don't try to make it "more current."
- **Query timeout ≠ agent error**: If a query times out (2s limit), the agent just doesn't get a domain answer. It keeps deciding from existing local state. No retry logic needed.
- **Inbox memory is negligible**: Each agent's inbox holds a handful of items between ticks (~5 InterAgentMessages + ~1 QueryResult on average). At ~200 bytes per item, 50K agents × 6 items × 200B = ~60 MB per node. Drained every tick.

### P9: Operation Catalog — One Registry, Two Execution Modes

P1 introduced the template registry as a "fixed set of named operations." P8 introduced the query template registry for Mode 2 async reads. The action event JSON (P8, Mode 1) also uses named read/write patterns inside each event. These are **three implicit registries for the same concept** — a named operation with typed parameters that expands to SQL and optionally reduces to a domain struct.

P9 makes this explicit: **there is one operation catalog**. The distinction between a "read pattern inside an action event" and a "query template" is an execution-mode difference, not a type difference.

#### The Coherence Problem

The current design has three namespaces:

1. **Event types** — `store_accept_order`, `consumer_purchase_intent` (dispatch key)
2. **Read/write patterns** — `check_inventory`, `insert_store_order` (inside event JSON body)
3. **Query templates** — `order_history`, `sales_analytics` (separate Mode 2 registry)

Event type `store_accept_order` *implicitly requires* that patterns `check_inventory`, `insert_store_order`, and `update_inventory` exist. But nothing declares or enforces this — a typo on the Python side produces a runtime error in Go. Meanwhile, query templates live in a completely separate namespace with different registration mechanics, even though semantically they do the same thing: expand named params into SQL, optionally reduce, return a domain struct.

#### The Unified Operation Definition

Every operation in the translator — whether it's a correlated read inside a write event, a standalone INSERT, or an async analytical query — is an entry in a single catalog:

```yaml
# operations/store.yaml
domain: store
operations:
  # Sync patterns (used inside Mode 1 action events)
  - name: check_inventory
    mode: read
    params: { product_id: int }
    sql: "SELECT qty FROM {tenant}.inventory WHERE product_id = :product_id"
    returns: { qty: int }

  - name: insert_store_order
    mode: write
    params: { order_request_id: string, product_id: int, qty: int, price: decimal }
    sql: "INSERT INTO {tenant}.store_orders (order_request_id, product_id, qty, price) VALUES (:order_request_id, :product_id, :qty, :price)"

  - name: update_inventory
    mode: write
    params: { product_id: int, qty_delta: int }
    sql: "UPDATE {tenant}.inventory SET qty = qty + :qty_delta WHERE product_id = :product_id"

  # Async query templates (Mode 2 — same catalog, different execution mode)
  - name: sales_analytics
    mode: query
    params: { seller_id: int, window: duration }
    sql: |
      SELECT product_id, SUM(qty), SUM(revenue)
      FROM {tenant}.store_orders
      WHERE seller_id = :seller_id AND created_at > NOW() - :window
      GROUP BY product_id ORDER BY revenue DESC
    reducer: aggregation_summary
    returns: { revenue: decimal, top_products: list, trend: string }

# Event compositions — make implicit coupling explicit
events:
  - name: store_accept_order
    requires: [check_inventory, insert_store_order, update_inventory]
  - name: seller_reprices
    requires: [update_store_pricing]
```

The `events.requires` declaration turns hidden coupling into **startup-time validation**. When the Go translator boots, `Catalog.Validate()` checks that every event type's required patterns exist in the catalog, every query-mode operation has a registered reducer, and every parameter type is valid.

#### Domain-Partitioned Files

One YAML file per simulation domain:

```
operations/
  store.yaml        ← check_inventory, insert_store_order, sales_analytics, ...
  consumer.yaml     ← insert_consumer_order, order_history, ...
  logistics.yaml    ← insert_shipment, shipment_tracking, ...
  payment.yaml      ← insert_transaction, ...
  government.yaml   ← insert_gov_record, gov_economic_indicators, ...
  supplier.yaml     ← update_capacity, fulfillment_overdue, ...
```

Adding a new agent type (e.g., Bank) means adding `bank.yaml` + a schema migration. No Go code changes unless the new domain requires a custom reducer shape.

#### Go Implementation

```go
// One definition type for all operations
type OperationDef struct {
    Name       string            `yaml:"name"`
    Mode       OpMode            `yaml:"mode"`        // read | write | query
    Params     map[string]string `yaml:"params"`       // name -> type (validated at startup)
    SQL        string            `yaml:"sql"`          // single-statement
    SQLSeq     []string          `yaml:"sql_sequence"` // multi-statement (transactional writes)
    ReducerKey string            `yaml:"reducer"`      // query mode only
    Returns    map[string]string `yaml:"returns"`      // documentation + validation
}

type OpMode string
const (
    OpRead  OpMode = "read"
    OpWrite OpMode = "write"
    OpQuery OpMode = "query"
)

// The catalog: loaded once at startup from YAML files
type Catalog struct {
    ops      map[string]OperationDef  // "check_inventory" -> def
    events   map[string][]string      // "store_accept_order" -> [required op names]
    reducers map[string]ReducerFunc   // "aggregation_summary" -> func
}

// ReducerFunc: escape hatch for custom aggregation logic
type ReducerFunc func(rows *sql.Rows) (map[string]any, error)

func (c *Catalog) LoadFromYAML(paths ...string) error { ... }
func (c *Catalog) RegisterReducer(name string, fn ReducerFunc) { ... }
func (c *Catalog) Validate() error { ... }  // fail fast at boot
```

The hot path is a map lookup + parameterized SQL execution. No reflection, no virtual dispatch. At 50K events/tick, this is the right trade-off.

#### What Requires Go Code vs. What Doesn't

| Change | Go code required? |
|--------|-------------------|
| New read/write pattern (simple SQL) | No — YAML only |
| New query template with existing reducer shape | No — YAML only |
| New event type composing existing patterns | No — YAML only |
| New reducer with custom aggregation logic | Yes — register a `ReducerFunc` |
| New tenant routing strategy | Yes — register a `RouterFunc` |

Most simulation behaviors are new compositions of SQL templates — those are zero-code changes. Custom reducers are the escape hatch for the ~10% of cases that need Go logic.

#### Standard Reducer Library

Build 3–4 reusable reducers that cover ~90% of query templates:

| Reducer | Input | Output | Used by |
|---------|-------|--------|---------|
| `single_row` | 1 row, N columns | `map[string]any` | shipment_tracking, fulfillment_overdue |
| `list_with_count` | N rows | `{items: [...], count: int}` | order_history |
| `aggregation_summary` | GROUP BY result | `{metrics: {...}, top_N: [...]}` | sales_analytics, gov_economic_indicators |
| `passthrough` | raw rows | `[]map[string]any` | debugging / ad-hoc |

If you find yourself writing many custom reducers, it means return types are too varied — standardize on these shapes first.

#### The Pattern Name

This architecture is a **Table-Driven Interpreter** (Fowler) within a **CQRS** structure:

- **CQRS** (Command Query Responsibility Segregation) — a pattern that separates the write model (commands that change state) from the read model (queries that return data), giving each its own execution path, data model, and optimization strategy. In BizSim: action events are commands (they mutate tenant tables via Mode 1), query requests are queries (they read and reduce via Mode 2). The two paths have different connection pools, different result handling, and different latency profiles. CQRS is the reason this separation is principled rather than accidental — Mode 1 and Mode 2 are not "two ways to do the same thing," they are structurally different operations that happen to share the same translator binary.
- **Table-Driven Interpreter** — the translator interprets a closed vocabulary of domain operations via catalog lookup. The catalog (YAML files) IS the DSL specification. Agents speak in domain commands; the translator looks up the expansion rules in the table.
- **Not Event Sourcing** — Event Sourcing uses a persisted event log as the *authoritative source of truth for application state*: you reconstruct the current state of an order by replaying `OrderCreated → OrderPaid → OrderShipped`. BizSim events are not that. The event log (see §9, Local Disk Event Log) is a *workload recording* — it captures what SQL traffic the simulation generated, so you can replay the same DB workload against a different TiDB configuration without re-running the live simulation. The simulation's own state (agent memories, tick counter, random seed) lives in the Python process, not in the log. The log is the benchmark artifact; TiDB is the database being tested.
- **Not a general DSL** — it's a closed, fixed vocabulary. Agents cannot compose new operations at runtime. The vocabulary grows only when a simulation developer edits the YAML catalog and restarts.

#### Boundary Conditions

- **No conditional logic in the catalog.** If an operation needs IF/ELSE (e.g., "IF inventory < threshold THEN reject"), that logic belongs in the Python agent, not the YAML. The agent emits `check_inventory` (read), inspects the result, and decides which write to emit. The catalog is purely declarative.
- **No cross-tenant operations.** Each operation's SQL uses `{tenant}` as a single schema prefix. If a future requirement demands multi-tenant transactions (e.g., marketplace settlements touching two tenants atomically), the catalog model needs rethinking. Flag this as a known boundary.
- **SQL injection prevention.** Structural expansion (`{tenant}` → schema prefix) is safe because tenant IDs come from the simulation's own registry. Value binding (`:product_id` → `?` placeholders) must always use parameterized queries, never string interpolation.

---

## 3A. Architectural Guardrails

P1–P9 define what the system must do. This section defines how those principles are **enforced structurally** — not by documentation or convention, but by mechanisms that make violations physically impossible, caught at compile/startup time, or caught by CI.

The target audience is the coder agent implementing this system. These are not suggestions. A coder agent that circumvents these mechanisms is violating the architecture, not improving it.

### The Problem with Tests as Guardrails

Tests are the weakest form of enforcement — a coder agent can weaken or delete them. The goal is **structural impossibility**: a violation should require editing the enforcement code itself, which is itself guarded by CI. The enforcement hierarchy, strongest to weakest:

| Tier | Mechanism | Cannot be bypassed by editing... |
|------|-----------|----------------------------------|
| **S — Physically impossible** | Go unexported fields/types, Python import blocker | Single file (requires coordinated multi-file edits that CI catches) |
| **A — Compile/startup time** | `NewExecutor` requires validated catalog; Go package layout blocks `database/sql` import | Application logic (type system rejects it) |
| **B — CI (external)** | grep checks in CI pipeline the agent cannot edit | Anything — CI is outside agent's edit scope |
| **C — Test floor** | CI enforces minimum test counts | Any single test file (floor prevents silent deletion) |
| **D — Tests** | Unit + integration tests | Test files (weakest — last line of defense only) |

Build Tier S and A first. Use Tier B (CI) as the tamper-evident seal over both.

---

### G1: P1 Boundary — Agents Cannot Touch SQL

**Constraint**: Python agents only emit named events and receive domain structs. No agent code ever sees SQL, table names, or column names.

#### Python — Import Firewall (Tier S)

The agent execution harness installs an import blocker **before** any agent module loads:

```python
# bizsim/agents/_sandbox.py
import sys, importlib.abc

_BLOCKED_MODULES = frozenset({
    "sqlalchemy", "sqlite3", "psycopg2", "pymysql",
    "mysql.connector", "bizsim.translator", "bizsim.db", "subprocess",
})

class _ImportBlocker(importlib.abc.MetaPathFinder):
    def find_module(self, fullname, path=None):
        for blocked in _BLOCKED_MODULES:
            if fullname == blocked or fullname.startswith(blocked + "."):
                return self
    def load_module(self, fullname):
        raise ImportError(
            f"P1 VIOLATION: agents cannot import '{fullname}'. "
            f"Emit a named event instead."
        )

def activate():
    sys.meta_path.insert(0, _ImportBlocker())
```

```python
# bizsim/agents/runner.py — the ONLY entry point for running agents
from bizsim.agents._sandbox import activate
activate()  # BEFORE any agent module is imported
```

#### Python — SQL-Unrepresentable Event Type (Tier A)

The `Event` dataclass — the only type agents can emit — has no field that can hold a SQL string. Defense-in-depth: `__post_init__` rejects param values that look like SQL keywords:

```python
# bizsim/events.py
@dataclass(frozen=True)
class Event:
    event_type: str
    tenant_id: str
    params: dict[str, int | float | str | bool]  # scalar values only

    def __post_init__(self):
        SQL_KEYWORDS = {"SELECT ", "INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER "}
        for v in self.params.values():
            if isinstance(v, str) and any(kw in v.upper() for kw in SQL_KEYWORDS):
                raise ValueError(f"P1 VIOLATION: SQL-like string in event params: {v!r}")
```

#### Go — `*sql.DB` is Unexported (Tier A — compile time)

The `handler` package (agent-facing) has no `*sql.DB` and cannot import `database/sql`. SQL can only be executed through `executor.Execute()`:

```
go-translator/pkg/
  executor/      ← owns *sql.DB (unexported field)
  handler/       ← calls executor.Execute() — no database/sql import
  internal/db/   ← connection setup, only executor imports this
```

#### CI Check (Tier B)

```yaml
# .github/workflows/arch-guard.yml
- name: P1 — No SQL import in agent code
  run: |
    VIOLATIONS=$(grep -rn 'import.*\(sqlalchemy\|sqlite3\|psycopg2\|pymysql\)' \
      bizsim/agents/ --include='*.py' || true)
    [ -z "$VIOLATIONS" ] || { echo "P1 VIOLATION: $VIOLATIONS"; exit 1; }

- name: P1 — Sandbox integrity check
  run: |
    python -c "
    import ast, sys
    src = open('bizsim/agents/_sandbox.py').read()
    tree = ast.parse(src)
    required = {'sqlalchemy', 'sqlite3', 'psycopg2', 'pymysql', 'bizsim.translator'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'frozenset':
            found = {e.value for e in node.args[0].elts if isinstance(e, ast.Constant)}
            missing = required - found
            if missing: sys.exit(f'SANDBOX TAMPERED: missing: {missing}')
    "
```

---

### G2: P4 Tenant Sovereignty — No Cross-Tenant Writes

**Constraint**: An agent's action events must always write to its own tenant. No agent can write to another agent's tenant tables.

#### Go — Unforgeable `TenantScope` Capability Token (Tier S — compile time)

`TenantScope` is an opaque token whose only constructor is unexported. Code outside `pkg/executor` cannot fabricate one:

```go
// pkg/executor/tenant.go
type TenantScope struct {
    tenantID string  // unexported — unreadable and unwritable outside this package
}

// newTenantScope is unexported — only executor creates these, from the incoming event's tenant_id
func newTenantScope(id string) TenantScope { return TenantScope{tenantID: id} }
```

The executor **ignores** any `tenant_id` in caller-supplied params and always uses the scope:

```go
func (e *Executor) Execute(ctx context.Context, scope TenantScope, op string, params map[string]any) (Result, error) {
    params["tenant_id"] = scope.tenantID  // overwrite unconditionally
    // ...
}
```

#### Python — Tenant Baked into `EventEmitter` (Tier A)

Agents receive a pre-bound `EventEmitter`. There is no `emit(tenant_id=..., ...)` method:

```python
# bizsim/domain.py
@dataclass(frozen=True)
class TenantContext:
    tenant_id: str  # immutable after construction

class EventEmitter:
    def __init__(self, tenant: TenantContext):
        self._tenant = tenant

    def emit(self, event_type: str, params: dict) -> Event:
        return Event(event_type=event_type, tenant_id=self._tenant.tenant_id, params=params)
        # tenant_id NEVER comes from the caller
```

---

### G3: P9 Operation Catalog — No Ad-Hoc SQL in Go

**Constraint**: All SQL lives in YAML catalog entries. No SQL string literals appear in Go code outside the catalog expansion logic.

#### Go Package Layout (Tier A — compile time)

`handler/` cannot call `db.Query()` because it has no `*sql.DB`. The executor's internal `run()` method — the only function that calls `db.QueryContext` — is unexported:

```go
// pkg/executor/executor.go
type Executor struct {
    db      *sql.DB          // unexported
    catalog *catalog.Catalog // unexported
}

// run is unexported — the only site where db.QueryContext is called
func (e *Executor) run(ctx context.Context, def catalog.OperationDef, params map[string]any) (Result, error) {
    query, args := def.Expand(params)  // SQL comes from YAML, never from caller
    rows, err := e.db.QueryContext(ctx, query, args...)
    // ...
}
```

#### `NewExecutor` Requires a Validated Catalog (Tier A — startup time)

A catalog that has not passed `Validate()` cannot be used to construct an `Executor`. The `validated` field is unexported:

```go
// pkg/catalog/catalog.go
type Catalog struct {
    ops       map[string]OperationDef
    events    map[string]bool
    validated bool  // unexported — only Validate() sets this to true
}

func (c *Catalog) Validate() error {
    // ... check all refs resolve, SQL templates parse, reducers exist ...
    c.validated = true
    return nil
}

// pkg/executor/executor.go
func NewExecutor(db *sql.DB, cat *catalog.Catalog) (*Executor, error) {
    if !cat.IsValidated() {
        return nil, errors.New("P9: catalog must be validated before use — call cat.Validate()")
    }
    return &Executor{db: db, catalog: cat}, nil
}
```

#### CI Check (Tier B)

```yaml
- name: P9 — No database/sql outside executor
  run: |
    VIOLATIONS=$(grep -rn '"database/sql"' go-translator/pkg/ --include='*.go' \
      | grep -v 'pkg/executor/' | grep -v 'pkg/internal/db/' | grep -v '_test.go' || true)
    [ -z "$VIOLATIONS" ] || { echo "P9 VIOLATION: $VIOLATIONS"; exit 1; }

- name: P9 — No raw db.Query calls outside executor
  run: |
    VIOLATIONS=$(grep -rn 'db\.\(Query\|Exec\|Prepare\)(' go-translator/pkg/ --include='*.go' \
      | grep -v 'pkg/executor/executor.go' | grep -v '_test.go' || true)
    [ -z "$VIOLATIONS" ] || { echo "P9 VIOLATION: raw SQL call outside executor: $VIOLATIONS"; exit 1; }
```

---

### G4: P9 Event Composition — Undeclared Events Rejected

**Constraint**: Every event type that Python agents emit must be declared in the operation catalog's `events.requires` section. Undeclared event types are rejected at the translator boundary.

#### Go — Unknown Events Rejected at Startup + Runtime (Tier A)

`Catalog.Validate()` builds the event whitelist. `NewExecutor` requires a validated catalog. Any event type not in the whitelist is rejected by the executor:

```go
func (e *Executor) Execute(ctx context.Context, scope TenantScope, op string, params map[string]any) (Result, error) {
    if !e.catalog.IsKnownEvent(op) {
        return Result{}, fmt.Errorf("P9 VIOLATION: unknown event type %q — add to catalog events.requires", op)
    }
    // ...
}
```

This means a coder agent who adds a new event type in Python must also add it to the YAML catalog. The translator will refuse to process it otherwise — the simulation fails loudly on the first tick that emits the new event.

---

### G5: Ch.2 Isolation — Inter-Agent Messages Never Cross the Translator

**Constraint**: Channel 2 (inter-agent messages) is pure Python in-memory. The Go translator must never receive, parse, or process a `Ch2Message`.

#### Structural Enforcement — Different Python Types, No Go Representation (Tier S)

`Ch2Message` is not a subclass of `Event`. `EventEmitter.emit()` only accepts `Event`-shaped data. There is no serialization path from `Ch2Message` to the Go translator:

```python
# bizsim/channels.py
@dataclass(frozen=True)
class Ch2Message:  # NOT a subclass of Event — different type entirely
    sender: str
    receiver: str
    payload: dict
    # No event_type field — will fail catalog lookup if somehow serialized
```

There is no `Ch2Message` struct in Go. If a `Ch2Message` were somehow serialized and sent, it would either fail JSON deserialization (wrong shape) or be rejected by the catalog event whitelist.

#### CI Check (Tier B)

```yaml
- name: Ch.2 — No inter-agent message handling in Go
  run: |
    VIOLATIONS=$(grep -rn 'Ch2\|Channel2\|ch2\|inter.agent' go-translator/ --include='*.go' || true)
    [ -z "$VIOLATIONS" ] || { echo "Ch.2 VIOLATION: $VIOLATIONS"; exit 1; }
```

---

### G6: Test Floor — Silent Test Deletion Prevention

Tests are the weakest guardrail but still valuable as specification documentation. CI enforces a minimum count that ratchets upward as the codebase grows. A coder agent cannot silently delete tests without CI failing:

```yaml
- name: Meta — Test count floor
  run: |
    PY_TESTS=$(grep -rn 'def test_' bizsim/ --include='*.py' | wc -l)
    GO_TESTS=$(grep -rn 'func Test' go-translator/ --include='*_test.go' | wc -l)
    # UPDATE THESE MINIMUMS when adding significant new test coverage
    MIN_PY=20
    MIN_GO=15
    [ "$PY_TESTS" -ge "$MIN_PY" ] || { echo "FAIL: Python tests ($PY_TESTS) below floor ($MIN_PY)"; exit 1; }
    [ "$GO_TESTS" -ge "$MIN_GO" ] || { echo "FAIL: Go tests ($GO_TESTS) below floor ($MIN_GO)"; exit 1; }
```

---

### Enforcement Summary

| Constraint | Strongest Mechanism | Tier | To bypass, agent must edit... |
|------------|---------------------|------|-------------------------------|
| **P1** — No SQL in agents | Import blocker + unexported `*sql.DB` | S + A | `_sandbox.py` AND `executor.go` (both caught by CI) |
| **P4** — Tenant sovereignty | Unexported `TenantScope` + forced param override | S | `executor.go` (CI catches `db.Query` appearing elsewhere) |
| **P9** — Catalog-only SQL | Executor accepts op names only, `*sql.DB` unexported | A | `executor.go` to expose SQL (CI grep catches it) |
| **P9** — Event whitelist | `NewExecutor` requires `Validate()`; unknown events rejected | A | Both `executor.go` and `catalog.go` |
| **Ch.2** — No Go representation | No `Ch2Message` type in Go; no serialization path | S | Create new Go type + serialization + bypass catalog check |

### What This Section Is

This is not a design principle — it is an **enforcement contract**. The principles (P1–P9) describe what the system does. This section describes the mechanisms that make it hard to accidentally or deliberately violate those principles during implementation.

A coder agent that proposes changes to the guardrail code itself (the import blocker, the `TenantScope` constructor, the `NewExecutor` validation requirement, the CI checks) must treat that as a flag requiring explicit human review — not a routine implementation detail.

---

## 4. Key Design Questions

### Q1: What is the primary workload metric being optimized?

| Goal | Simulation Implication |
|------|----------------------|
| **Workload pattern diversity** (many distinct operation patterns) | Need more entity types and interaction modes |
| **Data volume** (large datasets) | Need more agents, longer simulations |
| **Contention patterns** (hotspots, deadlocks) | Need concentrated seller/inventory access |
| **Temporal realism** (peaks, seasons) | Need sophisticated time modulation |

**Recommendation**: Optimize for **workload pattern diversity** first. A system that produces 20 distinct, reproducible workload patterns is more valuable than one ultra-realistic pattern.

### Q2: How many agents, and does it matter?

For DB testing, **concurrent database sessions** matter more than simulated agents. 1M consumers generating 1 purchase/hour = ~278 TPS from consumers alone.

**Practical approach**:
- Simulate 10K–100K consumers with detailed state
- Scale DB workload independently by multiplying event rates
- Use simulation for **pattern generation**, not raw load generation (use HammerDB for pure throughput)

### Q3: Where does LLM intelligence add DB workload value?

| Domain | LLM Needed? | Why |
|--------|-------------|-----|
| Seller pricing strategy | **Yes** | Creates unpredictable UPDATE patterns, competitive cascades |
| Consumer trend emergence | **Yes** | Creates bursty, correlated READ patterns |
| Individual purchase decisions | **No** | Probability model sufficient, 10,000x cheaper |
| Logistics routing | **No** | Deterministic algorithms produce realistic patterns |
| Government statistics | **No** | Pure aggregation |

**Budget**: ~50–200 LLM calls per simulated day for strategic decisions. Not per-agent, per-event.

### Q4: How does social influence propagation work mechanically?

Model communities as a **weighted directed graph** with topic-specific edges. Use **Independent Cascade Model**:

1. Consumer purchases/reviews a trending product → "activates" on that topic
2. Each activated consumer has a probability of activating each neighbor (weighted by edge strength)
3. Propagation runs for K hops max per tick
4. Creates correlated SELECT bursts on same product rows (hotspot testing) → INSERT order waves (write burst testing)

### Q5: Supply chain topology — how complex?

**Layered DAG** (directed acyclic graph):

```
Raw materials (L0) → Components (L1) → Assemblies (L2) → Products (L3) → Sellers (L4)
```

Each edge: capacity, lead_time, cost, reliability. Configurable:
- **Fan-in** (how many suppliers feed one producer)
- **Fan-out** (how many buyers one supplier serves)
- **Depth** (number of layers)
- **Redundancy** (alternative paths)

For DB testing: creates **cross-tenant JOIN patterns** and **cascading UPDATE storms** during disruptions.

### Q6: Reproducibility mechanism

```yaml
simulation_config:
  random_seed: 42
  agent_profiles: {distribution_parameters}
  network_topology_seed: 7
  disruption_schedule:
    - {tick: 1000, type: "supplier_failure", target: "S-42"}
  trend_injections:
    - {tick: 500, topic: "eco-friendly", intensity: 0.8}
  time_config:
    ticks: 10000
    tick_duration: "1h"
```

Same config = same event stream = same DB workload. For LLM calls: cache responses keyed by input hash, or record decisions in event stream for replay without LLM.

### Q7: What entity-specific DB operations patterns emerge?

| Entity | OLTP Pattern | OLAP Pattern | Contention Profile |
|--------|-------------|-------------|-------------------|
| Consumer | Point reads (browse), single-row inserts (consumer_orders) | — | Low (distributed) |
| Seller | Inventory updates (hot rows), store_orders inserts | Sales reports | **High** (popular products) |
| Supplier | Batch production updates | Capacity planning queries | Medium (shared resources) |
| Transport | Append-only tracking events | Route analytics | Low |
| Government | — | Heavy aggregation, full scans | **Massive read load** |
| Cross-tenant (via Ch.2) | Causal chain: consumer_orders → store_orders → shipment → payment (3-4 ticks) | Cross-entity reads (gov) | **Critical for testing** |

---

## 5. Tension Analysis: Simulation Fidelity vs. Workload Predictability

### The Spectrum

```
Pure benchmark (TPC-C)                              Pure simulation (AgentSociety)
├── Fully deterministic                              ├── Emergent, unpredictable
├── Statistically characterized                      ├── Behaviorally rich
├── Reproducible by construction                     ├── Reproducible only via replay
├── Boring, uniform patterns                         ├── Realistic, diverse patterns
└── Known DB stress points                           └── Unknown DB stress points
```

### Resolution: The "Scenario" Abstraction

Support **three modes** through a scenario system:

**Mode 1 — Controlled Scenarios** (regression testing, benchmarking):
- Pre-defined event sequences exercising specific DB patterns
- "Black Friday": 10x consumer activity spike for 48 ticks
- "Supply chain disruption": cascade of supplier failures
- "New market entrant": seller with aggressive pricing
- Parameterized templates, fully reproducible, statistically characterizable

**Mode 2 — Free Simulation** (chaos testing, discovering unknown issues):
- Full agent autonomy, LLM-driven strategic decisions
- Social influence propagation creates emergent patterns
- Record event stream for post-hoc analysis
- If interesting pattern found → **extract into a Mode 1 scenario**

**Mode 3 — Hybrid** (the practical default):
- Rule-based agents provide baseline workload (predictable)
- Stochastic perturbations add realism (controlled randomness)
- Occasional LLM-driven strategic shifts (bounded unpredictability)
- Scenario injections at scheduled points (structured chaos)

### The Key Insight

The simulation doesn't need to be *predictable* — the **event stream** needs to be **replayable**:

```
Simulation (non-deterministic) → Event Stream (recorded) → Replay (deterministic)
                                        ↑
                           This is your artifact, not the simulation itself
```

---

## 6. Building Block Assessment

### Tier 1: Direct Building Blocks (Use Their Code/Patterns)

| Project | Use For | How |
|---------|---------|-----|
| **Mesa** | Agent framework skeleton | Scheduler, agent lifecycle, data collection. Extend with economic models. |
| **SimPy** | Supply chain & logistics layer | Model transport as processes with resources. Handles queuing naturally. |
| **go-tpc** | DB driver layer reference | Study how it maps TPC-C operations to TiDB. Workload translator follows same patterns. |
| **RetailSynth** | Consumer behavior models | Use statistical models for realistic purchase distributions, basket composition, price sensitivity. |

### Tier 2: Architecture Inspiration (Study, Don't Import)

| Project | Learn From |
|---------|-----------|
| **Stanford Generative Agents** | Memory/reflection/planning pattern for the small number of LLM-powered seller agents |
| **EconAgent** | LLM-driven macro decisions — apply to Government entity |
| **CompeteAI** | Game-theoretic framework for seller competition and pricing |
| **OASIS / AgentSociety** | Scaling to 1M agents. Key: most agents are stateless reaction machines. |
| **TPC-E data model** | Brokerage model closest to multi-entity economy. Schema inspiration. |
| **GreaterWMS** | Production-ready inventory/warehouse data structures |
| **abcEconomics** | Double-entry bookkeeping, economic agent abstractions |

### Tier 3: Reference Only

| Project | Why Reference Only |
|---------|-------------------|
| **Salesforce AI Economist** | RL-based policy optimization — interesting but orthogonal to DB testing goal |
| **HammerDB** | Pure load generation — use alongside for brute-force throughput testing |
| **OLTP-Bench** | Good benchmark harness but we need something more specific |
| **ASSUME** | Energy market specific, limited transferability |

---

## 7. Recommended Tech Stack

```
┌──────────────────────┬──────────────┬─────────────────────────────────────┐
│ Layer                │ Language     │ Rationale                           │
├──────────────────────┼──────────────┼─────────────────────────────────────┤
│ Simulation Engine    │ Python       │ Mesa + SimPy + NumPy ecosystem      │
│ Event Stream         │ Local Log    │ Protobuf events, ordered, replayable│
│ Workload Translator  │ Go           │ TiDB compatibility, performance     │
│ Database Driver      │ Go           │ Leverage go-tpc patterns, TiDB libs │
│ LLM Integration      │ Python       │ Async, with response caching        │
│ Configuration        │ YAML + CLI   │ Scenario definitions                │
│ Orchestration        │ Docker/K8s   │ Dev compose, scale on K8s           │
└──────────────────────┴──────────────┴─────────────────────────────────────┘
```

**Why split Python/Go**: Simulation is CPU-bound logic where Python's ecosystem dominates. DB driver needs raw performance and TiDB's Go ecosystem. Event stream bridges them cleanly.

---

## 8. Roadmap Sketch

| Phase | Scope | Estimate |
|-------|-------|----------|
| **MVP** | Core event stream + rule-based consumers/sellers + workload translator for purchase/browse | 3–4 weeks |
| **V1** | Full entity types + supply chain DAG + social propagation + scenario system | 4–6 weeks |
| **V2** | LLM agent integration (seller strategy, trend emergence) + Mode 2 free simulation | 3–4 weeks |
| **Production** | Scale testing + tuning + metrics dashboard + documentation | 2–3 weeks |

### Recommended First Milestone (Week 1):

1. Define the event protobuf schema (all economic event types)
2. Build minimal consumer + seller simulation (Mesa, 1000 agents, rule-based)
3. Build workload translator for just `consumer_browses` and `consumer_purchases`
4. Execute against TiDB and measure: are the operations realistic? diverse? interesting?
5. **If yes → expand. If no → rethink the simulation model before adding complexity.**

---

## Watch Out For

- **Scope creep toward economic realism**: This is a database testing tool, not an economics research platform. Every simulation feature must justify itself by the DB workload patterns it produces. If a feature doesn't create interesting DB operations, cut it.
- **LLM cost explosion**: At $0.01/call, 1000 calls/tick × 10,000 ticks = $100K/run. Budget LLM calls ruthlessly. Cache aggressively. Default to rule-based.
- **The "demo trap"**: The simulation will be visually impressive before the DB workload generation is useful. Resist spending time on visualization before the event-stream-to-SQL pipeline works end-to-end.
- **Over-engineering the simulation**: The event stream is the artifact. The simulation is disposable. Make the stream format excellent; the simulation can be crude initially.

---

## 9. Capacity Planning

### 9.0 Unit Economics: Per-Agent Database Operation Profiles

Before sizing, establish how many DB operations each agent type generates per simulation tick. Under the Tenant Write Sovereignty model (P4), a purchase is a multi-tick chain — the SQL stmts below count only each agent's **own** writes per tick, not the full chain.

| Agent Type | DB Ops/Tick | Operation Breakdown | Avg SQL Stmts/Op |
|------------|-------------|---------------------|-------------------|
| Consumer | 1.5 | 60% browse (SELECT), 25% purchase intent (1 INSERT consumer_orders + Ch.2 msg), 15% idle | 1.4 |
| Seller | 1.8 | 40% process PlaceOrder (1 SELECT + 1 INSERT + 1 UPDATE txn), 30% reprice (UPDATE), 30% idle | 1.5 |
| Supplier | 0.8 | 40% batch update (5 UPDATEs), 60% idle | 2.0 |
| Transport | 2.0 | 80% create shipment from ShipRequest (2 INSERTs), 20% status SELECT | 1.8 |
| Government | 0.5 | 30% agg query (heavy SELECT), 20% record OrderReport (INSERT), 50% idle | 0.5 |

**Typical agent mix**: 50% Consumer, 20% Seller, 10% Supplier, 10% Transport, 10% Government.

**Per-agent weighted average SQL stmts/tick**:
```
= 0.50×1.4 + 0.20×1.5 + 0.10×2.0 + 0.10×1.8 + 0.10×0.5
= 0.70 + 0.30 + 0.20 + 0.18 + 0.05
= 1.43 SQL stmts per agent per tick
```

**Inter-agent message volume** (Ch.2, in-memory only — zero DB cost):
```
Per purchase chain:  ~5 messages (PlaceOrder, OrderConfirmed, ShipRequest, Charge, OrderReport)
Purchase rate:       ~25% of 50% consumers = 12.5% of all agents per tick
Per 50K agents:      ~6,250 purchases/tick × 5 msgs = ~31,250 messages/tick
Memory cost:         31,250 × 200 bytes = ~6 MB/tick (drained every tick — negligible)
```

**Key insight**: The multi-tick purchase model doesn't reduce total QPS — it *redistributes* SQL stmts across agent types and ticks. In steady state, the pipeline is always full: while Consumer N sends a new PlaceOrder, Store is processing Consumer N-1's order, and Transport is shipping Consumer N-2's order. The per-tick SQL count is the same; it's just spread across more agents.

### 9.1 TiDB Cloud Tier Reference Specs

#### Essential Tier (Serverless)

| Parameter | Free | Paid (spending limit removed) |
|-----------|------|-------------------------------|
| Max connections | 400 | 5,000 |
| RU budget | 50M RUs/month | Scales with spend |
| Storage | 5 GiB (row) + 5 GiB (columnar) | Pay per GiB |
| Effective compute | ~1-2 vCPU equiv | ~4-8 vCPU equiv at peak |
| Idle timeout (AWS) | 340s | 340s |
| Max transaction duration | 30 min | 30 min |

#### Premium Tier (Dedicated)

| Parameter | Value |
|-----------|-------|
| TiDB node options | 8vCPU/16GB, 16vCPU/32GB, 16vCPU/64GB |
| TiKV node options | 8vCPU/64GB, 16vCPU/64GB (+ NVMe SSD) |
| PD nodes | 3 (standard) |
| Connections per TiDB node | 500–2,000 |
| Max tables proven | 3.2M (Atlassian case study) |
| Region size | 96 MB default |
| Regions per 1TB TiKV | ~10,000–12,000 |

#### TiDB Performance Per vCPU (Sysbench v8.1)

| Operation | QPS/vCPU |
|-----------|----------|
| Point SELECT | ~3,400 |
| Simple INSERT | ~1,300 |
| Non-index UPDATE | ~1,300 |
| Complex read/write TPS | ~100 |
| Aggregation (GROUP BY) | ~200 (estimate) |

**Blended QPS/vCPU** (for BizSim workload mix: 45% SELECT, 25% INSERT, 25% UPDATE, 5% Agg):
```
= 0.45×3,400 + 0.25×1,300 + 0.25×1,300 + 0.05×200
= 1,530 + 325 + 325 + 10
= 2,190 blended QPS/vCPU
```

---

### 9.2 Scenario 1: Maximum Scale — Single Node + TiDB Essential

**Setup**: MacBook Pro M2 Max 64GB (or one AWS EC2) → TiDB Cloud Essential (paid)

#### Simulation Side

**Agent count: 50,000** (sweet spot for single Mesa process with hybrid optimization)

| Type | Count | Memory Model | Per-Agent | Subtotal |
|------|-------|-------------|-----------|----------|
| Consumer | 25,000 | `__slots__` + beliefs + inbox | ~2.1 KB | 52.5 MB |
| Seller | 10,000 | `__slots__` + inbox | ~500 B | 5.0 MB |
| Supplier | 5,000 | Standard `__dict__` | ~1.8 KB | 9.0 MB |
| Transport | 5,000 | `__slots__` | ~200 B | 1.0 MB |
| Government | 5,000 | Standard `__dict__` | ~2.0 KB | 10.0 MB |

```
Agent memory:                77.5 MB
SimPy processes (50K×1.5KB): 75 MB
NetworkX graph:              175 MB  (50K nodes + 150K edges)
Python runtime/GC/buffers:   500 MB
────────────────────────────────────
Total simulation memory:     ~830 MB  ✅ Easily fits in 64 GB
```

**Tick rate**: With partial NumPy vectorization for consumers → **~15 ticks/sec** possible on M2 Max.

#### ⚠️ Bottleneck: TiDB Essential is the constraint, not simulation

TiDB Essential at ~4 vCPU equivalent:
```
4 vCPU × 2,190 blended QPS/vCPU × 0.80 efficiency = ~7,000 QPS sustained
```

**Working backwards**: To match 7,000 QPS:
```
Required: 7,000 ÷ 1.43 stmts/agent-tick = 4,895 agent-ticks/sec
With 50K agents: 4,895 ÷ 50,000 = 0.098 ticks/sec (1 tick every ~10 seconds)
```

This is perfectly reasonable — each tick = 1 simulated hour at 10-second real time.

#### QPS Breakdown

| Operation | Share | QPS |
|-----------|-------|-----|
| Point SELECT | 45% | 3,150 |
| INSERT | 25% | 1,750 |
| UPDATE | 25% | 1,750 |
| Aggregation SELECT | 5% | 350 |
| **Total** | | **7,000** |

#### Table Count & Data Volume

| Schema Layout | Tables |
|---------------|--------|
| Single economy (1 tenant) | ~10 tables |
| Multi-tenant (500 small economies, 100 agents each) | ~5,000 tables |

**Data growth** (steady state — purchase pipeline fully warm):
```
Purchase chains initiated per tick: 50,000 × 0.25 purchase_rate = ~12,500
Each chain produces ~8 rows across 4 ticks (consumer_orders, store_orders,
  inventory, shipments, tracking, transactions, gov_records, status_update)
In steady state: ~12,500 chains × 8 rows ÷ ~4 ticks = ~25,000 purchase rows/tick
+ browse/reprice/tracking overhead: ~25,000 additional rows/tick
Total: ~50,000 rows/tick
Avg row size: ~200 bytes
Per tick: ~10 MB
Per real hour at 0.1 tick/sec: 360 ticks → ~3.6 GB
```
⚠️ Essential free 5 GiB storage exhausted in ~1.5 hours. Paid storage required.

#### Workload Translator (Go)

```
7,000 QPS ÷ ~3ms avg latency = 21 concurrent connections
× 2 safety margin = ~40 connections
1 Go process, 2 cores, ~256 MB
```

#### AWS Alternative

**Recommended**: `c7g.2xlarge` (Graviton3, 8 vCPU, 16 GB, ~$0.29/hr)
- 1 core for Python sim, 2 cores for Go translator, rest for OS/buffers
- 16 GB more than sufficient (sim uses ~1 GB)

#### Scenario 1 Summary

| Component | Value |
|-----------|-------|
| **Agents** | 50,000 (25K consumer, 10K seller, 5K supplier, 5K transport, 5K gov) |
| **Sim memory** | ~830 MB |
| **Tick rate** | 0.1 ticks/sec (DB-constrained) |
| **Sustained QPS** | ~7,000 |
| **Connections** | ~40 |
| **Tables** | 10 (single tenant) to 5,000 (500 tenants) |
| **Data growth** | ~3.6 GB/hour |
| **Sim hardware** | 1 × MacBook M2 Max or 1 × c7g.2xlarge ($0.29/hr) |
| **Primary bottleneck** | TiDB Essential QPS / RU budget |

---

### 9.3 Scenario 2: Full Scale — 500K QPS / 1M Tables / <4,000 Connections

**Target**: TiDB Cloud Premium Tier (unlimited resources)

#### Step 1: TiDB Premium Cluster — Working Backwards from Targets

**500K QPS blended workload**:
```
500,000 ÷ 2,190 blended QPS/vCPU = 228 vCPUs needed
÷ 0.80 efficiency = 285 vCPUs
285 ÷ 16 vCPU/node = 18 TiDB nodes
```

**Cross-check**: `18 × 16 × 2,190 × 0.80 = 504,576 QPS ✓`

**Write throughput** (50% of 500K = 250K write QPS):
```
TiKV write capacity: ~17,500 QPS/node (8-16 vCPU)
250,000 ÷ 17,500 ÷ 0.80 = 18 TiKV nodes minimum (for throughput)
```

**1M tables — storage and regions**:

| Tenant Size | Count | Tables/Tenant | Agents/Tenant | Data/Tenant | Total Data |
|-------------|-------|---------------|---------------|-------------|------------|
| Large | 20 | 5,000 | 50,000 | 500 GB | 10 TB |
| Medium | 100 | 3,000 | 10,000 | 50 GB | 5 TB |
| Small | 500 | 1,000 | 1,000 | 5 GB | 2.5 TB |
| **Total** | **620** | **~1,000,000** | **~2.5M** | | **~17.5 TB** |

```
Table count: 20×5,000 + 100×3,000 + 500×1,000 = 100K + 300K + 500K + system tables ≈ 1M ✓
```

**TiKV storage**:
```
17.5 TB data × 3 replicas = 52.5 TB
+ 30% overhead (compaction, tombstones) = ~68 TB
÷ 4 TB NVMe per node = 17 nodes for storage
Combined with write throughput need → 24 TiKV nodes (covers both)
```

**Region count**:
```
Data regions: 17.5 TB ÷ 96 MB = ~186,000
Table minimum regions: ~1,000,000 (1 per table)
Total: ~1.1M regions → PD needs to be well-specced
```

**Connection budget** (includes dual-mode read path — see P8):
```
Target: <4,000
With identical-node architecture (10 nodes × ~107 connections each):
  Write pool:       10 × ~75 connections  = ~750
  Read pool (P8):   10 × ~32 connections  = ~320
  Total connections: ~1,070
  
  1,070 < 4,000 ✓✓ (73% headroom — room to scale to ~37 nodes before hitting limit)
  Per TiDB node: 1,070 ÷ 18 = ~59 connections each ✓
```

##### TiDB Premium Cluster Final Sizing

| Component | Spec | Count |
|-----------|------|-------|
| **TiDB** (query) | 16 vCPU / 32 GB | **18 nodes** |
| **TiKV** (storage) | 16 vCPU / 64 GB / 4 TB NVMe | **24 nodes** |
| **PD** (scheduling) | 8 vCPU / 16 GB | **3 nodes** |


<br/>

#### Step 2: Simulation Cluster — Identical Node, Horizontal Scale-Out

**Design principle**: Every simulation node is identical and fully self-contained. Each node runs its own tenants, its own Go workload translator, and connects directly to TiDB. **No centralized coordinator, no shared state, no redistribution on scale-out.** Adding capacity = start another identical node with a fresh batch of tenants.

**Why this works**: Tenants are the natural unit of isolation. No tenant spans multiple nodes. No cross-tenant simulation state exists (cross-tenant *DB operations* emerge from independent tenant actions hitting the same DB). Each node is oblivious to other nodes.

**Active agents needed to generate 500K QPS**:
```
Agent-ticks/sec = 500,000 ÷ 1.43 = ~350,000 agent-ticks/sec
```

**Not all 2.5M agents active simultaneously.** ~100 active tenants at varying tick rates:

| Tenant Size | Agents/Tenant | Tick Rate | QPS/Tenant | Active Count | Total QPS |
|-------------|---------------|-----------|------------|-------------|-----------|
| Large | 50,000 | 0.2 t/s | 14,300 | 10 | 143,000 |
| Medium | 10,000 | 0.5 t/s | 7,150 | 30 | 214,500 |
| Small | 1,000 | 2.0 t/s | 2,860 | 60 | 171,600 |
| **Total** | | | | **100 active** | **529,100 ✓** |

**Identical node spec** — `c7g.4xlarge` (16 vCPU, 32 GB, ~$0.58/hr):

```
Per node (with standard tenant mix: 1 large + 3 medium + 6 small):
  Mesa processes:      10 (1 per tenant, each running independently)
  Go translator:       1 (co-located, handles all local tenants)
  Active agents:       ~86K (50K + 30K + 6K)
  QPS output:          ~53K blended
  DB connections:      ~107 (75 write pool + 32 read pool — see P8)
  Memory:              ~10 GB sim + 1 GB Go + 5 GB OS/buffers = ~16 GB of 32 GB
  CPU:                 ~10 cores sim + 2 cores Go + overhead = ~14 of 16 vCPU
```

**Node count for 500K QPS target**:
```
500,000 ÷ 53,000 QPS/node = 9.4 → 10 identical nodes
```

**Tenant distribution** (assigned at deploy time via config, not coordinated at runtime):
```
Each node gets the SAME mix of tenant sizes — truly identical and interchangeable.

Example with 10 identical nodes, each running:
  1 large tenant    (50K agents,  ~14,300 QPS)
  3 medium tenants  (30K agents,  ~21,450 QPS)
  6 small tenants   (6K agents,   ~17,160 QPS)
  ─────────────────────────────────────────────
  Per node total:   86K agents,   ~52,910 QPS

Cluster total:  10 nodes × 52,910 = ~529K QPS ✓
               10 × 86K = 860K active agents
               10 × 10 tenants = 100 active tenants
```

Any node can be replaced by a fresh identical node with the same config template.
New tenants? Start a new node with the same mix — or any mix that fits the per-node resource budget.

**Scaling is trivial**:
```
Want 250K QPS?  → 5 nodes
Want 500K QPS?  → 10 nodes
Want 750K QPS?  → 15 nodes  (add 5 nodes with new tenants, zero changes to existing)
Want to test?   → 1 node    (same binary, same config structure, just fewer tenants)
```

#### Step 3: Event Stream

Each node uses a **local in-process event channel** (Go channel or Unix pipe) between its Mesa processes and its Go translator. No shared Kafka cluster required for the core data path.

**Local disk event log for replay**: The Go translator asynchronously batch-writes all events to a local append-only log file (protobuf or line-delimited JSON) on the node's SSD or EBS volume. This is cheap — simulation nodes have idle disk I/O since the workload is CPU-bound and network-bound (to TiDB).

```
Core path (per node):
  Mesa processes → local pipe → Go translator → TiDB
                                     │
                                     └→ async batch write → local disk event log
```

**Disk I/O budget per node**:
```
~53K events/sec × 500 bytes avg = ~26 MB/sec sustained writes
Batch interval: 100ms (flush every 100ms or 5K events, whichever first)
Effective I/O:  ~260 KB per write syscall → trivial for any SSD
gp3 EBS (3,000 baseline IOPS, 125 MB/sec): uses <1% IOPS, ~21% throughput
Local NVMe SSD: uses <0.1% capacity

Storage per node per hour:
  26 MB/sec × 3,600 = ~94 GB/hour (uncompressed)
  With zstd streaming compression (~5:1 for structured events): ~19 GB/hour
  1 TB EBS gp3 → ~52 hours of continuous recording before rotation
```

**Replay**: To replay a simulation run against a different DB config, feed the local log files into standalone Go translator instances — no live simulation needed. Logs from multiple nodes can be collected to S3 for centralized replay or archival.

```
Replay path:    S3 (or local disk) → Go translator (replay mode) → TiDB (new config)
Collection:     Node local log → async upload to S3 (cron or on rotation)
```

**Why this replaces Kafka for most use cases**:
- No additional infrastructure to deploy or manage
- Each node's log is self-contained — no ordering dependencies across nodes
- Replay doesn't require the simulation cluster to be running
- S3 collection gives centralized access when needed, without critical-path coupling

#### Step 4: Workload Translator (Go) — Per-Node

Each node runs exactly **one Go translator process** that:
- Reads events from all local Mesa processes via local pipes
- Maintains its own TiDB connection pool
- Batches and executes SQL independently

```
Per node:
  QPS handled:      ~53K
  Write pool:       ~75 connections (action events → INSERT/UPDATE)
  Read pool:        ~32 connections (query pipeline → SELECT, see P8)
  Total connections: ~107
  Active goroutines: ~200 (150 write + 50 read)
  Memory:           ~1 GB
  Batching:         200-row INSERT batches for append-only tables
                    Individual statements for transactional operations

Total across 10 nodes:
  Connections:      10 × 107 = ~1,070 (< 4,000 limit ✓✓)
  QPS:              10 × 53K = ~530K (headroom above 500K target ✓)
```

#### Full Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│              SIMULATION CLUSTER (Identical Nodes)                       │
│                                                                         │
│  10 × c7g.4xlarge (16 vCPU, 32 GB each) — all identical                 │
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐       ┌──────────────────┐  │
│  │ Node 1           │  │ Node 2           │  ...  │ Node 10          │  │
│  │ ┌──────────────┐ │  │ ┌──────────────┐ │       │ ┌──────────────┐ │  │
│  │ │ Mesa procs×8 │ │  │ │ Mesa procs×8 │ │       │ │ Mesa procs×8 │ │  │
│  │ │ (tenants)    │ │  │ │ (tenants)    │ │       │ │ (tenants)    │ │  │
│  │ └──────┬───────┘ │  │ └──────┬───────┘ │       │ └──────┬───────┘ │  │
│  │        │local    │  │        │local    │       │        │local    │  │
│  │ ┌──────▼───────┐ │  │ ┌──────▼───────┐ │       │ ┌──────▼───────┐ │  │
│  │ │ Go translator│ │  │ │ Go translator│ │       │ │ Go translator│ │  │
│  │ │(~107 conns)  │ │  │ │(~107 conns)  │ │       │ │(~107 conns)  │ │  │
│  │ └──────┬───────┘ │  │ └──────┬───────┘ │       │ └──────┬───────┘ │  │
│  └────────┼─────────┘  └────────┼─────────┘       └────────┼─────────┘  │
│           └─────────────────────┼──────────────────────────┘            │
└─────────────────────────────────┼───────────────────────────────────────┘
                                  │
                                  ▼ ~1,070 connections total
┌─────────────────────────────────────────────────────────────┐
│                TiDB Cloud Premium                           │
│                                                             │
│  PD:   3 × 8vCPU/16GB  (managing ~1.1M regions)             │
│                                                             │
│  TiDB: 18 × 16vCPU/32GB                                     │
│    → 504K blended QPS capacity                              │
│    → ~59 connections per TiDB node                          │
│                                                             │
│  TiKV: 24 × 16vCPU/64GB/4TB NVMe                            │
│    → 336K write QPS capacity                                │
│    → 96 TB raw storage (17.5 TB × 3 replicas + overhead)    │
│    → ~1.1M regions                                          │
│                                                             │
│  Tables: ~1,000,000 across 620 databases/schemas            │
│  Connections: ~1,070 active (< 4,000 limit ✓✓)              │
└─────────────────────────────────────────────────────────────┘

Scaling: Want more QPS? Add identical nodes. No redistribution needed.

┌──────────┐  ┌──────────┐  ┌──────────┐
│ Node 11  │  │ Node 12  │  │ Node N   │  ← just start more
│ (new     │  │ (new     │  │          │
│ tenants) │  │ tenants) │  │          │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     └─────────────┼─────────────┘
                   ▼
            Same TiDB cluster
```

#### Scenario 2 Summary

| Component | Metric | Value |
|-----------|--------|-------|
| **Simulation** | | |
| | Total agents (all tenants) | ~2.5M |
| | Active agents (generating QPS) | ~860K |
| | Active tenants | 100 of 620 |
| | Node type | c7g.4xlarge (16 vCPU, 32 GB) — **all identical** |
| | Node count | **10** (scale-out: add more for more QPS) |
| | Per-node QPS | ~53K blended |
| | Per-node connections | ~107 (75 write + 32 read) |
| | Per-node memory used | ~16 GB of 32 GB |
| **Event Stream** | | |
| | Events/sec | ~350,000 (across all nodes) |
| | SQL expansion | ×1.43 → 530K QPS |
| | Inter-node coordination | **None** — each node is independent |
| | Event log (per node) | Local disk, async batch write, ~26 MB/sec (~19 GB/hr compressed) |
| | Replay | From local logs or S3 — no live sim needed |
| **Workload Translator** | | |
| | Go processes | 10 (one per node, co-located) |
| | Connections per node | ~107 (75 write + 32 read) |
| | Total connections | **~1,070** (< 4,000 ✓✓) |
| **TiDB Premium** | | |
| | TiDB nodes | **18 × 16vCPU/32GB** |
| | TiKV nodes | **24 × 16vCPU/64GB/4TB NVMe** |
| | PD nodes | **3 × 8vCPU/16GB** |
| | Sustained QPS | **~529K** (blended) |
| | QPS breakdown | 240K SELECT, 145K INSERT, 120K UPDATE, 25K Agg |
| | Tables | **~1,000,000** |
| | Databases/schemas | 620 |
| | Data volume (steady state) | ~17.5 TB |
| | Regions | ~1.1M |
| | Connections used | **~1,070** |
| **Scale-Out** | | |
| | To add ~53K QPS | Add 1 identical node + assign same tenant mix |
| | To double capacity | 10 → 20 nodes, zero changes to existing nodes |
| | Min viable cluster | 1 node (~53K QPS, for dev/test) |

---

### 9.4 Bottleneck Analysis

| Rank | Scenario 1 | Scenario 2 |
|------|-----------|-----------|
| 1 | **TiDB Essential QPS/RU budget** — hard wall at ~7K QPS | **TiKV write throughput** — 250K write QPS needs 24 nodes |
| 2 | Storage (5 GiB free burns in ~1.5 hr) | **PD region scheduling** — 1.1M regions requires monitoring PD CPU |
| 3 | Mesa single-thread (not hit at 0.1 t/s) | **TiDB connection headroom** — 1,070 of 4,000 used; generous but monitor at scale |
| 4 | — | **Per-node CPU saturation** — 10 Mesa + 1 Go on 16 vCPU; ~88% utilized |

Note: Scenario 2 bottlenecks are now entirely on the DB side, not simulation coordination. The sim cluster has no single point of failure and no shared state to bottleneck.

### 9.5 Escalation Triggers

| Trigger | Action |
|---------|--------|
| Essential tier RU cost > $200/month | Jump to Premium with 2 × 8vCPU TiDB nodes (~44K QPS headroom) |
| PD can't handle 1.1M regions | Switch to table partitioning (logical separation via partition keys) — reduces to ~50K regions |
| Single node CPU saturated | **Add another identical node** — assign new or migrated tenants (no redistribution of existing) |
| Mesa can't sustain tick rates | Move hot-path consumer logic to Cython/Rust extension — expect 5–10x speedup per node |
| Need > 500K QPS | **Add sim nodes** (linear scaling) + add TiDB nodes — each sim node adds ~53K QPS, each TiDB 16vCPU node adds ~28K blended QPS |
| Connection count approaching 4,000 | Reduce per-node pool size (currently ~107, can shrink to ~60 with aggressive batching) or add TiDB nodes |

### 9.6 Cost Estimates

#### Scenario 1: Single Node Dev

| Item | Monthly Cost |
|------|-------------|
| MacBook M2 Max (owned) | $0 |
| *or* AWS c7g.2xlarge (on-demand, 24/7) | ~$210 |
| TiDB Essential (paid, ~$50 RU budget) | ~$50–100 |
| **Total** | **$50–310/month** |

#### Scenario 2: Full Scale Production

| Item | Spec | Monthly Cost (est.) |
|------|------|-------------------|
| Sim cluster | 10 × c7g.4xlarge (on-demand) | ~$4,200 |
| Sim cluster (spot, 60% savings) | 10 × c7g.4xlarge | ~$1,680 |
| EBS gp3 (event logs) | 10 × 1 TB gp3 | ~$800 |
| S3 (log archival) | ~50 TB/month | ~$1,150 |
| TiDB Premium (18 TiDB + 24 TiKV + 3 PD) | 45 nodes total | ~$25,000–40,000* |
| **Total (on-demand)** | | **~$31,000–46,000/month** |
| **Total (spot sim + reserved DB)** | | **~$21,000–31,000/month** |

*TiDB Cloud Premium pricing varies by region and commitment tier. Contact PingCAP for exact quotes.*

---

## Appendix A: Key Researchers & Labs

| Researcher / Lab | Affiliation | Focus |
|-----------------|-------------|-------|
| Joon Sung Park | Stanford HCI | Creator of Generative Agents architecture |
| Percy Liang | Stanford CRFM | Foundation model evaluation/safety |
| Tsinghua FIB-Lab | Tsinghua University | Large-scale urban + economic simulation (AgentSociety, EconAgent) |
| CAMEL-AI | Multi-institutional | OASIS, multi-agent coordination |
| Microsoft Research | Microsoft | CompeteAI, MarS, Magentic-Marketplace |
| Salesforce Research | Salesforce | AI Economist (RL economic policy) |

---

## Appendix B: Landscape — Existing Open Source Projects & Research

### B.1 Agent-Based Economic Simulation Frameworks

| Project | URL | Stars | Key Strength | Relevance |
|---------|-----|-------|--------------|-----------|
| **Mesa** | [projectmesa/mesa](https://github.com/projectmesa/mesa) | 3,552 | Industry-standard Python ABM framework. Scheduler, spatial grids, data collection. v3.5 adds discrete-event scheduling. | **Core building block** — simulation engine foundation |
| **abcEconomics (ABCE)** | [AB-CE/abce](https://github.com/DavoudTaghawiNejad/abce) | 12 | Purpose-built for Agent-Based Computational Economics. Double-entry bookkeeping, firm/household interactions. | **Architecture reference** — economic domain abstractions |
| **Salesforce AI Economist** | [salesforce/ai-economist](https://github.com/salesforce/ai-economist) | 1,200+ | RL-based economic policy optimization. Models agents + government with taxation. | **Inspiration** — government agent design |
| **OmniEcon Nexus** | [vinhatson/global-microeconomic-simulation-engine](https://github.com/vinhatson/global-microeconomic-simulation-engine) | — | High-performance engine claiming up to 5M agents for micro/macro forecasting. Deep learning + ABM. | **Scale reference** — massive agent counts |
| **ASSUME** | [assume-framework/assume](https://github.com/assume-framework/assume) | 79 | Agent-based market evolution. Market mechanism design and actor behavior evolution. | **Inspiration** — market mechanism patterns |

### B.2 LLM-Driven Economic Agent Research

| Project/Paper | URL | Date | Key Innovation |
|---------------|-----|------|----------------|
| **EconAgent** (Tsinghua FIB-Lab) | [tsinghua-fib-lab/ACL24-EconAgent](https://github.com/tsinghua-fib-lab/ACL24-EconAgent) | 2024 | LLM agents for macroeconomic activities. "Perception-decision-action" loop reacting to economic signals. |
| **CompeteAI** (Microsoft) | [microsoft/competeai](https://github.com/microsoft/competeai) | ICML 2024 | LLM agents in market competition scenarios (restaurant pricing wars, etc.). |
| **Magentic-Marketplace** (Microsoft) | [microsoft/multi-agent-marketplace](https://github.com/microsoft/multi-agent-marketplace) | 2025 | Simulates agentic markets to observe emergent evolution. 147 stars. |
| **MarS** (Microsoft) | [microsoft/MarS](https://github.com/microsoft/MarS) | 2025 | Financial market simulation via Generative Foundation Models. 1,680 stars. |
| **Shall We Team Up** | [wuzengqing001225/sabm_shallweteamup](https://github.com/wuzengqing001225/sabm_shallweteamup) | 2024 | Spontaneous cooperation/cartel formation among competing LLM agents. |
| **LLM Economist** | [arXiv:2507.15815](https://arxiv.org/abs/2507.15815) | Jul 2025 | Multi-agent generative simulacra for economic mechanism design. |
| *Large LLMs as Simulated Economic Agents* | [arXiv:2301.07543](https://arxiv.org/abs/2301.07543) | 2023/2026 | Foundational study: LLMs as "Homo Silicus" — they replicate human economic biases. |
| **LLM-Based Multi-Agent Marketing Sim** | [arXiv:2510.18155](https://arxiv.org/html/2510.18155v1) | Oct 2025 | Multi-agent simulation of marketing and consumer behavior. |
| **Percepta** | [extradimen.github.io/Percepta](https://extradimen.github.io/Percepta/) | 2025 | Extensible multi-agent economic world simulation framework. |

### B.3 Social Simulation & Influence Propagation

| Project | URL | Key Strength |
|---------|-----|--------------|
| **Stanford Generative Agents** ("Smallville") | [joonspk-research/generative_agents](https://github.com/joonspk-research/generative_agents) | Seminal memory/reflection/planning architecture. 25 agents in a sandbox town. |
| **AgentSociety** (Tsinghua FIB-Lab) | [tsinghua-fib-lab/AgentSociety](https://github.com/tsinghua-fib-lab/agentsociety) | Large-scale (up to 1M agents) urban social simulation. Distributed microkernel architecture. |
| **OASIS** (CAMEL-AI) | [camel-ai/oasis](https://github.com/camel-ai/oasis) | 1M agent social interaction sim. Social media dynamics, information diffusion. |
| **YSocial** | [ysocialtwin/ysocial](https://github.com/ysocialtwin/ysocial) | AI-driven social media simulator. LLM-backed agents for trend cascades. |
| **HiSim** | [xymou/HiSim](https://github.com/xymou/HiSim) | Hybrid framework for large-scale social media behavior simulation. |
| **SocioVerse** (Fudan DISC) | [FudanDISC/SocioVerse](https://github.com/FudanDISC/SocioVerse) | Social-psychological aspects: personality stability, group dynamics. 10M real user pool. |
| **FashionNetworkSims** | [Gholtes/fashionNetworkSims](https://github.com/Gholtes/fashionNetworkSims) | Agent-based model of fashion trend propagation in social networks. |
| *Emergence of Social Norms in Generative Agent Societies* | [IJCAI 2024](https://www.ijcai.org/proceedings/2024/0874.pdf) | How social norms emerge spontaneously from agent-to-agent interactions. |

### B.4 Supply Chain & Logistics Simulation

| Project | URL | Key Strength |
|---------|-----|--------------|
| **SimPy** | [simpy/simpy](https://github.com/simpy/simpy) | Gold standard for process-based discrete event simulation in Python. |
| **OpenCLSim** (TU Delft) | [TUDelft-CITG/openclsim](https://github.com/TUDelft-CITG/openclsim) | SimPy-based rule-driven scheduling for cyclic logistics processes. |
| **SupplyNetPy** | [PyPI](https://pypi.org/project/supplynetpy/) | Multi-echelon inventory and supply chain simulation (v0.1.6, 2025). |
| **SupplyChainAgent** | [HIT-ICES/SupplyChainAgent](https://github.com/HIT-ICES/SupplyChainAgent) | Hybrid Python/TypeScript for multi-tier supply chain agent simulation. |
| **Amazon supply-chain-sim** | [amzn/supply-chain-simulation-environment](https://github.com/amzn/supply-chain-simulation-environment) | Enterprise-grade supply chain simulation environment. |
| **GreaterWMS** | [GreaterWMS/GreaterWMS](https://github.com/GreaterWMS/GreaterWMS) | 4,270 stars. Production WMS based on Ford Asia Pacific logistics. Real inventory/supplier structures. |
| **Beer Distribution Game** | [TomLaMantia/SupplyChainSimulation](https://github.com/TomLaMantia/SupplyChainSimulation) | Classic MIT supply chain coordination simulation. Bullwhip effect modeling. |
| **Stockpyl** | [stockpyl.readthedocs.io](https://stockpyl.readthedocs.io/) | Multi-product inventory and replenishment simulation. |

### B.5 Database Benchmarks & Workload Generators

| Project | URL | Key Strength |
|---------|-----|--------------|
| **TPC-C** | [TPC spec](https://www.tpc.org/tpcc/) | OLTP benchmark: warehouse/district/customer hierarchy. 5 transaction types. Tests contention and data locality. |
| **TPC-E** | [TPC spec](https://www.tpc.org/tpce/) | Brokerage model: 33 tables, 10 tx types. Non-uniform distributions from real market data. |
| **TPC-DS** | [TPC spec](https://www.tpc.org/tpcds/) | Decision support: 24 tables, 99 queries. Multi-channel retail with ETL tasks. |
| **go-tpc** | [pingcap/go-tpc](https://github.com/pingcap/go-tpc) | TiDB's Go implementation of TPC-C and TPC-H. |
| **BenchmarkSQL** | [benchmarksql/benchmarksql](https://github.com/benchmarksql/benchmarksql) | Java-based TPC-C implementation. |
| **OLTP-Bench** | [CMU paper](https://www.cs.cmu.edu/~pavlo/static/papers/oltpbench-vldb.pdf) | Extensible multi-DB benchmark testbed (CMU). |
| **HammerDB** | [TPC-Council/HammerDB](https://github.com/TPC-Council/HammerDB) | 742 stars. Database load testing tool with TPC-C/TPC-H support. |
| **Lauca** | [luyiqu/Lauca](https://github.com/luyiqu/Lauca) | Learns and synthesizes OLTP workload patterns from real traces. High fidelity. |
| **RetailSynth** | [arXiv:2312.14095](https://arxiv.org/abs/2312.14095) | Generates synthetic retail transaction data from agent-based shopper models. |
| **ACES** | [mycustomai/ACES](https://github.com/mycustomai/ACES) | AI agents shopping in e-commerce sandbox — generates full-stack DB traffic. |
| **MTD-DS** | [hal-04312262](https://hal.science/hal-04312262v2) | SLA-aware decision support benchmark for multi-tenant parallel DBs. |
| **LDBC FinBench** | [ldbc/ldbc_finbench_docs](https://github.com/ldbc/ldbc_finbench_docs) | Financial benchmark specification for graph/relational databases. |
| **Swingbench** | [domgiles/swingbench-public](https://github.com/domgiles/swingbench-public) | Updated TPC-C/E generator for modern RDBMS. |
| **pgEdge LoadGen** | [pgEdge/pgedge-loadgen](https://github.com/pgEdge/pgedge-loadgen) | Go-based realistic PostgreSQL workload simulation. High-concurrency OLTP. |
| **Datasynth-Generators** | [Crates.io](https://crates.io/crates/datasynth-generators) | Rust-based financial event log and journal entry generator. |

### B.6 Key Academic Papers (Survey)

| Paper | URL | Relevance |
|-------|-----|-----------|
| *LLMs empowered ABM: a survey and perspectives* | [Nature HSSCOMM](https://www.nature.com/articles/s41599-024-03611-3) | Comprehensive 2024 survey of LLM + agent-based modeling across economics and social science |
| *LLM-Driven Multi-Agent for Coupled Epidemic-Economic Dynamics* | [MDPI](https://www.mdpi.com/2078-2489/17/3/259) | Multi-agent framework coupling health and economic simulation |
| *Redbench: Workload Synthesis From Cloud Traces* | [arXiv:2511.13059](https://arxiv.org/html/2511.13059v1) | Synthesizing database workloads from production traces |
| *Benchmarking Multi-Tenant Architectures in PostgreSQL* | [EDBT 2026](https://openproceedings.org/2026/conf/edbt/paper-172.pdf) | Multi-tenant database benchmarking methodology |
| *MulTe: Multi-Tenancy Database Benchmark Framework* | [TU Dresden](https://tud.qucosa.de/api/qucosa%3A83087/attachment/ATT-0/) | Framework for benchmarking multi-tenant databases |

---

*Document generated: 2026-03-28*
*Sources: 4 parallel librarian research agents + 2 Oracle architecture consultations + direct web/GitHub search*
*Last revision: Systematic rewrite for Tenant Write Sovereignty + inter-agent message protocol*
