# Agent Base — Scheduling, Inbox, Correlation, Failure Handling

> Extracted from: agent-behavior.md §4 (lines 884–966) + §7 (lines 1397–1451)
> Cross-references: MESSAGES.md, EVENTS.md, QUERIES.md

## 1. Action Scheduling Configuration

### Design

A centralized YAML config file defines the recurring cycle for each autonomous agent action. The simulation scheduler checks each tick: for each agent, for each of its recurring actions, if `last_executed_tick + cycle_ticks + jitter_offset <= current_tick`, the action fires.

**Jitter** prevents synchronized bursts: each agent draws a random offset from `[-jitter, +jitter]` at initialization, fixed for the simulation run (deterministic with seed).

Only **autonomous** actions (self-initiated by the agent) are scheduled here. **Reactive** actions (triggered by inbox messages) fire immediately when the message is processed during inbox drain.

Note: The community subsystem (see COMMUNITY.md) is NOT scheduled via this mechanism. It runs as tick loop step 4, after all agent actions complete, and before events are emitted (step 6). See ARCHITECTURE.md for the full tick loop.

### Configuration Schema

```yaml
# bizsim_scheduling.yaml
#
# cycle_ticks: base period between action firings
# jitter: random offset range drawn per-agent at init (±jitter ticks)
# Notes: 1 tick = 1 simulated hour (configurable in sim_config)

scheduling:
  consumer:
    browse_catalog:
      cycle_ticks: 10          # browse every ~10 ticks (10 simulated hours)
      jitter: 3                # actual period: 7-13 ticks per consumer
    query_order_history:
      cycle_ticks: 50          # check order history every ~50 ticks
      jitter: 10

  seller:
    evaluate_pricing:
      cycle_ticks: 100         # pricing review every ~100 ticks (~4 sim days)
      jitter: 20
    evaluate_inventory:
      cycle_ticks: 60          # inventory review every ~60 ticks (~2.5 sim days)
      jitter: 15

  supplier:
    produce_goods:
      cycle_ticks: 24          # daily production update
      jitter: 0                # no jitter — production runs on schedule
    query_fulfillment_status:
      cycle_ticks: 48          # check fulfillment every ~2 sim days
      jitter: 10

  transport:
    update_tracking:
      cycle_ticks: 1           # tracking updates every tick for active shipments
      jitter: 0

  government:
    compute_statistics:
      cycle_ticks: 168         # weekly statistics computation (~7 sim days)
      jitter: 0                # government runs on fixed schedule
```

### Scheduler Algorithm

```
for each tick T:
    for each agent A:
        for each recurring action R of A's type:
            if A.last_fired[R] + R.cycle_ticks + A.jitter_offset[R] <= T:
                A.queue_action(R)
                A.last_fired[R] = T
```

The jitter offset `A.jitter_offset[R]` is computed once at agent initialization:
```
A.jitter_offset[R] = random_int(-R.jitter, +R.jitter)  # seeded by sim seed + agent_id
```

This ensures reproducibility while spreading agent actions across ticks.

## 2. Inbox Processing Order

When an agent drains its inbox at the start of each tick, items are processed in the following order:
1. QueryResult items (Ch.3) — sorted by query_id (deterministic)
2. InterAgentMessage items (Ch.2) — sorted by (tick_sent, from_agent) (deterministic)

This ordering ensures:
- Query results from the previous tick are processed before new messages
- Agents react to fresh data before handling incoming requests
- Processing order is deterministic for reproducibility

## 3. Multi-Tick Pipeline Correlation

Several actions span multiple ticks (e.g., view_product: query at N, result at N+1). The correlation between a query request and its result uses the `query_id` field (UUID).

Each agent maintains a `pending_queries: dict[str, PendingQuery]` mapping query_id to the context needed to process the result:

```
PendingQuery {
    query_id:       str         # UUID matching the QueryRequest
    query_template: str         # "product_details", "inventory_check", etc.
    context:        dict        # action-specific context (e.g., {sku_id, order_request_id})
    issued_tick:    int         # tick when query was emitted
}
```

When a QueryResult arrives in the inbox:
1. Look up pending_queries[result.query_id]
2. If found, process the result with the stored context
3. If not found (orphaned result), log warning and discard
4. TTL: If current_tick - issued_tick > QUERY_TTL (default 10), discard the pending query entry and log a pipeline stall warning. The agent continues with stale local state.

## 4. Failure Handling & Centralized Logging

### V1 Failure Model

In V1, **no business-logic failures occur** because all agents have unlimited capacity and resources:
- Consumers: unlimited budget → payments never fail
- Sellers: unlimited stock (via suppliers) → orders never rejected for stock-out
- Suppliers: unlimited production → restocks always fulfilled immediately
- Transport: unlimited shipping capacity → shipments always accepted
- Payment: no external service → no transaction failures

### What CAN Fail (Technical Anomalies)

| Failure Type | Cause | Detection | Response |
|---|---|---|---|
| **Message delivery** | Bug in inbox routing — message sent to nonexistent agent | `to_agent` not found in agent registry | Log error, discard message |
| **Schema violation** | Event payload missing required fields | Translator validation at event ingestion | Log error, skip event |
| **Unknown event type** | Python emits event not in Go operation catalog | Catalog whitelist check (see GO_TRANSLATOR.md G4) | Log error, reject event |
| **Query timeout** | TiDB query exceeds 2-second limit | Go translator timeout | Log warning, agent receives no result (continues with stale local state) |
| **Unexpected agent state** | Agent receives message for unknown order_request_id | Lookup miss in local state | Log warning, discard message |
| **Pipeline stall** | Agent waiting for QueryResult that never arrives | Tick-based TTL on pending operations (QUERY_TTL = 10 ticks, see §3 above) | Log warning, cancel pending operation after TTL ticks |

Note: Inbox processing follows a deterministic ordering protocol (see §2 above) to ensure reproducible behavior even under varying message delivery patterns.

### Centralized Log Schema

All agents write anomaly logs to a shared in-memory log buffer, flushed periodically to disk:

```
AnomalyLog {
    timestamp:   datetime         # wall-clock time
    tick:        int              # simulation tick
    agent_id:    int              # agent that detected the anomaly
    agent_type:  string           # "consumer", "seller", etc.
    action:      string           # action being executed when anomaly occurred
    error_type:  string           # "message_delivery", "schema_violation", etc.
    severity:    string           # "warning", "error"
    details:     dict             # {msg_type, expected, actual, stacktrace, ...}
}
```

**Log format on disk**: JSONL (one JSON object per line), rotated per simulation run.

### V2 Failure Hooks

The following extension points are reserved for V2 capacity-constrained operation:

| Hook Location | V2 Feature | Current V1 Behavior |
|---|---|---|
| `Seller.process_order()` step 2 | Inventory check → reject if out of stock | Always accept |
| `Transport.receive_ship_request()` step 1 | Capacity check → reject if no carrier available | Always accept |
| `Consumer.make_payment()` step 2 | Balance check → fail if insufficient funds | Always succeed |
| `Supplier.receive_restock_order()` step 1 | Capacity check → partial fill or backorder | Always fulfill fully |

Each hook is a clearly marked decision point in the agent code: `# V2_HOOK: capacity_check`.
