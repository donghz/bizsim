# System Architecture — BizSim V1

> Synthesized from: vision.md P1 (lines 174–262), P2 (264–277), P3 (279–307), P4 (309–398), P5 (351–408), P8 (486–927)

## Overview Diagram

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

## Three Channels

| Channel | Direction | What flows | Crosses translator? | Touches DB? |
| :--- | :--- | :--- | :--- | :--- |
| **Ch.1: Action Events** | Agent → Translator → TiDB | Domain events (`order_accepted`, `shipment_created`) | Yes — translated to SQL | Yes — INSERT/UPDATE to agent's **own** tenant |
| **Ch.2: Inter-Agent Messages** | Agent → Agent (via inbox) | Domain requests (`PlaceOrder`, `ShipRequest`, `Charge`) | **No** — stays inside simulation | **No** — pure in-memory |
| **Ch.3: Query Requests** | Agent → Translator → TiDB → Agent | Domain questions + reduced answers | Yes — translated to SQL, results reduced | Yes — SELECT from agent's **own** tenant |

## Bidirectional DB Contract

The translator mediates two DB-facing data flows, translating between domain concepts and SQL in both directions:

*   **Outbound — Ch.1 (agent → DB)**: Agents emit domain events. The translator maps each event to SQL statements (schema-aware, tenant-aware) with correlated reads and transaction boundaries. Each event targets only the emitting agent's own tenant.
*   **Inbound — Ch.3 (DB → agent)**: Agents request domain answers. The translator turns these into SQL queries, executes them against TiDB, and reduces the result set to a small, fixed-size domain answer. Raw rows never cross the boundary.

## What the Translator Encapsulates vs Must NOT Do

### The Translator Encapsulates (Agents Must NOT Know)
*   **Schema**: Table names, column names, indexes, partitioning strategy.
*   **Tenant mapping**: Which schema/database a tenant maps to, key prefixes, routing.
*   **SQL dialect**: TiDB-specific syntax, optimizer hints, batch sizes.
*   **Result cardinality**: The translator reduces potentially large result sets to O(1) domain metrics.
*   **Connection management**: Pools, timeouts, retries, read/write pool separation.

### What the Translator Must NOT Do (Simulation Responsibility)
*   Agent decision logic (buy/sell/cancel).
*   Simulation state management (agent memory, beliefs).
*   Inter-agent communication (Channel 2 is invisible to the translator).
*   Interpreting domain answer meaning (the agent decides what a 4% unemployment rate means).

## Agent Intelligence Tiers

| Agent Type | Count | Intelligence Model | Rationale |
| :--- | :--- | :--- | :--- |
| **Consumer** | 100K–1M | **Rule-based** + statistical profiles + social influence | Volume matters. Use demographics + noise + network effects. |
| **Seller** | 100–10K | **Hybrid**: rules for routine + occasional LLM for strategy | Pricing, marketing decisions. LLM only for strategic pivots. |
| **Supplier** | 50–5K | **Rule-based** + stochastic disruption injection | Production capacity, lead times, quality. |
| **Transport** | 10–500 | **Discrete event / queue-based** (SimPy) | Routes, capacity, delays. Physics + queuing models. |
| **Government** | 1 | **Aggregate statistics** + policy rules | Reads everything, writes policy changes. Pure computation. |

**Not agents in V1**: Community influence is a simulation engine subsystem (graph diffusion model, not an agent). Payment is handled as direct bookkeeping within the purchase pipeline (no separate payment agent).

## Tick Loop

The simulation uses discrete ticks with configurable duration. Every tick follows this 7-step sequence:

1.  **Drain inboxes**: Each agent processes inter-agent messages (Ch.2) and query results (Ch.3) that arrived since the last tick.
2.  **Process external events**: Handle disruptions, policy changes, or trend injections.
3.  **Run agent decision cycles**: Consumers browse/buy, sellers reprice, suppliers produce. Decisions are influenced by inbox contents.
4.  **Advance transport/logistics state machines**: Update shipment positions and tracking.
5.  **Compute community influence propagation**: Batched social network diffusion.
6.  **Government aggregation**: Analytical computation (runs every N ticks).
7.  **Emit action events (Ch.1) and inter-agent messages (Ch.2)**: 
    *   Ch.1 events go to the Go translator for DB writes.
    *   Ch.2 messages are appended to target agents' inboxes (available next tick).
    *   Ch.3 query requests go to the Go translator for async DB reads.

## Tick Ordering and Reproducibility

*   **Determinism**: The same random seed combined with the same tick sequence produces an identical event stream.
*   **Message Order**: Inter-agent message delivery order within a single tick is deterministic (sorted by sender ID).
*   **V2 Evolution**: The architecture supports variable tick resolution (e.g., hourly for normal operations, minute-level for stress testing).

## Multi-Tenancy and Tenant Write Sovereignty

The economic ecosystem maps naturally to multi-tenant schemas:

| Tenant Type | Simulation Entity | DB Access Pattern |
| :--- | :--- | :--- |
| **Consumer App** | Community platform | High-write social |
| **Individual Store** | Seller | Per-tenant schema/database |
| **Logistics Provider** | Transport company | Separate tenant, append-heavy |
| **Government/analytics** | Government entity | Read-heavy analytical |
| **Supplier ERP** | Supplier group | Mixed OLTP |
| **Payment Ledger** | Financial service | Strict transactional |

### Tenant Write Sovereignty Rule
**An agent only writes to tables owned by its own tenant. No exceptions.**

Cross-tenant effects happen via **inter-agent messages** (Channel 2). When a consumer buys from a store, the consumer sends a `PlaceOrder` message. The store processes it next tick and writes to its own tables.

*   **Correct Pattern**: Consumer agent → Message(to=store_003, PlaceOrder) → Store agent → INSERT INTO store_003.store_orders.
*   **Anti-Pattern**: Consumer agent → INSERT INTO store_003.store_orders.

**Government Read Exception**: Government agents may read across all tenants via Channel 3 query requests to generate analytical pressure. However, they only write to their own tenant tables (`gov_records`, `statistics`).

## Domain-First Schema

| Tenant Type | Tables Owned |
| :--- | :--- |
| **Consumer App** | `consumer_profiles`, `consumer_orders` (intents), `consumer_reviews` |
| **Individual Store** | `catalog`, `inventory`, `store_orders` (authoritative), `store_pricing`, `store_reviews` |
| **Supplier ERP** | `suppliers`, `supply_chain_edges`, `purchase_orders` |
| **Logistics Provider** | `shipments`, `tracking_events` |
| **Social Graph** | `community_posts`, `influence_edges` |
| **Payment Ledger** | `transactions` (double-entry bookkeeping) |
| **Government** | `gov_records`, `statistics` |

**Key design decision**: `consumer_orders` ≠ `store_orders`. The consumer records "I want to buy X" in their own tenant. The store records "I accepted/rejected order for X" in its own tenant. The two records are linked by an `order_request_id` carried in the Ch.2 `PlaceOrder` message. This dual-record pattern preserves Tenant Write Sovereignty and doubles write diversity for DB testing.

## Dual-Mode Read Path

The simulation employs two complementary modes to produce a realistic read workload.

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

### Mode 1: Action-Correlated Reads
When an agent takes an action, the translator fires the SELECTs that would logically precede the write (e.g., browse catalog before buying). The results are consumed in full by the translator and then discarded. This simulates hot-path transactional pressure.

### Mode 2: Async Query Pipeline
Agents periodically request domain answers about historical data (e.g., "what are my recent orders?"). The translator executes the SQL, reduces the result to a small domain struct, and delivers it to the agent's inbox in a future tick.

### Comparison Table

| Feature | Mode 1: Action-Correlated | Mode 2: Query Pipeline |
| :--- | :--- | :--- |
| **Purpose** | Hot-path transactional reads | Historical lookups, status checks, analytics |
| **Timing** | Synchronous with write | Async (arrival in future tick) |
| **Results used?** | Discarded by translator | Reduced to domain struct for agent |
| **Data accessed** | Current catalog, prices, inventory | Historical orders, shipments, aggregates |
| **DB test value** | Read-write transaction patterns | Read-After-Write isolation, secondary indexes |

### Constraints and Budgets
*   **QUERY_COOLDOWNS**: Agents do not query every tick. Cooldowns range from 20 ticks (shipment tracking) to 100 ticks (sales analytics).
*   **Inbox Memory**: Negligible budget (~200 bytes per item). Drained every tick.
*   **V2 Evolution**: Future hooks include policy feedback loops where government agents adjust tax/interest rates based on analytical query results.

## Cross-References

*   For message types and definitions, see **MESSAGES.md**.
*   For event types and Ch.1 envelopes, see **EVENTS.md**.
*   For query templates and SQL reduction details, see **QUERIES.md**.
*   For Go translator implementation and guardrails, see **GO_TRANSLATOR.md**.
*   For Python contracts and dataclass definitions, see **CONTRACTS.md**.
