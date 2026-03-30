# Ch.1 Action Events — Shared Reference

> Extracted from: agent-behavior.md §5.2 (lines 1033–1108)

## Envelope

All Ch.1 events share a common envelope:

```
ActionEvent {
    event_id:      uuid            # unique event ID
    event_type:    string          # event type (see tables below)
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

## Consumer Events

| Event Type | Tenant | Correlated Reads (Mode 1) | Writes (Mode 1) | Description |
|---|---|---|---|---|
| `consumer_browse` | Consumer App | `browse_catalog: {category, limit: 20}`, `check_reviews: {sku_ids}` | (none — read-only) | Consumer browses products, generates catalog scan + review reads |
| `consumer_purchase_intent` | Consumer App | (none) | `insert_consumer_order: {order_request_id, sku_id, qty, seller_id, offered_price, status: "requested"}` | Consumer records purchase intent |
| `consumer_order_status_update` | Consumer App | (none) | `update_consumer_order: {order_request_id, status}` | Consumer updates order status (accepted, delivered, cancel_requested, cancelled) |

## Seller Events

| Event Type | Tenant | Correlated Reads (Mode 1) | Writes (Mode 1) | Description |
|---|---|---|---|---|
| `store_order_accepted` | Store (per-store) | `check_inventory: {sku_id}` | `insert_store_order: {order_request_id, sku_id, qty, price, consumer_id, status: "accepted"}`, `update_inventory: {sku_id, qty_delta: -N}` | Store accepts order and decrements inventory |
| `store_payment_received` | Store (per-store) | (none) | `insert_payment_log: {store_order_id, amount, payer_id, tick}` | Store logs payment receipt |
| `store_order_cancelled` | Store (per-store) | (none) | `update_store_order: {order_request_id, status: "cancelled"}`, `update_inventory: {sku_id, qty_delta: +N}` | Store cancels order and restores inventory |
| `store_inventory_update` | Store (per-store) | (none) | `update_inventory: {sku_id, qty_delta: +N}` | Store inventory increment from restocked goods delivery (NOT used for consumer order delivery — consumer delivery does not change inventory) |
| `store_price_update` | Store (per-store) | `select_current_price: {sku_id}` | `update_store_pricing: {sku_id, old_price, new_price, tick}` | Store updates product price |

## Supplier Events

| Event Type | Tenant | Correlated Reads (Mode 1) | Writes (Mode 1) | Description |
|---|---|---|---|---|
| `supplier_restock_fulfilled` | Supplier ERP | (none) | `insert_purchase_order: {restock_order_id, sku_id, qty, store_id, status: "fulfilled"}` | Supplier records fulfilled restock |
| `supplier_restock_delivered` | Supplier ERP | (none) | `update_purchase_order: {restock_order_id, status: "delivered"}` | Supplier marks restock order as delivered |
| `supplier_production_update` | Supplier ERP | `select_capacity: {supplier_id}` | `update_supplier_capacity: {supplier_id, produced_qty, current_capacity}` | Periodic production bookkeeping |

## Transport Events

| Event Type | Tenant | Correlated Reads (Mode 1) | Writes (Mode 1) | Description |
|---|---|---|---|---|
| `transport_shipment_created` | Logistics | (none) | `insert_shipment: {shipment_id, order_id, origin_id, dest_id, carrier_id, status: "in_transit", eta_tick}`, `insert_tracking_event: {shipment_id, status: "picked_up", location: origin, tick}` | New shipment created |
| `transport_tracking_update` | Logistics | (none) | `insert_tracking_event: {shipment_id, status: "in_transit", location_estimate, tick}` | Tracking milestone |
| `transport_delivery_complete` | Logistics | (none) | `update_shipment: {shipment_id, status: "delivered", delivered_tick}`, `insert_tracking_event: {shipment_id, status: "delivered", location: destination, tick}` | Shipment delivered |

## Government Events

| Event Type | Tenant | Correlated Reads (Mode 1) | Writes (Mode 1) | Description |
|---|---|---|---|---|
| `gov_record_insert` | Analytics | (none) | `insert_gov_record: {entity_type, entity_id, report_type, metrics_json, tick}` | Government records a report |
| `gov_statistics_insert` | Analytics | (none) | `insert_statistics: {period, gdp, transaction_volume, avg_price_index, active_sellers, active_consumers, tick}` | Government publishes computed statistics |

## Community Events

| Event Type | Tenant | Correlated Reads (Mode 1) | Writes (Mode 1) | Description |
|---|---|---|---|---|
| `community_propagation_batch` | Social Graph | (none) | `batch_update_influence_edges: {edges: [{source, target, new_weight}]}` | Community subsystem strengthens edges that successfully propagated influence |
