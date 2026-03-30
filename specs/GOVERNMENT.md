# Government Agent Spec

> Extracted from: agent-behavior.md §3.5 (lines 730–764) + §6.4 (lines 1308–1326)
> Cross-references: MESSAGES.md (order_report, disruption_report), EVENTS.md (gov_*), QUERIES.md (gov_economic_indicators)

## Action Catalog

### `receive_report`

| | |
|---|---|
| **Trigger** | Inbox: `OrderReport` or `DisruptionReport` message |
| **Input** | Report payload (order details, disruption details) |
| **Pipeline** | Single-tick |

**Steps**:
1. Emit Ch.1 event: `gov_record_insert` → INSERT `gov_records` (entity_type, entity_id, period, metrics_json)

**Output**:
- **Ch.1**: `gov_record_insert` (INSERT `gov_records` in Analytics tenant)

---

### `compute_statistics`

| | |
|---|---|
| **Trigger** | Recurring tick schedule (see AGENT_BASE.md) — infrequent, heavy |
| **Input** | None (queries TiDB for raw data) |
| **Pipeline** | Two-tick: query → compute + publish |

**Steps**:
1. **Tick N**: Emit Ch.3 query: `gov_economic_indicators` template (heavy GROUP BY across gov_records)
2. **Tick N+1**: Receive `QueryResult` with aggregated metrics (GDP, unemployment, trade_balance, etc.)
3. **Tick N+1**: Emit Ch.1 event: `gov_statistics_insert` → INSERT `statistics` (aggregated indicators)
4. **Tick N+1**: (V2) Broadcast policy changes to other agents via Ch.2

**Output**:
- **Ch.3**: `gov_economic_indicators` query request (heavy analytical)
- **Ch.1**: `gov_statistics_insert` (INSERT `statistics` in Analytics tenant)

---

## Pipeline Sequence: Government Statistics

```
Tick   Government
─────  ──────────────────────────────────────────────
  N     compute_statistics() triggered by schedule
        └─ Ch.3: gov_economic_indicators query (Mode 2)
           (heavy: SELECT COUNT(*), AVG(), SUM()
            FROM gov_records JOIN statistics
            GROUP BY sector, region)

  N+1   drain inbox:
        └─ QueryResult(gov_economic_indicators)
        └─ Compute derived indicators
        └─ Ch.1: gov_statistics_insert
           (INSERT statistics with GDP, transaction_volume,
            avg_price_index, etc.)
        └─ (V2: broadcast policy changes to agents)
```

## DB Workload Pattern

Government generates **two distinct DB patterns**:

1. **Write pattern** (Analytics tenant):
   - `INSERT gov_records` — frequent, one per received report (driven by Seller order completions)
   - `INSERT statistics` — infrequent (~every 168 ticks), one row of aggregated indicators

2. **Read pattern** (Analytics tenant, via Mode 2 query):
   - `gov_economic_indicators` — **heaviest query in the system**: full table scans + GROUP BY + multi-table JOINs across gov_records and statistics
   - Exercises TiDB's analytical query processing on realistic data volumes

## Read Sovereignty Exception

Government is the only agent type that reads across all tenants via Ch.3 queries (analytical queries, census, statistics). This is allowed — they read via the translator, which generates realistic analytical read pressure on TiDB. But government **writes** only to its own Analytics tenant tables (`gov_records`, `statistics`). Government never modifies another tenant's data.
