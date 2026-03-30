# Seller (Store) Agent Spec

> Extracted from: agent-behavior.md §3.2 (lines 433–588) + §6.3 (lines 1285–1304) + §9 (lines 1576–1738)
> Cross-references: MESSAGES.md (place_order, order_accepted, order_rejected, payment, ship_request, delivery_complete, shipment_notification, order_report, restock_order, cancel_request, cancel_confirmed, cancel_rejected, restock_delivered), EVENTS.md (store_*), QUERIES.md (inventory_check, inventory_levels, sales_analytics, competitor_prices), PRODUCT_SYSTEM.md (sku_catalog, sku_seller_mapping, sku_supplier_mapping)

## Action Catalog

### `receive_order`

| | |
|---|---|
| **Trigger** | Inbox: `PlaceOrder` message from Consumer |
| **Input** | `order_request_id`, `sku_id`, `qty`, `consumer_id` from message payload |
| **Pipeline** | First step of a multi-tick order processing pipeline |

**Steps**:
1. Validate SKU exists in this seller's catalog (Product System lookup)
2. Queue the order in local state: `pending_incoming[order_request_id] = {sku_id, qty, consumer_id, status: "queued"}`
3. Emit Ch.3 Mode 2 query: `inventory_check` template with `{seller_id, sku_id}` → queries TiDB for current inventory level
4. Wait for query result (arrives next tick)

**Output**:
- **Ch.3**: `inventory_check` query request
- **Local state**: Order queued

---

### `process_order`

| | |
|---|---|
| **Trigger** | Inbox: `QueryResult` for `inventory_check` from previous tick |
| **Input** | Inventory level from query result, queued order details |
| **Pipeline** | Single-tick, produces Ch.1 events and Ch.2 messages |

**Steps**:
1. Retrieve queued order matching this inventory check
2. Decision: accept order (V1: always accept — unlimited stock means inventory always sufficient)
3. Emit Ch.1 event: `store_order_accepted` → INSERT `store_orders`, UPDATE `inventory` (decrement)
4. Send Ch.2 message: `OrderAccepted` → Consumer's inbox

**V1 note**: Since capacity is unlimited, step 2 always accepts. The Mode 2 inventory query still generates realistic DB read patterns even though the decision outcome is predetermined.

**Output**:
- **Ch.1**: `store_order_accepted` (INSERT `store_orders` + UPDATE `inventory` in Store tenant)
- **Ch.2**: `OrderAccepted` message to Consumer

---

### `receive_payment`

| | |
|---|---|
| **Trigger** | Inbox: `Payment` message from Consumer |
| **Input** | `order_request_id`, `amount`, `payer_id` |
| **Pipeline** | Single-tick, fans out to multiple agents |

**Steps**:
1. Validate payment matches a pending order
2. Update local state: mark order as "paid"
3. Emit Ch.1 event: `store_payment_received` → INSERT into `payment_log` (receipt bookkeeping)
4. Send Ch.2 message: `ShipRequest` → Transport carrier's inbox (selected round-robin or by assignment)
   - Include `shipment_type = "consumer_order"`
5. Send Ch.2 message: `OrderReport` → Government's inbox

**Output**:
- **Ch.1**: `store_payment_received` (INSERT `payment_log` in Store tenant)
- **Ch.2**: `ShipRequest` to Transport
- **Ch.2**: `OrderReport` to Government

---

### `receive_delivery_confirmation`

| | |
|---|---|
| **Trigger** | Inbox: `DeliveryComplete` from Transport (for consumer orders) OR `RestockDelivered` from Supplier (for restocks) |
| **Input** | `shipment_id`, `shipment_type` ("consumer_order" or "restock"), associated order/restock IDs |
| **Pipeline** | Single-tick |

**Steps**:
1. Look up shipment/order context from local state
2. **IF shipment_type == "consumer_order"** (Triggered by `DeliveryComplete` from Transport):
   a. Update local state: mark order as "delivered"
   b. Send Ch.2: `ShipmentNotification` → Consumer
   c. (NO inventory update — inventory was already decremented at process_order)
3. **IF shipment_type == "restock"** (Triggered by `RestockDelivered` from Supplier):
   a. Update local state: mark restock as "received"
   b. Emit Ch.1: `store_inventory_update` → UPDATE `inventory` (increment by restocked qty)
   c. (NO consumer notification — this is a B2B restock)

**Output**:
- **Consumer order**: Ch.2 `ShipmentNotification` to Consumer
- **Restock**: Ch.1 `store_inventory_update` (UPDATE `inventory` in Store tenant)

---

### `receive_cancel_request`

| | |
|---|---|
| **Trigger** | Inbox: `CancelRequest` message from Consumer |
| **Input** | `order_request_id`, `consumer_id` |
| **Pipeline** | Single-tick |

**Steps**:
1. Look up order in local state
2. If order status allows cancellation (not yet shipped):
   a. Update local state: mark order as "cancelled"
   b. Emit Ch.1: `store_order_cancelled` → UPDATE `store_orders` SET status='cancelled'
   c. Emit Ch.1: `store_inventory_update` → UPDATE `inventory` (increment back)
   d. Send Ch.2: `CancelConfirmed` → Consumer
3. If order already shipped (V1: rare since shipping is immediate):
   a. Send Ch.2: `CancelRejected` → Consumer (order already in transit)

**Output**:
- Varies by case.

---

### `evaluate_pricing`

| | |
|---|---|
| **Trigger** | Recurring tick schedule (see AGENT_BASE.md) — LLM-driven |
| **Input** | Sales analytics (from Mode 2 query result), competitor prices (from Mode 2 query result), current inventory levels, Product System price bounds |
| **Pipeline** | Three-tick: query data (tick N) → receive + LLM decide (tick N+1) → emit updates (tick N+1) |

**Steps**:
1. **Tick N**: Emit Ch.3 queries: `sales_analytics` and `competitor_prices` templates
2. **Tick N+1**: Receive `QueryResult` items in inbox. Update local sales cache. Construct LLM context (see Pricing Strategy below).
3. **Tick N+1**: Call LLM with pricing context. LLM returns list of `(sku_id, new_price)` adjustments.
4. **Tick N+1**: Validate each price against Product System bounds (`price_floor`, `price_ceiling`). Clamp if needed.
5. **Tick N+1**: For each price change, emit Ch.1 event: `store_price_update` → UPDATE `store_pricing`

**Output**:
- **Ch.3**: `sales_analytics` + `competitor_prices` query requests
- **Ch.1**: One or more `store_price_update` events (UPDATE `store_pricing` in Store tenant)

---

### `evaluate_inventory`

| | |
|---|---|
| **Trigger** | Recurring tick schedule (see AGENT_BASE.md) — LLM-driven |
| **Input** | Current inventory levels (from Mode 2 query), sales velocity, BOM data from Product System |
| **Pipeline** | Three-tick: query (tick N) → receive + LLM decide (tick N+1) → send restock (tick N+1) |

**Steps**:
1. **Tick N**: Emit Ch.3 query: `inventory_levels` template (full inventory snapshot for this store)
2. **Tick N+1**: Receive `QueryResult`. Construct LLM context with inventory levels, recent sales velocity, and BOM reference data.
3. **Tick N+1**: Call LLM with inventory context. LLM returns list of `(sku_id, restock_qty)` recommendations.
4. **Tick N+1**: For each restock recommendation, determine which supplier(s) to order from (`sku_supplier_mapping` in Product System).
5. **Tick N+1**: Send Ch.2 message: `RestockOrder` → Supplier's inbox

**Output**:
- **Ch.3**: `inventory_levels` query request
- **Ch.2**: One or more `RestockOrder` messages to Supplier(s)

---

## Pricing Strategy Pipeline (§6.3)

```
Tick   Seller
─────  ──────────────────────────────────────────────
  N     evaluate_pricing() triggered by schedule
        └─ Ch.3: sales_analytics query (Mode 2)
        └─ Ch.3: competitor_prices query (Mode 2)

  N+1   drain inbox:
        └─ QueryResult(sales_analytics)
        └─ QueryResult(competitor_prices)
        └─ Update local sales cache
        └─ Construct LLM context (see below)
        └─ LLM call → returns price adjustments
        └─ Validate against Product System bounds
        └─ For each price change:
           └─ Ch.1: store_price_update
              (UPDATE store_pricing SET price = new_price)
```

---

## Seller Strategy Detail (§9)

### Pricing Strategy

#### Data Pipeline

```
Tick N:   Seller emits Mode 2 queries:
          └─ sales_analytics: {seller_id, window_ticks: 200}
          └─ competitor_prices: {category}   (for each category seller participates in)

Tick N+1: Seller receives QueryResults, constructs LLM context:
          ├─ Sales data: revenue, units sold, top/bottom products, trend
          ├─ Competitor data: avg price, min price, price rank per category
          ├─ Current prices: from local state
          ├─ Inventory levels: from local state (last known from Mode 2 cache)
          └─ Product bounds: from Product System (price_floor, price_ceiling)

          LLM call → price adjustment decisions

          For each adjustment:
          └─ Ch.1: store_price_update
             (UPDATE store_pricing SET price = new_price WHERE sku_id = ?)
```

#### LLM Prompt Template (Pricing)

```
You are a store pricing manager. Based on the following data, recommend price adjustments.

STORE PERFORMANCE (last {window} ticks):
- Revenue: ${revenue}
- Units sold: {units_sold}
- Top products: {top_products_with_prices}
- Underperforming products: {bottom_products_with_prices}
- Trend: {trend}

COMPETITOR LANDSCAPE:
{for each category}
- Category "{category}": avg market price ${avg}, lowest ${min}, your rank #{rank}
{end}

CURRENT INVENTORY:
{for each sku}
- SKU {sku_id} "{name}": {qty} units, current price ${price}, base price ${base}
{end}

CONSTRAINTS:
- Each product has a price floor and ceiling (provided below)
- Price changes take effect next tick
- Goal: maximize revenue while maintaining competitive positioning

PRICE BOUNDS:
{for each sku}
- SKU {sku_id}: floor ${price_floor}, ceiling ${price_ceiling}
{end}

Respond with a JSON array of price changes:
[{"sku_id": 123, "new_price": 45.99, "reasoning": "..."}]
Only include products that need price changes. Empty array if no changes needed.
```

#### Pricing Guardrails

| Guardrail | Enforcement |
|---|---|
| Price within bounds | Clamp to `[price_floor, price_ceiling]` from Product System. Log warning if LLM exceeded. |
| Maximum change per cycle | ±20% from current price. Larger changes are clamped. Prevents LLM hallucination causing wild swings. |
| Rate limit | Maximum 1 LLM call per `evaluate_pricing` cycle per seller. |
| Fallback | If LLM fails (timeout, malformed response), keep current prices. Log error. |

---

### Inventory Control Strategy

#### Data Pipeline

```
Tick N:   Seller emits Mode 2 query:
          └─ inventory_levels: {seller_id}

Tick N+1: Seller receives QueryResult, constructs LLM context:
          ├─ Current inventory: qty per SKU
          ├─ Sales velocity: (from local sales cache — units sold per tick)
          ├─ Pending restocks: from local state (outstanding RestockOrders)
          ├─ BOM data: from Product System (which parts/suppliers for each SKU)
          └─ Lead time estimate: configured per supplier (constant in V1)

          LLM call → restocking decisions

          For each restock:
          └─ Ch.2: RestockOrder → Supplier's inbox
```

#### LLM Prompt Template (Inventory)

```
You are a store inventory manager. Based on the following data, recommend restocking actions.

CURRENT INVENTORY:
{for each sku}
- SKU {sku_id} "{name}": {qty} units in stock
  Sales velocity: {sales_per_tick} units/tick (last {window} ticks)
  Days of stock remaining: {qty / sales_per_tick / 24} simulated days
  Pending restock: {pending_qty} units (ETA: {eta_ticks} ticks)
{end}

SUPPLIER INFO:
{for each supplier}
- Supplier {supplier_id}: lead time {lead_time} ticks, provides parts for SKUs {sku_list}
{end}

CONSTRAINTS:
- Restocking takes {lead_time} ticks to arrive
- Goal: prevent stockouts while minimizing excess inventory
- Consider pending restocks already in transit

Respond with a JSON array of restock orders:
[{"sku_id": 123, "qty": 50, "supplier_id": 7, "reasoning": "..."}]
Only include SKUs that need restocking. Empty array if no restocking needed.
```

#### Inventory Guardrails

| Guardrail | Enforcement |
|---|---|
| Valid supplier | Supplier must exist in `sku_supplier_mapping` for the requested SKU |
| Reasonable quantity | Restock qty capped at 10× average sales velocity. Log warning if LLM exceeded. |
| Rate limit | Maximum 1 LLM call per `evaluate_inventory` cycle per seller |
| Fallback | If LLM fails, use rule-based default: restock to 2× lead_time × sales_velocity |

---

### LLM Integration Architecture

```
Seller Agent (Python)
    │
    ├─ Construct prompt from local state + QueryResults + Product System
    │
    ├─ async LLM call (with response caching keyed by input hash)
    │  └─ Cache hit? Use cached response (deterministic replay)
    │  └─ Cache miss? Call LLM API, cache response
    │
    ├─ Parse LLM JSON response
    │  └─ Validation: check types, bounds, referenced SKU/supplier existence
    │  └─ Fallback: if parse fails, use rule-based default
    │
    └─ Emit events / send messages based on validated decisions
```

**LLM call budget (V1)**: With ~1,000 sellers, each calling LLM twice per evaluation cycle (pricing + inventory), at average cycles of ~80 ticks:
- Calls per tick: `1000 × 2 / 80 = ~25 LLM calls/tick`
- At 0.1 ticks/sec (Scenario 1): `~2.5 LLM calls/sec` — easily within rate limits
- Cost: at $0.01/call, $2.50/1000 ticks ≈ $0.25/simulated day — very manageable
