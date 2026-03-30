# Consumer Agent Spec

> Extracted from: agent-behavior.md §3.1 (lines 222–431) + §6.1 (lines 1127–1239) + §6.6 (lines 1359–1393) + §8 (lines 1455–1572)
> Cross-references: MESSAGES.md (place_order, order_accepted, payment, shipment_notification, cancel_request, cancel_confirmed, cancel_rejected), EVENTS.md (consumer_*), QUERIES.md (product_details, order_history), PRODUCT_SYSTEM.md (sku_catalog, sku_seller_mapping), COMMUNITY.md (enqueue_activation)

## Order Status Lifecycle

```
requested → accepted → delivered
            → cancel_requested → cancelled
```

## Action Catalog

### `browse_catalog`

| | |
|---|---|
| **Trigger** | Recurring tick schedule (see AGENT_BASE.md) |
| **Input** | Consumer's interest profile (category weights), active trend multipliers from social layer |
| **Pipeline** | Single-step, completes within one tick |

**Steps**:
1. Query Product System (SQLite): select a category weighted by consumer interest profile + trend influence
2. Retrieve candidate SKUs: `SELECT sku_id, name, base_price FROM sku_catalog WHERE category = ? LIMIT 20`
3. For each candidate SKU, compute `view_probability` (see Purchase Funnel below)
4. Emit Ch.1 event: `consumer_browse` (read-only — generates correlated SELECTs in TiDB for catalog/review data)
5. SKUs that pass the view threshold are stored in local state for `view_product` next tick

**Output**:
- **Ch.1**: `consumer_browse` event (correlated reads: `SELECT catalog`, `SELECT reviews` — results discarded by translator)
- **Local state**: List of SKU IDs the consumer will "view" next tick

---

### `view_product`

| | |
|---|---|
| **Trigger** | Pipeline continuation from `browse_catalog`, next tick |
| **Input** | SKU IDs from browse step, consumer's price sensitivity |
| **Pipeline** | Two-tick: emit query (tick N), receive result + decide (tick N+1) |

**Steps**:
1. **Tick N**: For each SKU to view, emit Ch.3 Mode 2 query: `product_details` (fetches current price from seller's `store_pricing`, review scores)
2. **Tick N+1**: Receive `QueryResult` in inbox. For each product viewed:
   a. Apply **View → Cart** dropout probability (see Purchase Funnel below)
   b. Products that survive enter the consumer's local cart

**Output**:
- **Ch.3**: `product_details` query request (per SKU)
- **Local state**: Cart updated with surviving products

---

### `add_to_cart`

| | |
|---|---|
| **Trigger** | Pipeline continuation from `view_product` |
| **Input** | Products that passed view→cart dropout |
| **Pipeline** | Instant (same tick as view_product result processing) |

**Steps**:
1. Add product to local cart state
2. Apply **Cart → Purchase** dropout probability (see Purchase Funnel below)
3. Products that survive trigger `initiate_purchase`

**Output**:
- **Local state only** — no Ch.1 event, no Ch.2 message, no DB operation

---

### `initiate_purchase`

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

### `make_payment`

| | |
|---|---|
| **Trigger** | Inbox: `OrderAccepted` message from Seller |
| **Input** | `order_request_id`, `amount` from OrderAccepted payload |
| **Pipeline** | Single-tick, immediate response to acceptance |

**Steps**:
1. Update local state: `pending_orders[order_request_id].status = "accepted"`
2. Emit Ch.1 event: `consumer_order_status_update` → UPDATE `consumer_orders` SET status='accepted'
3. Log spending in local budget tracker (V1: no balance check, unlimited funds)
4. Send Ch.2 message: `Payment` → target Seller agent's inbox

**Output**:
- **Ch.1**: `consumer_order_status_update` (UPDATE `consumer_orders` in Consumer App tenant)
- **Ch.2**: `Payment` message to Seller
- **Local state**: Order status updated, spending logged

---

### `receive_confirmation`

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

### `share_purchase`

| | |
|---|---|
| **Trigger** | Pipeline continuation from `receive_confirmation` (same tick or next) |
| **Input** | Completed order details (sku_id, category) |
| **Pipeline** | Single-tick |

**Steps**:
1. Call `community.enqueue_activation(share_purchase_data)` (not a Ch.2 message)
2. Community layer processes this during its batch propagation step in tick loop step 4

**Output**:
- **Action**: Enqueue activation in Community subsystem
- **Side effect**: Influences other consumers' interest profiles for the purchased category/brand

---

### `query_order_history`

| | |
|---|---|
| **Trigger** | Recurring tick schedule (see AGENT_BASE.md) |
| **Input** | Consumer ID, time window |
| **Pipeline** | Two-tick: emit query (tick N), process result (tick N+1) |

**Steps**:
1. **Tick N**: Emit Ch.3 query request: `order_history` template with `{consumer_id, window_days: 30}`
2. **Tick N+1**: Receive `QueryResult` in inbox. Update `known_orders` local cache with fresh order statuses from TiDB.
3. Check for late orders: if `is_late == true` and `random < cancel_probability`, trigger `cancel_order` action.

**Output**:
- **Ch.3**: `order_history` query request
- **Local state**: `known_orders` cache refreshed

---

### `cancel_order`

| | |
|---|---|
| **Trigger** | Pipeline continuation from `query_order_history` (when is_late == true and random < cancel_probability) |
| **Input** | `order_request_id` from `known_orders` where `is_late` |
| **Pipeline** | Single-tick |

**Steps**:
1. Update local state: `pending_orders[order_request_id].status = "cancel_requested"`
2. Emit Ch.1 event: `consumer_order_status_update` → UPDATE `consumer_orders` SET status='cancel_requested'
3. Send Ch.2 message: `CancelRequest` → target Seller agent's inbox

**Output**:
- **Ch.1**: `consumer_order_status_update`
- **Ch.2**: `CancelRequest` to Seller

---

### `receive_cancel_response`

| | |
|---|---|
| **Trigger** | Inbox: `CancelConfirmed` or `CancelRejected` message from Seller |
| **Input** | `order_request_id`, cancellation outcome |
| **Pipeline** | Single-tick |

**Steps**:
1. If `CancelConfirmed`:
   a. Update local state: `pending_orders[order_request_id].status = "cancelled"`
   b. Move to `completed_orders`
   c. Emit Ch.1 event: `consumer_order_status_update` → UPDATE `consumer_orders` SET status='cancelled'
2. If `CancelRejected`:
   a. Update local state: revert `pending_orders[order_request_id].status` to `"accepted"` (order still active)
   b. Emit Ch.1 event: `consumer_order_status_update` → UPDATE `consumer_orders` SET status='accepted'

**Output**:
- **Ch.1**: `consumer_order_status_update`

---

## Purchase Pipeline — Full Causal Chain (§6.1)

This is the most important workload pattern. A single consumer purchase spans **12+ ticks** across 5 agent types and 5 tenants.

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
       └─ store candidates in local state
       
 N+1   view_product() triggered
       └─ Ch.3: product_details
          query for candidate SKUs
          (Mode 2 → TiDB)
          
 N+2   drain inbox:
       └─ QueryResult(product_details)
       └─ apply View→Cart dropout
       └─ apply Cart→Purchase dropout
       └─ survivors → initiate_purchase()
       └─ Ch.1: consumer_purchase_intent
          (INSERT consumer_orders)
       └─ Ch.2: PlaceOrder ──────►  (in inbox)

 N+3                                drain inbox:
                                    └─ PlaceOrder received
                                    └─ queue order locally
                                    └─ Ch.3: inventory_check
                                       query (Mode 2 → TiDB)

 N+4                                drain inbox:
                                    └─ QueryResult(inventory_check)
                                    └─ decide: ACCEPT (V1: always)
                                    └─ Ch.1: store_order_accepted
                                       (INSERT store_orders,
                                        UPDATE inventory)
                                    └─ Ch.2: OrderAccepted ────►  (Consumer inbox)

 N+5   drain inbox:
       └─ OrderAccepted received
       └─ update local state
       └─ Ch.1: consumer_order_status_update
       └─ make_payment()
       └─ Ch.2: Payment ─────────►  (in inbox)

 N+6                                drain inbox:
                                    └─ Payment received
                                    └─ Ch.1: store_payment_received
                                       (INSERT payment_log)
                                    └─ Ch.2: ShipRequest ────────►  (Transport inbox)
                                    └─ Ch.2: OrderReport ──────────────────────────────► (Gov inbox)

 N+7                                                                drain inbox:          drain inbox:
                                                                    └─ ShipRequest recv   └─ OrderReport recv
                                                                    └─ create shipment    └─ Ch.1: gov_record_insert
                                                                    └─ Ch.1:                 (INSERT gov_records)
                                                                       transport_shipment_created
                                                                       (INSERT shipments, INSERT tracking_events)

 N+8                                                                update_tracking()
 ...                                                                └─ Ch.1: transport_tracking_update
                                                                     (INSERT tracking_events
                                                                      at milestones)

 N+7+T                                                              complete_delivery()
 (T=transit                                                         └─ Ch.1: transport_delivery_complete
  time)                                                                (UPDATE shipments,INSERT tracking_events)
                                                                    └─ Ch.2: DeliveryComplete ──►  (Seller inbox)

 N+8+T                              drain inbox:
                                    └─ DeliveryComplete received
                                    └─ update local state
                                    └─ Ch.2: ShipmentNotification ──►  (Consumer inbox)

 N+9+T drain inbox:
       └─ ShipmentNotification received
       └─ Ch.1: consumer_order_status_update
          (UPDATE consumer_orders
           SET status='delivered')
       └─ share_purchase()
       └─ Call Community subsystem

 N+10+T                                                                                  (Community batch:
                                                                                           update influence_edges,
                                                                                           modify trend multipliers)
```

### DB Workload Summary for One Purchase (transit time T=4 ticks)

| Tick | Tenant | SQL Operations | TiDB Pattern Tested |
|---|---|---|---|
| N | Consumer App | 2 SELECT (correlated browse) | Catalog scan + review range scan |
| N+1 | Consumer App | 1 SELECT (Mode 2 product_details) | Point lookup + JOIN |
| N+2 | Consumer App | 1 INSERT (consumer_orders) | Single-tenant point write |
| N+3 | Store | 1 SELECT (Mode 2 inventory_check) | Point lookup on inventory |
| N+4 | Store | 1 INSERT + 1 UPDATE (txn) | **Read-then-write transaction**, inventory hotspot |
| N+5 | Consumer App | 1 UPDATE (order status) | Status update |
| N+6 | Store | 1 INSERT (payment_log) | Single-tenant append |
| N+7 | Logistics | 2 INSERT (shipment + tracking) | Append-heavy tenant |
| N+7 | Analytics | 1 INSERT (gov_records) | Analytics tenant write |
| N+8..N+10 | Logistics | ~2 INSERT (tracking milestones) | Append-only table |
| N+11 | Logistics | 1 UPDATE + 1 INSERT (delivery) | Status update on shipment |
| N+12 | Consumer App | 1 UPDATE (order status) | Status update, eventual consistency |

**Total**: 1 logical purchase → **~15 SQL statements** across **4 tenants** over **12+ ticks**. No cross-tenant transaction.

---

## Cancel Pipeline (§6.6)

```
Tick   Consumer                    Seller (Store)
─────  ─────────────────────────   ────────────────────────────
 N     query_order_history()
       └─ Ch.3: order_history query
       
 N+1   drain inbox:
       └─ QueryResult(order_history)
       └─ identify late orders (is_late)
       └─ random check: P(cancel)
       └─ cancel_order()
       └─ Ch.1: consumer_order_status_update
          (UPDATE consumer_orders SET
           status='cancel_requested')
       └─ Ch.2: CancelRequest ──────►  (in inbox)

 N+2                                drain inbox:
                                    └─ CancelRequest received
                                    └─ check order status
                                    IF not yet shipped:
                                    └─ Ch.1: store_order_cancelled
                                       (UPDATE store_orders,
                                        UPDATE inventory += qty)
                                    └─ Ch.2: CancelConfirmed ──►  (Consumer inbox)
                                    IF already shipped:
                                    └─ Ch.2: CancelRejected ──►  (Consumer inbox)

 N+3   drain inbox:
       └─ CancelConfirmed/CancelRejected
       └─ Ch.1: consumer_order_status_update
          (UPDATE consumer_orders SET
           status='cancelled' or revert to 'accepted')
```

---

## Purchase Funnel Detail (§8)

### Funnel Model

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

### Stage Probabilities

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

### Funnel Configuration Schema

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

### DB Workload per Funnel Stage

| Stage | DB Operations | TiDB Pattern |
|---|---|---|
| Browse | Mode 1 correlated: `SELECT catalog WHERE category=? LIMIT 20`, `SELECT reviews WHERE sku_id IN (?)` | Category index scan, IN-list lookup |
| View | Mode 2: `product_details` query per SKU (batched) | Point lookups + JOINs on pricing and reviews |
| Cart | (none) | — |
| Purchase | Mode 1: `INSERT consumer_orders` | Single-row point write |

**Workload amplification**: If 10,000 consumers browse per tick with 20 SKUs each → 200,000 catalog SELECTs. After Stage 1 dropout (avg P=0.3), ~60,000 product_detail queries. After Stage 2 (avg P=0.7), ~42,000 cart additions. After Stage 3 (avg P=0.6), ~25,000 purchases → 25,000 INSERTs + 25,000 PlaceOrder messages to stores.
