# Python Interface Contracts — Shared Types & Protocols

> Synthesized from: vision.md P8 (lines 586–626), G2 (lines 1231–1248); agent-behavior.md §4.4–4.5 (lines 959–987), §5.1 (lines 993–1006), §5.2 (lines 1033–1057), §7 (lines 1397–1451)
> Cross-references: ARCHITECTURE.md (channels, tick loop), EVENTS.md (event type tables), MESSAGES.md (message type tables), QUERIES.md (query template tables), GO_TRANSLATOR.md (guardrails)

This file defines the Python dataclasses, protocols, and type aliases that form the shared vocabulary across all BizSim components. Every agent, the simulation engine, and the Python-side translator interface depend on these contracts.

---

## 1. Channel 2: Inter-Agent Messages (In-Memory)

Ch.2 messages are Python objects appended to a target agent's inbox `deque`. They never cross the translator boundary, never generate SQL, and never touch TiDB.

```python
from dataclasses import dataclass
from typing import Union
from uuid import UUID

@dataclass
class InterAgentMessage:
    msg_id:       UUID              # unique message ID
    msg_type:     str               # message type (see MESSAGES.md for full table)
    from_agent:   int               # sender agent ID
    to_agent:     int               # recipient agent ID
    from_tenant:  str               # sender's tenant ID
    tick_sent:    int               # tick when sent
    payload:      dict              # message-type-specific data (see MESSAGES.md)
```

**Delivery semantics**:
- Messages emitted at tick N are appended to target agent's inbox at tick N (step 6 of tick loop).
- Target agent drains its inbox at tick N+1 (step 0 of tick loop).
- Minimum delivery latency = 1 tick. Maximum = 1 tick (no queuing beyond one tick boundary).
- Delivery order within a tick is deterministic: sorted by `(tick_sent, from_agent)`.

**Not a Ch.2 message**: `SharePurchase` is delivered via direct function call to the Community Subsystem (see COMMUNITY.md), not through the inbox.

---

## 2. Channel 3: Query Pipeline (DB-Backed, Async)

### QueryRequest — Emitted by Agent

Agents emit query requests alongside action events. The Go translator executes the SQL, reduces the result, and delivers a `QueryResult` to the agent's inbox in a future tick.

```python
@dataclass
class QueryRequest:
    event_type:     str = "query_request"  # fixed discriminator
    query_id:       str               # UUID, for correlation with result
    agent_id:       int               # requesting agent
    query_template: str               # template name (see QUERIES.md for full table)
    params:         dict              # template-specific parameters
    tick_issued:    int               # tick when agent emitted request
```

### QueryResult — Delivered to Agent Inbox

```python
@dataclass
class QueryResult:
    event_type:     str = "query_result"   # fixed discriminator
    query_id:       str               # correlates to QueryRequest.query_id
    agent_id:       int               # agent that requested this
    query_template: str               # which template produced this result
    tick_issued:    int               # when agent asked (from request)
    tick_available: int               # earliest tick agent can see this (≥ tick_issued + 1)
    data:           dict              # reduced domain struct (NOT raw rows)
```

**Key invariant**: An agent never sees the result of a query in the same tick it was issued. Minimum latency = 1 tick. The `data` field is a small, fixed-schema domain struct whose shape is defined per template in QUERIES.md.

---

## 3. Inbox — Union Type

Every agent has an inbox that receives both Ch.2 messages and Ch.3 query results:

```python
from collections import deque

InboxItem = Union[InterAgentMessage, QueryResult]

# Per agent:
inbox: deque[InboxItem] = deque()
```

### Inbox Processing Order (§4.4)

When an agent drains its inbox at the start of each tick, items are processed in this order:
1. **QueryResult items** (Ch.3) — sorted by `query_id` (deterministic)
2. **InterAgentMessage items** (Ch.2) — sorted by `(tick_sent, from_agent)` (deterministic)

This ensures:
- Query results are processed before action-triggering messages
- Agents have fresh data context before reacting to incoming requests
- Processing order is reproducible across runs

---

## 4. Channel 1: Action Events (Translated to SQL)

Action events are the outbound contract from Python to the Go translator. The translator expands each event into SQL statements.

```python
from dataclasses import dataclass, field
from uuid import UUID

@dataclass
class ReadPattern:
    pattern:  str               # operation catalog name (see GO_TRANSLATOR.md)
    params:   dict              # template parameters

@dataclass
class WritePattern:
    pattern:  str               # operation catalog name (see GO_TRANSLATOR.md)
    params:   dict              # template parameters

@dataclass
class ActionEvent:
    event_id:   UUID            # unique event ID
    event_type: str             # event type (see EVENTS.md for full table)
    agent_id:   int             # emitting agent ID
    tenant_id:  str             # agent's own tenant ID (set by EventEmitter, never by agent)
    tick:       int             # current tick
    reads:      list[ReadPattern]         # Mode 1 correlated reads (translator discards results)
    writes:     list[WritePattern]        # Mode 1 writes (translator executes)
    messages:   list[InterAgentMessage]   # Ch.2 messages to route (sim engine processes)
```

**Separation of concerns**: The Go translator processes `reads` and `writes` (expanding them into SQL via the operation catalog). The simulation engine processes `messages` (appending them to target agent inboxes). The `event_type` field is the dispatch key for the translator's `events.requires` validation.

---

## 5. Multi-Tick Pipeline Correlation (§4.5)

Several actions span multiple ticks (e.g., `view_product`: query emitted at tick N, result arrives at tick N+1). Correlation uses the `query_id` UUID.

```python
@dataclass
class PendingQuery:
    query_id:       str         # UUID matching the QueryRequest
    query_template: str         # "product_details", "inventory_check", etc.
    context:        dict        # action-specific context (e.g., {sku_id, order_request_id})
    issued_tick:    int         # tick when query was emitted
```

Each agent maintains:
```python
pending_queries: dict[str, PendingQuery]  # query_id → PendingQuery
```

**Processing protocol**:
1. When `QueryResult` arrives in inbox, look up `pending_queries[result.query_id]`
2. If found → process result with stored context, remove from pending
3. If not found → orphaned result: log warning, discard
4. **TTL**: If `current_tick - issued_tick > QUERY_TTL` (default 10), discard the pending entry and log a pipeline stall warning. Agent continues with stale local state.

---

## 6. Tenant Context & Event Emitter (G2)

Agents receive a pre-bound `EventEmitter` that enforces Tenant Write Sovereignty. The `tenant_id` is baked in at agent construction — agents cannot specify or override it.

```python
@dataclass(frozen=True)
class TenantContext:
    tenant_id: str              # immutable after construction

class EventEmitter:
    """Pre-bound emitter that enforces tenant write sovereignty.
    
    Agents call self.emit_action(...) which delegates to this emitter.
    The tenant_id is ALWAYS set by the emitter, never by the agent.
    """
    def __init__(self, tenant: TenantContext):
        self._tenant = tenant

    def emit(self, event_type: str, reads: list[ReadPattern], writes: list[WritePattern],
             messages: list[InterAgentMessage]) -> ActionEvent:
        return ActionEvent(
            event_id=uuid4(),
            event_type=event_type,
            agent_id=self._agent_id,     # set at binding time
            tenant_id=self._tenant.tenant_id,  # NEVER from caller
            tick=self._current_tick,      # set by engine each tick
            reads=reads,
            writes=writes,
            messages=messages,
        )
```

**Design rationale**: This is a Tier A guardrail (see GO_TRANSLATOR.md). There is no `emit(tenant_id=..., ...)` method. The agent cannot forge writes to another tenant's tables.

---

## 7. Agent Base Protocol

All agent types implement this protocol. The simulation engine calls `step()` once per tick.

```python
from typing import Protocol

class AgentProtocol(Protocol):
    agent_id: int
    agent_type: str                         # "consumer", "seller", "supplier", "transport", "government"
    tenant_id: str
    inbox: deque[InboxItem]
    pending_queries: dict[str, PendingQuery]

    def step(self, tick: int) -> list[ActionEvent]:
        """Execute one tick of agent behavior.
        
        The step() method:
        1. Drains inbox (QueryResults first, then InterAgentMessages)
        2. Executes scheduled autonomous actions
        3. Returns a list of ActionEvents to emit
        
        QueryRequests are returned separately via emit_query().
        """
        ...

    def emit_query(self, query_template: str, params: dict, context: dict) -> QueryRequest:
        """Emit a Ch.3 query request with correlation context.
        
        Automatically:
        - Generates a query_id UUID
        - Records a PendingQuery in self.pending_queries
        - Returns the QueryRequest for the engine to forward to the translator
        """
        ...
```

---

## 8. Anomaly Log (§7)

All agents write anomaly logs to a shared in-memory buffer, flushed periodically to disk as JSONL.

```python
@dataclass
class AnomalyLog:
    timestamp:  str             # wall-clock time (ISO 8601)
    tick:       int             # simulation tick
    agent_id:   int             # agent that detected the anomaly
    agent_type: str             # "consumer", "seller", etc.
    action:     str             # action being executed when anomaly occurred
    error_type: str             # "message_delivery", "schema_violation", "unknown_event_type",
                                # "query_timeout", "unexpected_state", "pipeline_stall"
    severity:   str             # "warning" or "error"
    details:    dict            # {msg_type, expected, actual, stacktrace, ...}
```

**Error types and responses**:

| Error Type | Cause | Response |
|---|---|---|
| `message_delivery` | Message to nonexistent agent | Log error, discard message |
| `schema_violation` | Event payload missing required fields | Log error, skip event |
| `unknown_event_type` | Event not in Go operation catalog | Log error, reject event |
| `query_timeout` | TiDB query exceeds 2s limit | Log warning, no result delivered |
| `unexpected_state` | Message for unknown order_request_id | Log warning, discard message |
| `pipeline_stall` | QueryResult never arrives within TTL | Log warning, cancel pending query |

---

## 9. Query Cooldowns

Agents do not query every tick. Rate limiting prevents query flooding:

```python
QUERY_COOLDOWNS: dict[str, int] = {
    "order_history":           50,   # consumer checks orders every ~50 ticks
    "shipment_tracking":       20,   # more frequent for active orders
    "product_details":         10,   # consumer checks before purchase decision
    "sales_analytics":        100,   # seller checks weekly
    "competitor_prices":       40,   # seller monitors competition
    "inventory_check":         30,   # seller checks stock (only during evaluate_inventory)
    "inventory_levels":        60,   # seller checks all stock
    "fulfillment_overdue":     30,   # supplier checks regularly
    "gov_economic_indicators": 100,  # government runs census periodically
}
```

Each agent tracks `last_query_tick: dict[str, int]` per template. A query is only emitted if `current_tick - last_query_tick[template] >= QUERY_COOLDOWNS[template]`.

---

## 10. Cross-References

| Topic | Spec File |
|---|---|
| System architecture, tick loop, channels | ARCHITECTURE.md |
| Ch.2 message type definitions & payloads | MESSAGES.md |
| Ch.1 event type definitions & Mode 1 patterns | EVENTS.md |
| Ch.3 query templates & return schemas | QUERIES.md |
| Go translator, operation catalog, guardrails | GO_TRANSLATOR.md |
| Agent scheduling, inbox ordering, failure handling | AGENT_BASE.md |
| Consumer actions & purchase funnel | CONSUMER.md |
| Seller actions & LLM strategy | SELLER.md |
| Supplier actions & restock pipeline | SUPPLIER.md |
| Transport actions & shipment state machine | TRANSPORT.md |
| Government actions & statistics pipeline | GOVERNMENT.md |
| Community subsystem & social propagation | COMMUNITY.md |
| Product system & SKU catalog | PRODUCT_SYSTEM.md |
