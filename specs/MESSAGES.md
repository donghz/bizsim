# Ch.2 Inter-Agent Messages — Shared Reference

> Extracted from: agent-behavior.md §5.1 (lines 991–1029)

## Envelope

All Ch.2 messages share a common envelope:

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

## Message Type Definitions

| msg_type | From → To | Payload Fields | Description |
|---|---|---|---|
| `place_order` | Consumer → Seller | `order_request_id: uuid`, `sku_id: int`, `qty: int`, `offered_price: decimal` | Consumer requests to purchase a product |
| `order_accepted` | Seller → Consumer | `order_request_id: uuid`, `store_order_id: int`, `confirmed_price: decimal`, `eta_ticks: int` | Seller confirms the order |
| `order_rejected` | Seller → Consumer | `order_request_id: uuid`, `reason: string` | Seller rejects the order (V2 only — not used in V1) |
| `payment` | Consumer → Seller | `order_request_id: uuid`, `store_order_id: int`, `amount: decimal`, `payer_id: int` | Consumer pays for accepted order |
| `ship_request` | Seller → Transport | `shipment_request_id: uuid`, `store_order_id: int`, `origin_id: int`, `destination_id: int`, `items: [{sku_id: int, qty: int}]`, `shipment_type: string` | Seller requests shipment after payment ("consumer_order") |
| `ship_request` | Supplier → Transport | `restock_order_id: uuid`, `origin_id: int`, `destination_id: int`, `items: [{sku_id: int, qty: int}]`, `shipment_type: string` | Supplier ships restocked goods to seller ("restock") |
| `delivery_complete` | Transport → Seller/Supplier | `shipment_id: uuid`, `store_order_id: int` or `restock_order_id: uuid`, `delivered_tick: int`, `shipment_type: string` | Shipment delivered. Routed by shipment_type: consumer_order → Seller, restock → Supplier |
| `shipment_notification` | Seller → Consumer | `order_request_id: uuid`, `store_order_id: int`, `shipment_id: uuid`, `delivered_tick: int` | Seller notifies consumer of delivery |
| `order_report` | Seller → Government | `store_order_id: int`, `seller_id: int`, `sku_id: int`, `qty: int`, `amount: decimal`, `tick: int` | Seller reports completed transaction |
| `restock_order` | Seller → Supplier | `restock_order_id: uuid`, `sku_id: int`, `qty: int`, `store_id: int` | Seller requests inventory replenishment |
| `cancel_request` | Consumer → Seller | `order_request_id: uuid`, `consumer_id: int`, `reason: string` | Consumer requests cancellation of an order |
| `cancel_confirmed` | Seller → Consumer | `order_request_id: uuid` | Seller confirms order cancellation |
| `cancel_rejected` | Seller → Consumer | `order_request_id: uuid`, `reason: string` | Seller rejects cancellation (order already shipped) |
| `restock_delivered` | Supplier → Seller | `restock_order_id: uuid`, `sku_id: int`, `qty: int`, `delivered_tick: int` | Supplier notifies seller that restocked goods have been delivered |
| `disruption_report` | Supplier → Government | `supplier_id: int`, `part_id: int`, `severity: string`, `tick: int` | V2: Supplier reports supply disruption |

## Notes

- `SharePurchase` is **not** a Ch.2 message. It is delivered via direct function call to the Community Subsystem (see COMMUNITY.md).
- Ch.2 messages are **in-memory only** — they never touch the DB or cross the translator boundary.
- Messages are appended to the target agent's inbox and processed next tick during inbox drain.
- Inbox processing order: QueryResult items first (sorted by query_id), then InterAgentMessage items (sorted by tick_sent, from_agent). See AGENT_BASE.md §4.4.
