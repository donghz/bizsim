# Ch.3 Mode 2 Query Requests — Shared Reference

> Extracted from: agent-behavior.md §5.3 (lines 1111–1123)

## Query Template Registry

Agents emit Mode 2 query requests using these named templates. The Go translator executes the full SQL, reduces the result to a domain struct, and delivers it to the agent's inbox in the next tick.

| Template Name | Requesting Agent | Params | Returns (domain struct) | TiDB Pattern |
|---|---|---|---|---|
| `product_details` | Consumer | `{sku_id: int, seller_id: int}` | `{current_price: decimal, avg_review: float, review_count: int}` | Point lookup + JOIN on reviews |
| `order_history` | Consumer | `{consumer_id: int, window_days: int}` | `{orders: [{order_request_id, status, is_late: bool}], count: int}` | Secondary index range scan |
| `inventory_check` | Seller | `{seller_id: int, sku_id: int}` | `{qty_available: int}` | Point lookup on inventory |
| `inventory_levels` | Seller | `{seller_id: int}` | `{items: [{sku_id, qty, last_updated_tick}]}` | Full table scan on inventory |
| `sales_analytics` | Seller | `{seller_id: int, window_ticks: int}` | `{revenue: decimal, top_products: [sku_id], units_sold: int, trend: "up"/"down"/"flat"}` | GROUP BY + aggregate + ORDER BY |
| `competitor_prices` | Seller | `{category: string}` | `{avg_price: decimal, min_price: decimal, max_price: decimal, price_rank: int}` | Cross-seller category scan |
| `fulfillment_overdue` | Supplier | `{supplier_id: int}` | `{overdue_count: int, worst_delay_ticks: int}` | Composite index scan on date |
| `shipment_tracking` | Consumer / Seller | `{order_id: int}` | `{status: string, eta_tick: int, is_delayed: bool, last_location: string}` | Point lookup + LEFT JOIN |
| `gov_economic_indicators` | Government | `{period_ticks: int}` | `{gdp: decimal, transaction_volume: int, avg_price_index: float, trade_balance: decimal, active_entities: int}` | Full table scans + heavy GROUP BY + multi-table JOINs |

## Query Pipeline Protocol

1. Agent emits `QueryRequest` with `query_template` name and `params` dict
2. Go translator executes the full SQL query (may scan 100K+ rows — this IS the DB pressure)
3. Translator reduces result set to a small, fixed-schema domain struct (O(1) size)
4. `QueryResult` is delivered to the agent's inbox, available **next tick** (minimum 1-tick latency)
5. Agent processes `QueryResult` during inbox drain, uses it to update local state or make decisions

## Query Correlation

Each query request carries a `query_id` (UUID). The corresponding `QueryResult` includes the same `query_id` for correlation. Agents maintain a `pending_queries` map to associate results with their original request context. See AGENT_BASE.md §4.5 for the full correlation protocol.

## Rate Limiting

Agents do not query every tick. Each template has a cooldown period configured in the scheduling system (see AGENT_BASE.md §4). Mode 2 queries generate naturally staggered read workload, not synchronized bursts.
