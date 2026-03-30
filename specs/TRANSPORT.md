# Transport (Carrier) Agent Spec

> Extracted from: agent-behavior.md §3.4 (lines 669–727) + §6.2 transport portion (lines 1263–1270)
> Cross-references: MESSAGES.md (ship_request, delivery_complete), EVENTS.md (transport_*), QUERIES.md (shipment_tracking)

## Action Catalog

### `receive_ship_request`

| | |
|---|---|
| **Trigger** | Inbox: `ShipRequest` message from Seller or Supplier |
| **Input** | `order_id`, `origin_id`, `destination_id`, `items` list, `shipment_type` |
| **Pipeline** | Single-tick |

**Steps**:
1. Generate `shipment_id`
2. Calculate transit time: `base_transit_ticks + random_jitter` (from config)
3. Record shipment in local state: `active_shipments[shipment_id] = {order_id, origin, dest, start_tick, eta_tick, shipment_type, status: "in_transit"}`
4. Emit Ch.1 event: `transport_shipment_created` → INSERT `shipments` + INSERT `tracking_events` (initial "picked_up" event)

**Output**:
- **Ch.1**: `transport_shipment_created` (INSERT `shipments` + INSERT `tracking_events` in Logistics tenant)

---

### `update_tracking`

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

### `complete_delivery`

| | |
|---|---|
| **Trigger** | `update_tracking` detects transit time expired |
| **Input** | Shipment details from local state |
| **Pipeline** | Single-tick |

**Steps**:
1. Update local state: `active_shipments[shipment_id].status = "delivered"`
2. Emit Ch.1 event: `transport_delivery_complete` → UPDATE `shipments` SET status='delivered' + INSERT `tracking_events` (final "delivered" event)
3. Determine the recipient of `DeliveryComplete` based on `shipment_type`:
   - "consumer_order" → send to originating Seller
   - "restock" → send to originating Supplier
4. Send Ch.2 message: `DeliveryComplete` → recipient's inbox

**Output**:
- **Ch.1**: `transport_delivery_complete` (UPDATE `shipments` + INSERT `tracking_events` in Logistics tenant)
- **Ch.2**: `DeliveryComplete` to originating agent

---

## Shipment State Machine

```
ShipRequest received
    │
    ▼
 in_transit ──── tracking milestones (25%, 50%, 75%) ──── each emits tracking_update
    │
    │ current_tick >= eta_tick
    ▼
 delivered ──── DeliveryComplete message sent to originator
```

## Delivery Routing by `shipment_type`

The `shipment_type` field in the ShipRequest determines who receives the `DeliveryComplete` message:

| shipment_type | ShipRequest from | DeliveryComplete sent to | Next hop |
|---|---|---|---|
| `"consumer_order"` | Seller | Seller | Seller → ShipmentNotification → Consumer |
| `"restock"` | Supplier | Supplier | Supplier → RestockDelivered → Seller |

This routing ensures the delivery notification returns to the agent that originated the shipment request, maintaining the causal chain.

## DB Workload Pattern

Transport generates **append-heavy** workload in the Logistics tenant:
- `INSERT shipments` — one per shipment creation
- `INSERT tracking_events` — multiple per shipment (picked_up, milestones, delivered)
- `UPDATE shipments` — one per delivery completion (status change)

This is the classic append-only log pattern with occasional status updates.
