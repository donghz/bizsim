# Supplier Agent Spec

> Extracted from: agent-behavior.md §3.3 (lines 590–665) + §6.2 supplier portion (lines 1243–1276)
> Cross-references: MESSAGES.md (ship_request, delivery_complete, restock_order, restock_delivered), EVENTS.md (supplier_*), QUERIES.md (fulfillment_overdue), PRODUCT_SYSTEM.md (sku_supplier_mapping)

## Action Catalog

### `receive_restock_order`

| | |
|---|---|
| **Trigger** | Inbox: `RestockOrder` message from Seller |
| **Input** | `sku_id`, `qty`, `store_id` (destination), `restock_order_id` |
| **Pipeline** | Single-tick (V1: always fulfill immediately) |

**Steps**:
1. Record the restock order locally
2. Emit Ch.1 event: `supplier_restock_fulfilled` → INSERT into `purchase_orders` (fulfillment record)
3. Send Ch.2 message: `ShipRequest` → Transport carrier's inbox (goods destined for the requesting Store)
   - Include `shipment_type = "restock"`

**V1 note**: No capacity check. Every restock is immediately fulfilled.

**Output**:
- **Ch.1**: `supplier_restock_fulfilled` (INSERT `purchase_orders` in Supplier ERP tenant)
- **Ch.2**: `ShipRequest` to Transport (with `destination = store_id`, `origin = supplier_id`)

---

### `receive_delivery_confirmation`

| | |
|---|---|
| **Trigger** | Inbox: `DeliveryComplete` from Transport (for restock shipments) |
| **Input** | `shipment_id`, `restock_order_id`, `delivered_tick` |
| **Pipeline** | Single-tick |

**Steps**:
1. Update local state: mark restock_order as "delivered"
2. Emit Ch.1 event: `supplier_restock_delivered` → UPDATE `purchase_orders` SET status='delivered'
3. Send Ch.2 message: `RestockDelivered` → Seller (the store that requested the restock)

**Output**:
- **Ch.1**: `supplier_restock_delivered` (UPDATE `purchase_orders` in Supplier ERP tenant)
- **Ch.2**: `RestockDelivered` to Seller

---

### `produce_goods`

| | |
|---|---|
| **Trigger** | Recurring tick schedule (see AGENT_BASE.md) |
| **Input** | Current capacity metrics |
| **Pipeline** | Single-tick |

**Steps**:
1. Update production bookkeeping counters
2. Emit Ch.1 event: `supplier_production_update` → UPDATE `suppliers` SET capacity metrics

**V1 note**: Pure bookkeeping — capacity is unlimited but we still generate the UPDATE workload for DB testing.

**Output**:
- **Ch.1**: `supplier_production_update` (UPDATE `suppliers` in Supplier ERP tenant)

---

### `query_fulfillment_status`

| | |
|---|---|
| **Trigger** | Recurring tick schedule (see AGENT_BASE.md) |
| **Input** | Supplier ID |
| **Pipeline** | Two-tick: query → receive |

**Steps**:
1. **Tick N**: Emit Ch.3 query: `fulfillment_overdue` template
2. **Tick N+1**: Receive result, update local metrics. V1: no overdue orders expected.

**Output**:
- **Ch.3**: `fulfillment_overdue` query request

---

## Pipeline Sequence: Restocking (Supplier Portion)

From §6.2 — showing the supplier's role in the restocking pipeline:

```
Tick   Seller                      Supplier                    Transport
─────  ─────────────────────────   ────────────────────────    ─────────────────────
 ...   (Seller sends RestockOrder)

 N+2                                drain inbox:
                                    └─ RestockOrder received
                                    └─ Ch.1: supplier_restock_fulfilled
                                       (INSERT purchase_orders)
                                    └─ Ch.2: ShipRequest ──────────────►  (in inbox)

 ...                                                            (Transport ships)

 N+3+T                                                          complete_delivery()
                                                                 └─ Ch.2: DeliveryComplete ──►  (Supplier inbox)

 N+4+T                              drain inbox:
                                    └─ DeliveryComplete received
                                    └─ Ch.1: supplier_restock_delivered
                                    └─ Ch.2: RestockDelivered ───► (Seller inbox)
```

## Delivery Routing

Transport sends `DeliveryComplete` with `shipment_type = "restock"` back to the Supplier (the originator of the ship request). The Supplier then forwards `RestockDelivered` to the Seller who originally requested the restock. This two-hop delivery chain ensures each agent only writes to its own tenant.
