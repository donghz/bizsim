# BizSim Agent Behavior Specification (V1)

> **Purpose**: Define every agent type, every action it can take, when and why it takes each action, what data it needs, what messages/events it produces, and the full async pipeline sequence for multi-step flows. A developer should be able to implement all agent behavior from this document alone.

> **Scope**: V1 — unlimited capacity for all agents, no business-logic failures, no payment agent, simple recurring scheduling. V2 hooks noted where applicable.

> **Companion**: Read `vision.md` for architecture principles (P1–P9), channel definitions (Ch.1/Ch.2/Ch.3), tenant write sovereignty, and capacity planning.

---

## Table of Contents

1. [Agent Type Catalog](#1-agent-type-catalog)
2. [Product System & Common Knowledge](#2-product-system--common-knowledge)
3. [Action Catalog — Per Agent Type](#3-action-catalog--per-agent-type)
4. [Action Scheduling Configuration](#4-action-scheduling-configuration)
5. [Message & Event Schema](#5-message--event-schema)
6. [Pipeline Sequence Diagrams](#6-pipeline-sequence-diagrams)
7. [Failure Handling & Centralized Logging](#7-failure-handling--centralized-logging)
8. [Consumer Purchase Funnel Detail](#8-consumer-purchase-funnel-detail)
9. [Seller Strategy Detail](#9-seller-strategy-detail)
10. [V2 Evolution Hooks](#10-v2-evolution-hooks)

---

## 1. Agent Type Catalog

### 1.1 Overview Table

| Agent Type | Count Range | Intelligence Tier | V1 Capacity | DB Tenant | Primary Motivation |
|---|---|---|---|---|---|
| **Consumer** | 10K–1M | Rule-based + statistical profiles + social influence | Unlimited budget | Consumer App (shared) | Fulfill needs driven by demographics, trends, and social influence |
| **Seller (Store)** | 100–10K | Hybrid: rules for order processing + LLM for strategy | Unlimited stock (via suppliers) | Per-Store (isolated) | Maximize profit through pricing and inventory optimization |
| **Supplier** | 50–5K | Rule-based | Unlimited production capacity | Supplier ERP (grouped) | Fulfill restock orders reliably |
| **Transport (Carrier)** | 10–500 | Discrete event / queue-based | Unlimited shipping capacity | Logistics (shared or per-carrier) | Move goods from origin to destination within transit time |
| **Government** | 1 | Aggregate statistics + policy rules | N/A | Analytics (isolated) | Monitor ecosystem health, produce statistics |

### 1.2 What is NOT an Agent in V1

| Entity | Why Not an Agent | How It Works Instead |
|---|---|---|
| **Payment** | No separate payment service in V1 | Consumer sends `Payment` message directly to Seller as a step in the purchase pipeline. Consumer logs spending; Seller logs receipt. Both are bookkeeping operations on their own tenants. |
| **Community / Social** | Not an agent — a propagation mechanism | A graph diffusion model that runs as a batch computation within the simulation engine. Activated when consumers emit `SharePurchase` messages. Modifies other consumers' interest profiles and trend multipliers. |
| **Marketplace Platform** | No central marketplace agent | Replaced by the Product System (§2): a read-only SQLite database providing SKU registry and category taxonomy as common knowledge. |

### 1.3 Agent Descriptions

#### Consumer

**Role**: The demand generator. Consumers browse products, make purchase decisions through a statistical funnel, buy from stores, and share purchase experiences that influence other consumers.

**What drives autonomous actions**: Recurring needs (configured by demographic profile), social influence from community trends, and periodic order-history checks. Consumers never use LLM — all decisions are probability-based with parameters drawn from configured distributions.

**Tenant writes**: `consumer_orders` (purchase intents, status updates), `consumer_reviews` (V2).

#### Seller (Store)

**Role**: The supply-demand bridge. Stores receive orders from consumers, manage inventory levels, set prices competitively, and coordinate with suppliers and transport.

**What drives autonomous actions**:
- **Reactive**: Incoming `PlaceOrder` messages trigger order processing pipelines.
- **Proactive (LLM)**: Periodic strategy evaluations (pricing, inventory) driven by tick-based scheduling. LLM analyzes sales data and market conditions to make strategic adjustments.

**Tenant writes**: `store_orders`, `inventory`, `store_pricing`, `payment_log` (receipt bookkeeping).

#### Supplier

**Role**: The production source. Suppliers receive restock orders from stores and arrange shipment of goods via transport carriers.

**What drives autonomous actions**:
- **Reactive**: Incoming `RestockOrder` messages trigger fulfillment (always successful in V1).
- **Proactive**: Periodic production bookkeeping updates.

**V1 simplification**: Unlimited capacity — every restock order is immediately fulfilled. No allocation decisions, no prioritization.

**Tenant writes**: `suppliers` (capacity bookkeeping), `purchase_orders` (inbound order records).

#### Transport (Carrier)

**Role**: The logistics executor. Carriers create shipments, track transit progress, and deliver goods.

**What drives autonomous actions**:
- **Reactive**: Incoming `ShipRequest` messages trigger shipment creation.
- **Autonomous**: In-transit shipments advance through a state machine each tick. When transit time expires, delivery completes automatically.

**V1 simplification**: Unlimited capacity — every shipment request is immediately accepted. Transit time is a configured constant per route (or random within a range).

**Tenant writes**: `shipments`, `tracking_events`.

#### Government

**Role**: The observer and statistician. Government receives reports from other agents and periodically runs heavy analytical queries to compute economic indicators.

**What drives autonomous actions**:
- **Reactive**: Incoming `OrderReport` and `DisruptionReport` messages trigger record insertion.
- **Proactive**: Periodic statistics computation via heavy Mode 2 analytical queries.

**V1 simplification**: Read-only observer. No policy feedback loops (V2).

**Tenant writes**: `gov_records`, `statistics`.

---

## 2. Product System & Common Knowledge

### 2.1 Design Overview

The Product System is a **global, read-only SQLite database** loaded into simulation memory at startup. It serves as shared reference data ("common knowledge") that all agents can query in-process. It does NOT go through the Go translator, does NOT generate TiDB workload, and does NOT cross the IPC boundary.

```
┌───────────────────────────────────────────────────────┐
│                 Simulation Process                    │
│                                                       │
│  ┌───────────────────────────────────┐                │
│  │   Product System (SQLite, r/o)    │                │
│  │                                   │                │
│  │  ┌─────────────┐ ┌──────────────┐ │                │
│  │  │ SKU Catalog │ │ Parts / BOM  │ │                │
│  │  └─────────────┘ └──────────────┘ │                │
│  └──────────┬────────────────────────┘                │
│             │ in-process queries                      │
│     ┌───────┼───────┬──────────┬──────────┐           │
│     ▼       ▼       ▼          ▼          ▼           │
│  Consumer  Seller  Supplier  Transport  Government    │
│                                                       │
│  (agents read SKU names, categories, seller mappings, │
│   BOM data — zero DB cost, zero IPC cost)             │
└───────────────────────────────────────────────────────┘
```

### 2.2 SKU Catalog Schema

```sql
CREATE TABLE sku_catalog (
    sku_id        INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,           -- "Wireless Earbuds Pro X1"
    category      TEXT NOT NULL,           -- "Electronics > Audio > Earbuds"
    subcategory   TEXT,                    -- "True Wireless"
    base_price    REAL NOT NULL,           -- 49.99 (reference price, sellers set actual)
    price_floor   REAL NOT NULL,           -- 25.00 (minimum allowed price)
    price_ceiling REAL NOT NULL,           -- 99.99 (maximum allowed price)
    weight_kg     REAL,                    -- 0.15
    brand         TEXT,                    -- "AudioTech"
    tags          TEXT,                    -- JSON array: ["trending", "gift", "portable"]
    created_tick  INTEGER DEFAULT 0
);

CREATE TABLE sku_seller_mapping (
    sku_id     INTEGER NOT NULL REFERENCES sku_catalog(sku_id),
    seller_id  INTEGER NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,     -- primary seller for this SKU
    PRIMARY KEY (sku_id, seller_id)
);

CREATE INDEX idx_sku_category ON sku_catalog(category);
CREATE INDEX idx_sku_seller ON sku_seller_mapping(seller_id);
```

**Usage patterns**:
- Consumer `browse_catalog`: `SELECT sku_id, name, base_price FROM sku_catalog WHERE category = ? ORDER BY RANDOM() LIMIT 20`
- Consumer `pick_product`: `SELECT s.seller_id FROM sku_seller_mapping s WHERE s.sku_id = ? AND s.is_primary = 1`
- Seller `get_my_skus`: `SELECT sku_id FROM sku_seller_mapping WHERE seller_id = ?`
- Seller LLM context: `SELECT name, base_price, price_floor, price_ceiling FROM sku_catalog WHERE sku_id IN (?)`

### 2.3 Parts / BOM Schema

Provides common terminology across the supply chain. Reference-only in V1 (no production constraints).

```sql
CREATE TABLE parts (
    part_id    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,              -- "Lithium Polymer Battery 500mAh"
    category   TEXT NOT NULL,              -- "Electronics > Batteries"
    unit_cost  REAL                        -- reference cost per unit
);

CREATE TABLE bill_of_materials (
    bom_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id     INTEGER NOT NULL REFERENCES sku_catalog(sku_id),
    part_id    INTEGER NOT NULL REFERENCES parts(part_id),
    qty        INTEGER NOT NULL DEFAULT 1, -- how many of this part per SKU
    layer      INTEGER NOT NULL DEFAULT 0  -- 0=raw, 1=component, 2=assembly, 3=finished
);

CREATE INDEX idx_bom_sku ON bill_of_materials(sku_id);
CREATE INDEX idx_bom_part ON bill_of_materials(part_id);
```

**V1 usage**: Sellers and Suppliers can look up "what parts are needed for SKU X" and "what SKUs use part Y" for terminology alignment and LLM context enrichment. No actual production constraint enforcement.

### 2.4 Initialization

The SQLite database is generated once from a configuration seed file (YAML or JSON) and loaded at simulation start:

```yaml
# products_seed.yaml
categories:
  - name: "Electronics > Audio > Earbuds"
    sku_count: 50
    price_range: [20, 150]
    sellers_per_sku: [1, 5]    # uniform random range
  - name: "Apparel > Shoes > Running"
    sku_count: 100
    price_range: [40, 300]
    sellers_per_sku: [2, 8]
# ... generates ~1000-10000 SKUs total
```

---

## 3. Action Catalog — Per Agent Type

Every action is defined with:
- **Trigger**: What causes the action (recurring tick schedule, inbox message, or pipeline continuation)
- **Input data**: What the agent needs to know
- **Pipeline steps**: Numbered steps, each producing a specific output
- **Output**: Ch.1 events (DB writes), Ch.2 messages (inter-agent), or Ch.3 queries (DB reads)

### 3.1 Consumer Actions

#### `browse_catalog`

| | |
|---|---|
| **Trigger** | Recurring tick schedule (see §4) |
| **Input** | Consumer's interest profile (category weights), active trend multipliers from social layer |
| **Pipeline** | Single-step, completes within one tick |

**Steps**:
1. Query Product System (SQLite): select a category weighted by consumer interest profile + trend influence
2. Retrieve candidate SKUs: `SELECT sku_id, name, base_price FROM sku_catalog WHERE category = ? LIMIT 20`
3. For each candidate SKU, compute `view_probability` (see §8 Consumer Funnel)
4. SKUs that pass the view threshold enter the `view_product` pipeline
5. Emit Ch.1 event: `consumer_browse` (read-only — generates correlated SELECTs in TiDB for catalog/review data)

**Output**:
- **Ch.1**: `consumer_browse` event (correlated reads: `SELECT catalog`, `SELECT reviews` — results discarded by translator)
- **Local state**: List of SKU IDs the consumer will "view" next tick

---

#### `view_product`

| | |
|---|---|
| **Trigger** | Pipeline continuation from `browse_catalog` (next tick) |
| **Input** | SKU IDs from browse step, consumer's price sensitivity |
| **Pipeline** | Two-tick: emit query (tick N), receive result + decide (tick N+1) |

**Steps**:
1. **Tick N**: For each SKU to view, emit Ch.3 Mode 2 query: `product_details` (fetches current price from seller's `store_pricing`, review scores)
2. **Tick N+1**: Receive `QueryResult` in inbox. For each product viewed:
   a. Apply **View → Cart** dropout probability (see §8)
   b. Products that survive enter the consumer's local cart

**Output**:
- **Ch.3**: `product_details` query request (per SKU)
- **Local state**: Cart updated with surviving products

---

#### `add_to_cart`

| | |
|---|---|
| **Trigger** | Pipeline continuation from `view_product` |
| **Input** | Products that passed view→cart dropout |
| **Pipeline** | Instant (same tick as view_product result processing) |

**Steps**:
1. Add product to local cart state
2. Apply **Cart → Purchase** dropout probability (see §8)
3. Products that survive trigger `initiate_purchase`

**Output**:
- **Local state only** — no Ch.1 event, no Ch.2 message, no DB operation

---

#### `initiate_purchase`

| | |
|---|---|
| **Trigger** | Pipeline continuation from `add_to_cart` (same tick) |
| **Input** | SKU ID, quantity, selected seller ID (from Product System mapping), current price |
| **Pipeline** | Single-tick, produces both Ch.1 event and Ch.2 message |

**Steps**:
1. Generate `order_request_id` (UUID)
2. Record purchase intent in local state: `pending_orders[order_request_id] = {sku_id, qty, status: "requested"}`
3. Emit Ch.1 event: `consumer_purchase_intent` → INSERT into `consumer_orders`
4. Send Ch.2 message: `PlaceOrder` → target Seller agent's inbox

**Output**:
- **Ch.1**: `consumer_purchase_intent` (INSERT `consumer_orders` in Consumer App tenant)
- **Ch.2**: `PlaceOrder` message to Seller

---

#### `make_payment`

| | |
|---|---|
| **Trigger** | Inbox: `OrderAccepted` message from Seller |
| **Input** | `order_request_id`, `amount` from OrderAccepted payload |
| **Pipeline** | Single-tick, immediate response to acceptance |

**Steps**:
1. Update local state: `pending_orders[order_request_id].status = "accepted"`
2. Log spending in local budget tracker (V1: no balance check, unlimited funds)
3. Send Ch.2 message: `Payment` → target Seller agent's inbox

**Output**:
- **Ch.2**: `Payment` message to Seller
- **Local state**: Order status updated, spending logged

---

#### `receive_confirmation`

| | |
|---|---|
| **Trigger** | Inbox: `ShipmentNotification` message from Seller |
| **Input** | `order_request_id`, `shipment_id`, delivery status |
| **Pipeline** | Single-tick |

**Steps**:
1. Update local state: `pending_orders[order_request_id].status = "delivered"`
2. Move from `pending_orders` to `completed_orders`
3. Emit Ch.1 event: `consumer_order_status_update` → UPDATE `consumer_orders` SET status='delivered'

**Output**:
- **Ch.1**: `consumer_order_status_update` (UPDATE `consumer_orders` in Consumer App tenant)
- Triggers `share_purchase` in next step

---

#### `share_purchase`

| | |
|---|---|
| **Trigger** | Pipeline continuation from `receive_confirmation` (same tick or next) |
| **Input** | Completed order details (sku_id, category) |
| **Pipeline** | Single-tick |

**Steps**:
1. Send Ch.2 message: `SharePurchase` → Community propagation mechanism
2. Community layer processes this during its batch propagation step (see vision.md P3 step 4)

**Output**:
- **Ch.2**: `SharePurchase` message to Community propagation system
- **Side effect**: Influences other consumers' interest profiles for the purchased category/brand

---

#### `query_order_history`

| | |
|---|---|
| **Trigger** | Recurring tick schedule (see §4) |
| **Input** | Consumer ID, time window |
| **Pipeline** | Two-tick: emit query (tick N), process result (tick N+1) |

**Steps**:
1. **Tick N**: Emit Ch.3 query request: `order_history` template with `{consumer_id, window_days: 30}`
2. **Tick N+1**: Receive `QueryResult` in inbox. Update `known_orders` local cache with fresh order statuses from TiDB.
3. Check for late orders: if `is_late == true`, may trigger `cancel_order` action (V1: low probability since no actual delays)

**Output**:
- **Ch.3**: `order_history` query request
- **Local state**: `known_orders` cache refreshed

---

### 3.2 Seller (Store) Actions

#### `receive_order`

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

#### `process_order`

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

#### `receive_payment`

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
5. Send Ch.2 message: `OrderReport` → Government's inbox

**Output**:
- **Ch.1**: `store_payment_received` (INSERT `payment_log` in Store tenant)
- **Ch.2**: `ShipRequest` to Transport
- **Ch.2**: `OrderReport` to Government

---

#### `receive_delivery_confirmation`

| | |
|---|---|
| **Trigger** | Inbox: `DeliveryComplete` message from Transport |
| **Input** | `order_id`, `shipment_id`, delivery timestamp |
| **Pipeline** | Single-tick |

**Steps**:
1. Update local state: mark order as "delivered"
2. Emit Ch.1 event: `store_inventory_update` → UPDATE `inventory` (V1: replenishment not needed since unlimited, but bookkeeping write generates DB workload)
3. Send Ch.2 message: `ShipmentNotification` → Consumer's inbox

**Output**:
- **Ch.1**: `store_inventory_update` (UPDATE `inventory` in Store tenant)
- **Ch.2**: `ShipmentNotification` to Consumer

---

#### `evaluate_pricing`

| | |
|---|---|
| **Trigger** | Recurring tick schedule (see §4) — LLM-driven |
| **Input** | Sales analytics (from Mode 2 query result), competitor prices (from Mode 2 query result), current inventory levels, Product System price bounds |
| **Pipeline** | Three-tick: query data (tick N) → receive + LLM decide (tick N+1) → emit updates (tick N+1) |

**Steps**:
1. **Tick N**: Emit Ch.3 queries: `sales_analytics` and `competitor_prices` templates
2. **Tick N+1**: Receive `QueryResult` items in inbox. Construct LLM context (see §9 for prompt template).
3. **Tick N+1**: Call LLM with pricing context. LLM returns list of `(sku_id, new_price)` adjustments.
4. **Tick N+1**: Validate each price against Product System bounds (`price_floor`, `price_ceiling`). Clamp if needed.
5. **Tick N+1**: For each price change, emit Ch.1 event: `store_price_update` → UPDATE `store_pricing`

**Output**:
- **Ch.3**: `sales_analytics` + `competitor_prices` query requests
- **Ch.1**: One or more `store_price_update` events (UPDATE `store_pricing` in Store tenant)

---

#### `evaluate_inventory`

| | |
|---|---|
| **Trigger** | Recurring tick schedule (see §4) — LLM-driven |
| **Input** | Current inventory levels (from Mode 2 query), sales velocity, BOM data from Product System |
| **Pipeline** | Three-tick: query (tick N) → receive + LLM decide (tick N+1) → send restock (tick N+1) |

**Steps**:
1. **Tick N**: Emit Ch.3 query: `inventory_levels` template (full inventory snapshot for this store)
2. **Tick N+1**: Receive `QueryResult`. Construct LLM context with inventory levels, recent sales velocity, and BOM reference data.
3. **Tick N+1**: Call LLM with inventory context. LLM returns list of `(sku_id, restock_qty)` recommendations.
4. **Tick N+1**: For each restock recommendation, determine which supplier(s) to order from (Product System BOM → supplier mapping).
5. **Tick N+1**: Send Ch.2 message: `RestockOrder` → Supplier's inbox

**Output**:
- **Ch.3**: `inventory_levels` query request
- **Ch.2**: One or more `RestockOrder` messages to Supplier(s)

---

#### `query_sales_analytics`

| | |
|---|---|
| **Trigger** | Recurring tick schedule (see §4) |
| **Input** | Seller ID, time window |
| **Pipeline** | Two-tick: query (tick N) → receive result (tick N+1) and update local cache |

**Steps**:
1. **Tick N**: Emit Ch.3 query: `sales_analytics` template
2. **Tick N+1**: Receive result, update local sales cache. Used as input for next `evaluate_pricing` cycle.

**Output**:
- **Ch.3**: `sales_analytics` query request
- **Local state**: Sales cache updated

---

### 3.3 Supplier Actions

#### `receive_restock_order`

| | |
|---|---|
| **Trigger** | Inbox: `RestockOrder` message from Seller |
| **Input** | `sku_id`, `qty`, `store_id` (destination), `restock_order_id` |
| **Pipeline** | Single-tick (V1: always fulfill immediately) |

**Steps**:
1. Record the restock order locally
2. Emit Ch.1 event: `supplier_restock_fulfilled` → INSERT into `purchase_orders` (fulfillment record)
3. Send Ch.2 message: `ShipRequest` → Transport carrier's inbox (goods destined for the requesting Store)

**V1 note**: No capacity check. Every restock is immediately fulfilled.

**Output**:
- **Ch.1**: `supplier_restock_fulfilled` (INSERT `purchase_orders` in Supplier ERP tenant)
- **Ch.2**: `ShipRequest` to Transport (with `destination = store_id`, `origin = supplier_id`)

---

#### `produce_goods`

| | |
|---|---|
| **Trigger** | Recurring tick schedule (see §4) |
| **Input** | Current capacity metrics |
| **Pipeline** | Single-tick |

**Steps**:
1. Update production bookkeeping counters
2. Emit Ch.1 event: `supplier_production_update` → UPDATE `suppliers` SET capacity metrics

**V1 note**: Pure bookkeeping — capacity is unlimited but we still generate the UPDATE workload for DB testing.

**Output**:
- **Ch.1**: `supplier_production_update` (UPDATE `suppliers` in Supplier ERP tenant)

---

#### `query_fulfillment_status`

| | |
|---|---|
| **Trigger** | Recurring tick schedule (see §4) |
| **Input** | Supplier ID |
| **Pipeline** | Two-tick: query → receive |

**Steps**:
1. **Tick N**: Emit Ch.3 query: `fulfillment_overdue` template
2. **Tick N+1**: Receive result, update local metrics. V1: no overdue orders expected.

**Output**:
- **Ch.3**: `fulfillment_overdue` query request

---

### 3.4 Transport (Carrier) Actions

#### `receive_ship_request`

| | |
|---|---|
| **Trigger** | Inbox: `ShipRequest` message from Seller or Supplier |
| **Input** | `order_id`, `origin_id`, `destination_id`, `items` list |
| **Pipeline** | Single-tick |

**Steps**:
1. Generate `shipment_id`
2. Calculate transit time: `base_transit_ticks + random_jitter` (from config)
3. Record shipment in local state: `active_shipments[shipment_id] = {order_id, origin, dest, start_tick, eta_tick, status: "in_transit"}`
4. Emit Ch.1 event: `transport_shipment_created` → INSERT `shipments` + INSERT `tracking_events` (initial "picked_up" event)

**Output**:
- **Ch.1**: `transport_shipment_created` (INSERT `shipments` + INSERT `tracking_events` in Logistics tenant)

---

#### `update_tracking`

| | |
|---|---|
| **Trigger** | Recurring tick schedule — runs every tick for active shipments |
| **Input** | All `active_shipments` with status "in_transit" |
| **Pipeline** | Single-tick |

**Steps**:
1. For each active shipment, check if current_tick matches a tracking milestone (e.g., 25%, 50%, 75% of transit time)
2. For shipments at milestones, emit Ch.1 event: `transport_tracking_update` → INSERT `tracking_events` (status: "in_transit", location estimate)
3. Check if `current_tick >= eta_tick` → if yes, trigger `complete_delivery`

**Output**:
- **Ch.1**: Zero or more `transport_tracking_update` events (INSERT `tracking_events` in Logistics tenant)

---

#### `complete_delivery`

| | |
|---|---|
| **Trigger** | `update_tracking` detects transit time expired |
| **Input** | Shipment details from local state |
| **Pipeline** | Single-tick |

**Steps**:
1. Update local state: `active_shipments[shipment_id].status = "delivered"`
2. Emit Ch.1 event: `transport_delivery_complete` → UPDATE `shipments` SET status='delivered' + INSERT `tracking_events` (final "delivered" event)
3. Determine the originator of the shipment (Seller or Supplier)
4. Send Ch.2 message: `DeliveryComplete` → originator's inbox

**Output**:
- **Ch.1**: `transport_delivery_complete` (UPDATE `shipments` + INSERT `tracking_events` in Logistics tenant)
- **Ch.2**: `DeliveryComplete` to Seller or Supplier (whoever sent the original `ShipRequest`)

---

### 3.5 Government Actions

#### `receive_report`

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

#### `compute_statistics`

| | |
|---|---|
| **Trigger** | Recurring tick schedule (see §4) — infrequent, heavy |
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

## 4. Action Scheduling Configuration

### 4.1 Design

A centralized YAML config file defines the recurring cycle for each autonomous agent action. The simulation scheduler checks each tick: for each agent, for each of its recurring actions, if `last_executed_tick + cycle_ticks + jitter_offset <= current_tick`, the action fires.

**Jitter** prevents synchronized bursts: each agent draws a random offset from `[-jitter, +jitter]` at initialization, fixed for the simulation run (deterministic with seed).

Only **autonomous** actions (self-initiated by the agent) are scheduled here. **Reactive** actions (triggered by inbox messages) fire immediately when the message is processed during inbox drain.

### 4.2 Configuration Schema

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
    query_sales_analytics:
      cycle_ticks: 80          # sales data refresh every ~80 ticks
      jitter: 20

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

### 4.3 Scheduler Algorithm

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

---

## 5. Message & Event Schema

### 5.1 Ch.2 Inter-Agent Messages (In-Memory)

All messages share a common envelope:

```
InterAgentMessage {
    msg_id:        uuid            # unique message ID
    msg_type:      string          # message type (see table below)
    from_agent:    int             # sender agent ID
    to_agent:      int             # recipient agent ID
    from_tenant:   string          # sender's tenant ID
    tick_sent:     int             # tick when sent
    payload:       dict            # message-type-specific (see below)
}
```

#### Message Type Definitions

| msg_type | From → To | Payload Fields | Description |
|---|---|---|---|
| `place_order` | Consumer → Seller | `order_request_id: uuid`, `sku_id: int`, `qty: int`, `offered_price: decimal` | Consumer requests to purchase a product |
| `order_accepted` | Seller → Consumer | `order_request_id: uuid`, `store_order_id: int`, `confirmed_price: decimal`, `eta_ticks: int` | Seller confirms the order |
| `order_rejected` | Seller → Consumer | `order_request_id: uuid`, `reason: string` | Seller rejects the order (V2 only — not used in V1) |
| `payment` | Consumer → Seller | `order_request_id: uuid`, `store_order_id: int`, `amount: decimal`, `payer_id: int` | Consumer pays for accepted order |
| `ship_request` | Seller → Transport | `shipment_request_id: uuid`, `store_order_id: int`, `origin_id: int`, `destination_id: int`, `items: [{sku_id: int, qty: int}]` | Seller requests shipment after payment |
| `ship_request` | Supplier → Transport | `restock_order_id: uuid`, `origin_id: int`, `destination_id: int`, `items: [{sku_id: int, qty: int}]` | Supplier ships restocked goods to seller |
| `delivery_complete` | Transport → Seller/Supplier | `shipment_id: uuid`, `store_order_id: int` or `restock_order_id: uuid`, `delivered_tick: int` | Shipment delivered successfully |
| `shipment_notification` | Seller → Consumer | `order_request_id: uuid`, `store_order_id: int`, `shipment_id: uuid`, `delivered_tick: int` | Seller notifies consumer of delivery |
| `order_report` | Seller → Government | `store_order_id: int`, `seller_id: int`, `sku_id: int`, `qty: int`, `amount: decimal`, `tick: int` | Seller reports completed transaction |
| `restock_order` | Seller → Supplier | `restock_order_id: uuid`, `sku_id: int`, `qty: int`, `store_id: int` | Seller requests inventory replenishment |
| `share_purchase` | Consumer → Community | `consumer_id: int`, `sku_id: int`, `category: string`, `satisfaction: float` | Consumer shares purchase experience |
| `disruption_report` | Supplier → Government | `supplier_id: int`, `part_id: int`, `severity: string`, `tick: int` | V2: Supplier reports supply disruption |

---

### 5.2 Ch.1 Action Events (Translated to SQL)

All events share a common envelope:

```
ActionEvent {
    event_id:      uuid            # unique event ID
    event_type:    string          # event type (see table below)
    agent_id:      int             # emitting agent ID
    tenant_id:     string          # agent's own tenant ID
    tick:          int             # current tick
    reads:         [ReadPattern]   # Mode 1 correlated reads (translator executes, discards)
    writes:        [WritePattern]  # Mode 1 writes (translator executes)
    messages:      [InterAgentMessage]  # Ch.2 messages to send (processed by sim engine)
}

ReadPattern {
    pattern:  string   # operation catalog name
    params:   dict     # template parameters
}

WritePattern {
    pattern:  string   # operation catalog name
    params:   dict     # template parameters
}
```

#### Event Type Definitions

##### Consumer Events

| Event Type | Tenant | Correlated Reads (Mode 1) | Writes (Mode 1) | Description |
|---|---|---|---|---|
| `consumer_browse` | Consumer App | `browse_catalog: {category, limit: 20}`, `check_reviews: {sku_ids}` | (none — read-only) | Consumer browses products, generates catalog scan + review reads |
| `consumer_purchase_intent` | Consumer App | (none) | `insert_consumer_order: {order_request_id, sku_id, qty, seller_id, offered_price, status: "requested"}` | Consumer records purchase intent |
| `consumer_order_status_update` | Consumer App | (none) | `update_consumer_order: {order_request_id, status}` | Consumer updates order status (confirmed, delivered, cancelled) |

##### Seller Events

| Event Type | Tenant | Correlated Reads (Mode 1) | Writes (Mode 1) | Description |
|---|---|---|---|---|
| `store_order_accepted` | Store (per-store) | `check_inventory: {sku_id}` | `insert_store_order: {order_request_id, sku_id, qty, price, consumer_id, status: "accepted"}`, `update_inventory: {sku_id, qty_delta: -N}` | Store accepts order and decrements inventory |
| `store_payment_received` | Store (per-store) | (none) | `insert_payment_log: {store_order_id, amount, payer_id, tick}` | Store logs payment receipt |
| `store_inventory_update` | Store (per-store) | (none) | `update_inventory: {sku_id, qty_delta: +N}` | Store inventory adjustment (delivery received) |
| `store_price_update` | Store (per-store) | `select_current_price: {sku_id}` | `update_store_pricing: {sku_id, old_price, new_price, tick}` | Store updates product price |

##### Supplier Events

| Event Type | Tenant | Correlated Reads (Mode 1) | Writes (Mode 1) | Description |
|---|---|---|---|---|
| `supplier_restock_fulfilled` | Supplier ERP | (none) | `insert_purchase_order: {restock_order_id, sku_id, qty, store_id, status: "fulfilled"}` | Supplier records fulfilled restock |
| `supplier_production_update` | Supplier ERP | `select_capacity: {supplier_id}` | `update_supplier_capacity: {supplier_id, produced_qty, current_capacity}` | Periodic production bookkeeping |

##### Transport Events

| Event Type | Tenant | Correlated Reads (Mode 1) | Writes (Mode 1) | Description |
|---|---|---|---|---|
| `transport_shipment_created` | Logistics | (none) | `insert_shipment: {shipment_id, order_id, origin_id, dest_id, carrier_id, status: "in_transit", eta_tick}`, `insert_tracking_event: {shipment_id, status: "picked_up", location: origin, tick}` | New shipment created |
| `transport_tracking_update` | Logistics | (none) | `insert_tracking_event: {shipment_id, status: "in_transit", location_estimate, tick}` | Tracking milestone |
| `transport_delivery_complete` | Logistics | (none) | `update_shipment: {shipment_id, status: "delivered", delivered_tick}`, `insert_tracking_event: {shipment_id, status: "delivered", location: destination, tick}` | Shipment delivered |

##### Government Events

| Event Type | Tenant | Correlated Reads (Mode 1) | Writes (Mode 1) | Description |
|---|---|---|---|---|
| `gov_record_insert` | Analytics | (none) | `insert_gov_record: {entity_type, entity_id, report_type, metrics_json, tick}` | Government records a report |
| `gov_statistics_insert` | Analytics | (none) | `insert_statistics: {period, gdp, transaction_volume, avg_price_index, active_sellers, active_consumers, tick}` | Government publishes computed statistics |

---

### 5.3 Ch.3 Mode 2 Query Requests

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

---

## 6. Pipeline Sequence Diagrams

### 6.1 Consumer Purchase Pipeline — The Full Causal Chain

This is the most important workload pattern. A single consumer purchase spans **12+ ticks** across 5 agent types and 5 tenants when including the Mode 2 inventory query.

```
Tick   Consumer                    Seller (Store)                Transport              Government
─────  ─────────────────────────   ────────────────────────────  ─────────────────────  ──────────────
 N     browse_catalog()
       └─ SQLite: pick category
       └─ SQLite: get SKU list
       └─ Ch.1: consumer_browse
          (correlated reads:
           SELECT catalog,
           SELECT reviews)
       └─ Ch.3: product_details
          query for top SKUs
          (Mode 2 → TiDB)
       
 N+1   drain inbox:
       └─ QueryResult(product_details)
       └─ apply View→Cart dropout
       └─ apply Cart→Purchase dropout
       └─ survivors → initiate_purchase()
       └─ Ch.1: consumer_purchase_intent
          (INSERT consumer_orders)
       └─ Ch.2: PlaceOrder ──────►  (in inbox)

 N+2                                drain inbox:
                                    └─ PlaceOrder received
                                    └─ queue order locally
                                    └─ Ch.3: inventory_check
                                       query (Mode 2 → TiDB)

 N+3                                drain inbox:
                                    └─ QueryResult(inventory_check)
                                    └─ decide: ACCEPT (V1: always)
                                    └─ Ch.1: store_order_accepted
                                       (INSERT store_orders,
                                        UPDATE inventory)
                                    └─ Ch.2: OrderAccepted ────►  (Consumer inbox)

 N+4   drain inbox:
       └─ OrderAccepted received
       └─ update local state
       └─ make_payment()
       └─ Ch.2: Payment ─────────►  (in inbox)

 N+5                                drain inbox:
                                    └─ Payment received
                                    └─ Ch.1: store_payment_received
                                       (INSERT payment_log)
                                    └─ Ch.2: ShipRequest ────────►  (Transport inbox)
                                    └─ Ch.2: OrderRepor──────────────────────────────► (Gov inbox)

 N+6                                                                drain inbox:          drain inbox:
                                                                    └─ ShipRequest recv   └─ OrderReport recv
                                                                    └─ create shipment    └─ Ch.1: gov_record_insert
                                                                    └─ Ch.1:                 (INSERT gov_records)
                                                                       transport_shipment_created
                                                                       (INSERT shipments, INSERT tracking_events)

 N+7                                                                update_tracking()
 ...                                                                └─ Ch.1: transport_tracking_update
                                                                     (INSERT tracking_events
                                                                      at milestones)

 N+6+T                                                              complete_delivery()
 (T=transit                                                         └─ Ch.1: transport_delivery_complete
  time)                                                                (UPDATE shipments,INSERT tracking_events)
                                                                    └─ Ch.2: DeliveryComplete ──►  (Seller inbox)

 N+7+T                              drain inbox:
                                    └─ DeliveryComplete received
                                    └─ Ch.1: store_inventory_update
                                       (UPDATE inventory)
                                    └─ Ch.2: ShipmentNotification ──►  (Consumer inbox)

 N+8+T drain inbox:
       └─ ShipmentNotification received
       └─ Ch.1: consumer_order_status_update
          (UPDATE consumer_orders
           SET status='delivered')
       └─ share_purchase()
       └─ Ch.2: SharePurchase ──────►  Community propagation

 N+9+T                                                                                   (Community batch:
                                                                                          update influence_edges,
                                                                                          modify trend multipliers)
```

**DB workload summary for one purchase** (assuming transit time T=4 ticks):

| Tick | Tenant | SQL Operations | TiDB Pattern Tested |
|---|---|---|---|
| N | Consumer App | 2 SELECT (correlated browse) | Catalog scan + review range scan |
| N | Consumer App | 1 SELECT (Mode 2 product_details) | Point lookup + JOIN |
| N+1 | Consumer App | 1 INSERT (consumer_orders) | Single-tenant point write |
| N+2 | Store | 1 SELECT (Mode 2 inventory_check) | Point lookup on inventory |
| N+3 | Store | 1 INSERT + 1 UPDATE (txn) | **Read-then-write transaction**, inventory hotspot |
| N+4 | (no DB ops — payment is Ch.2 only) | — | — |
| N+5 | Store | 1 INSERT (payment_log) | Single-tenant append |
| N+6 | Logistics | 2 INSERT (shipment + tracking) | Append-heavy tenant |
| N+6 | Analytics | 1 INSERT (gov_records) | Analytics tenant write |
| N+7..N+9 | Logistics | ~2 INSERT (tracking milestones) | Append-only table |
| N+10 | Logistics | 1 UPDATE + 1 INSERT (delivery) | Status update on shipment |
| N+11 | Store | 1 UPDATE (inventory) | Write-after-write on same tenant |
| N+12 | Consumer App | 1 UPDATE (order status) | Status update, eventual consistency |

**Total**: 1 logical purchase → **~15 SQL statements** across **4 tenants** over **12+ ticks**. No cross-tenant transaction.

---

### 6.2 Seller Restocking Pipeline

```
Tick   Seller                      Supplier                    Transport
─────  ─────────────────────────   ────────────────────────    ─────────────────────
 N     evaluate_inventory()
       └─ Ch.3: inventory_levels
          query (Mode 2 → TiDB)

 N+1   drain inbox:
       └─ QueryResult(inventory_levels)
       └─ LLM: evaluate restock needs
       └─ Ch.2: RestockOrder ──────►  (in inbox)

 N+2                                drain inbox:
                                    └─ RestockOrder received
                                    └─ Ch.1: supplier_restock_fulfilled
                                       (INSERT purchase_orders)
                                    └─ Ch.2: ShipRequest ──────────────►  (in inbox)

 N+3                                                            drain inbox:
                                                                └─ ShipRequest received
                                                                └─ Ch.1: transport_shipment_created
                                                                   (INSERT shipments + tracking)

 N+3+T                                                          complete_delivery()
                                                                └─ Ch.1: transport_delivery_complete
                                                                └─ Ch.2: DeliveryComplete ──►  (Seller inbox)

 N+4+T drain inbox:
       └─ DeliveryComplete received
       └─ Ch.1: store_inventory_update
          (UPDATE inventory += restocked qty)
```

---

### 6.3 Seller Pricing Strategy Pipeline

```
Tick   Seller
─────  ──────────────────────────────────────────────
 N     evaluate_pricing() triggered by schedule
       └─ Ch.3: sales_analytics query (Mode 2)
       └─ Ch.3: competitor_prices query (Mode 2)

 N+1   drain inbox:
       └─ QueryResult(sales_analytics)
       └─ QueryResult(competitor_prices)
       └─ Construct LLM context (see §9.1)
       └─ LLM call → returns price adjustments
       └─ Validate against Product System bounds
       └─ For each price change:
          └─ Ch.1: store_price_update
             (UPDATE store_pricing SET price = new_price)
```

---

### 6.4 Government Statistics Pipeline

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

---

### 6.5 Social Propagation Pipeline

```
Tick   Consumer (Purchaser)        Community Layer             Consumer (Influenced)
─────  ─────────────────────────   ────────────────────────    ─────────────────────
 N     share_purchase()
       └─ Ch.2: SharePurchase ──►  (queue)

 N+1                               Batch propagation:
                                   └─ For each SharePurchase:
                                      └─ Activate purchaser node
                                         on topic = category
                                      └─ Independent Cascade:
                                         For each neighbor:
                                         P(activate) = edge_weight
                                         × topic_relevance
                                      └─ Activated neighbors get
                                         interest boost for category
                                   └─ Ch.1: (Social Graph tenant)
                                      batch UPDATE influence_edges

 N+2                                                            browse_catalog() picks up
                                                                boosted category interest
                                                                └─ higher P(browse→view)
                                                                   for trending category
                                                                └─ → potential purchase
                                                                   → more SharePurchase
                                                                   → cascading trend
```

**Viral amplification**: If 100 consumers buy the same product in the same tick, 100 `SharePurchase` messages fire simultaneously. Community propagation activates their neighbors (average degree ~6), boosting interest for ~600 consumers. Next browse cycle, these 600 have higher purchase probability → potential for exponential growth, dampened by the cascade probability and limited hops (K=3 max).

---

## 7. Failure Handling & Centralized Logging

### 7.1 V1 Failure Model

In V1, **no business-logic failures occur** because all agents have unlimited capacity and resources:
- Consumers: unlimited budget → payments never fail
- Sellers: unlimited stock (via suppliers) → orders never rejected for stock-out
- Suppliers: unlimited production → restocks always fulfilled immediately
- Transport: unlimited shipping capacity → shipments always accepted
- Payment: no external service → no transaction failures

### 7.2 What CAN Fail (Technical Anomalies)

| Failure Type | Cause | Detection | Response |
|---|---|---|---|
| **Message delivery** | Bug in inbox routing — message sent to nonexistent agent | `to_agent` not found in agent registry | Log error, discard message |
| **Schema violation** | Event payload missing required fields | Translator validation at event ingestion | Log error, skip event |
| **Unknown event type** | Python emits event not in Go operation catalog | Catalog whitelist check (see vision.md G4) | Log error, reject event |
| **Query timeout** | TiDB query exceeds 2-second limit | Go translator timeout | Log warning, agent receives no result (continues with stale local state) |
| **Unexpected agent state** | Agent receives message for unknown order_request_id | Lookup miss in local state | Log warning, discard message |
| **Pipeline stall** | Agent waiting for QueryResult that never arrives | Tick-based TTL on pending operations | Log warning, cancel pending operation after TTL ticks |

### 7.3 Centralized Log Schema

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

### 7.4 V2 Failure Hooks

The following extension points are reserved for V2 capacity-constrained operation:

| Hook Location | V2 Feature | Current V1 Behavior |
|---|---|---|
| `Seller.process_order()` step 2 | Inventory check → reject if out of stock | Always accept |
| `Transport.receive_ship_request()` step 1 | Capacity check → reject if no carrier available | Always accept |
| `Consumer.make_payment()` step 2 | Balance check → fail if insufficient funds | Always succeed |
| `Supplier.receive_restock_order()` step 1 | Capacity check → partial fill or backorder | Always fulfill fully |

Each hook is a clearly marked decision point in the agent code: `# V2_HOOK: capacity_check`.

---

## 8. Consumer Purchase Funnel Detail

### 8.1 Funnel Model

The consumer purchase process is a multi-stage statistical funnel. At each stage, a probability determines whether the consumer proceeds to the next stage or drops out. This is purely rule-based — no LLM involvement.

```
                    ┌───────────────────┐
                    │   browse_catalog  │  (all consumers on schedule)
                    └────────┬──────────┘
                             │
                    P(browse → view) = category_interest × trend_multiplier
                             │
                    ┌────────▼──────────┐
                    │   view_product    │  (emit Mode 2 query, wait 1 tick)
                    └────────┬──────────┘
                             │
                    P(view → cart) = f(price_sensitivity, price_vs_base, review_score)
                             │
                    ┌────────▼──────────┐
                    │    add_to_cart    │  (local state only)
                    └────────┬──────────┘
                             │
                    P(cart → purchase) = urgency × (1 - cart_abandonment_base)
                             │
                    ┌────────▼──────────┐
                    │ initiate_purchase │  (Ch.1 event + Ch.2 message)
                    └───────────────────┘
```

### 8.2 Stage Probabilities

#### Stage 1: Browse → View

```
P_view = clamp(interest[category] × trend_multiplier × novelty_factor, 0, 1)
```

| Parameter | Source | Type | Range |
|---|---|---|---|
| `interest[category]` | Consumer profile (initialized from demographic distribution) | float | [0.0, 1.0] |
| `trend_multiplier` | Social propagation layer — boosted when category is trending | float | [0.5, 3.0] |
| `novelty_factor` | Decreases if consumer recently viewed this category | float | [0.3, 1.0] |

A consumer browsing 20 SKUs with P_view=0.3 will "view" ~6 products on average.

#### Stage 2: View → Cart

```
price_ratio = (actual_price - base_price) / base_price
review_factor = min(avg_review_score / 4.0, 1.0)  # normalized to [0, 1]
P_cart = clamp((1.0 - price_ratio × price_sensitivity) × review_factor, 0, 1)
```

| Parameter | Source | Type | Range |
|---|---|---|---|
| `actual_price` | Mode 2 query result (`product_details.current_price`) | decimal | varies |
| `base_price` | Product System (SQLite) | decimal | varies |
| `price_sensitivity` | Consumer profile | float | [0.1, 2.0] — higher = more price sensitive |
| `avg_review_score` | Mode 2 query result (`product_details.avg_review`) | float | [1.0, 5.0] |

Example: base_price=50, actual_price=55, price_sensitivity=1.0, reviews=4.2:
`P_cart = (1.0 - 0.1×1.0) × min(4.2/4.0, 1.0) = 0.9 × 1.0 = 0.9`

#### Stage 3: Cart → Purchase

```
P_purchase = urgency × (1.0 - cart_abandonment_base) × inventory_of_need
```

| Parameter | Source | Type | Range |
|---|---|---|---|
| `urgency` | Consumer profile (higher for essential goods categories) | float | [0.3, 1.0] |
| `cart_abandonment_base` | Global config | float | [0.1, 0.4] — typical e-commerce abandonment |
| `inventory_of_need` | Whether consumer recently bought this category | float | [0.2, 1.0] — lower if recently purchased similar |

### 8.3 Configuration Schema

```yaml
# consumer_funnel.yaml
funnel:
  browse_to_view:
    base_interest_distribution:
      type: "beta"
      alpha: 2.0
      beta: 5.0                    # skewed toward lower interest (realistic)
    trend_multiplier_range: [0.5, 3.0]
    novelty_decay_ticks: 50        # novelty_factor recovers over 50 ticks
    
  view_to_cart:
    price_sensitivity_distribution:
      type: "normal"
      mean: 1.0
      std: 0.3
      min: 0.1
      max: 2.0
    review_weight: 1.0             # multiplier for review influence
    
  cart_to_purchase:
    urgency_by_category:
      "Groceries": { mean: 0.9, std: 0.05 }
      "Electronics": { mean: 0.5, std: 0.15 }
      "Apparel": { mean: 0.4, std: 0.2 }
      "default": { mean: 0.6, std: 0.15 }
    cart_abandonment_base: 0.25
    repeat_purchase_cooldown_ticks: 100  # suppress urgency for recent purchases
```

### 8.4 DB Workload per Funnel Stage

| Stage | DB Operations | TiDB Pattern |
|---|---|---|
| Browse | Mode 1 correlated: `SELECT catalog WHERE category=? LIMIT 20`, `SELECT reviews WHERE sku_id IN (?)` | Category index scan, IN-list lookup |
| View | Mode 2: `product_details` query per SKU (batched) | Point lookups + JOINs on pricing and reviews |
| Cart | (none) | — |
| Purchase | Mode 1: `INSERT consumer_orders` | Single-row point write |

**Workload amplification**: If 10,000 consumers browse per tick with 20 SKUs each → 200,000 catalog SELECTs. After Stage 1 dropout (avg P=0.3), ~60,000 product_detail queries. After Stage 2 (avg P=0.7), ~42,000 cart additions. After Stage 3 (avg P=0.6), ~25,000 purchases → 25,000 INSERTs + 25,000 PlaceOrder messages to stores.

---

## 9. Seller Strategy Detail

### 9.1 Pricing Strategy

#### Trigger & Frequency

Triggered by recurring schedule: `evaluate_pricing` fires every ~100 ticks (±20 jitter). One LLM call per evaluation cycle per seller.

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

#### LLM Prompt Template

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

#### Guardrails

| Guardrail | Enforcement |
|---|---|
| Price within bounds | Clamp to `[price_floor, price_ceiling]` from Product System. Log warning if LLM exceeded. |
| Maximum change per cycle | ±20% from current price. Larger changes are clamped. Prevents LLM hallucination causing wild swings. |
| Rate limit | Maximum 1 LLM call per `evaluate_pricing` cycle per seller. |
| Fallback | If LLM fails (timeout, malformed response), keep current prices. Log error. |

---

### 9.2 Inventory Control Strategy

#### Trigger & Frequency

Triggered by recurring schedule: `evaluate_inventory` fires every ~60 ticks (±15 jitter). One LLM call per evaluation cycle per seller.

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

#### LLM Prompt Template

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
- Supplier {supplier_id}: handles SKUs {sku_list}, lead time ~{lead_time} ticks
{end}

CONSTRAINTS:
- Suppliers have unlimited capacity (V1)
- Restocking has a lead time (supplier processing + transport)
- Goal: maintain sufficient stock to avoid stockouts while minimizing over-ordering
- Recommended safety stock: {safety_stock_ticks} ticks worth of demand

Respond with a JSON array of restock orders:
[{"sku_id": 123, "qty": 500, "supplier_id": 7, "reasoning": "..."}]
Only include SKUs that need restocking. Empty array if all stock levels are healthy.
```

#### Guardrails

| Guardrail | Enforcement |
|---|---|
| Minimum restock qty | Must be > 0 and ≤ 10,000 per order (prevents LLM hallucination of extreme quantities) |
| Valid supplier | Supplier must be mapped to the SKU in Product System BOM |
| Rate limit | Maximum 1 LLM call per `evaluate_inventory` cycle per seller |
| Fallback | If LLM fails, apply simple rule: restock if `qty < safety_stock_qty` (computed from sales velocity × safety_stock_ticks) |

### 9.3 LLM Integration Architecture

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

---

## 10. V2 Evolution Hooks

### 10.1 Feature Additions

| Feature | Where It Plugs In | V1 Current Behavior | V2 Behavior |
|---|---|---|---|
| **Consumer income/spending accounts** | `Consumer.make_payment()` | Unlimited budget, log spending only | Check wallet balance, reject if insufficient, update wallet with income events |
| **Seller double-entry accounting** | `Seller.receive_payment()` | Log receipt only | Full debit/credit entries in Payment Ledger tenant |
| **Supplier capacity limits** | `Supplier.receive_restock_order()` | Always fulfill | Check capacity, partial fill or backorder if exceeded, send `PartialFill` or `BackorderNotice` |
| **Transport capacity limits** | `Transport.receive_ship_request()` | Always accept | Check carrier capacity, reject or queue if overloaded |
| **Order rejection** | `Seller.process_order()` | Always accept | Reject if inventory < qty, send `OrderRejected` Ch.2 to Consumer |
| **Payment agent** | Purchase pipeline | Direct Consumer→Seller payment message | Separate Payment agent handles `Charge` message, double-entry bookkeeping, settlement |
| **Per-action temporal curves** | Scheduling (§4) | Flat recurring with jitter | Hourly/weekly/seasonal modulation curves per action type |
| **Government policy feedback** | `Government.compute_statistics()` | Statistics published, no downstream effect | Government broadcasts policy changes (tax rates, regulations) that modify agent behavior parameters |
| **Consumer review system** | Post-delivery | `share_purchase` only | `write_review` action → INSERT `consumer_reviews`, affects other consumers' View→Cart probability |
| **Supply chain disruptions** | Supplier events | No disruptions | Stochastic disruption injection: `supplier_disrupted` event → cascading `SupplyDisruption` messages to stores |

### 10.2 Hook Markers in Code

Every V2 extension point should be marked in the implementation with:

```python
# V2_HOOK: <feature_name>
# Current: <V1 behavior>
# Future: <V2 behavior description>
```

Example:
```python
def process_order(self, order):
    inventory = self._get_inventory_result(order.sku_id)
    
    # V2_HOOK: capacity_check
    # Current: always accept (unlimited inventory)
    # Future: if inventory.qty < order.qty: send OrderRejected, return
    
    self.emit_action(StoreOrderAccepted(...))
    self.send_message(OrderAccepted(...))
```

---

*Document version: V1.0*
*Companion to: vision.md*
*Last updated: 2026-03-30*
