from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from bizsim.agents.base import BaseAgent
from bizsim.channels import InterAgentMessage
from bizsim.domain import ActionEvent, ReadPattern, TenantContext, WritePattern

if TYPE_CHECKING:
    from bizsim.market import MarketFactory


class SellerAgent(BaseAgent):
    def __init__(
        self,
        agent_id: int,
        tenant_context: TenantContext,
        scheduling_config: dict[str, Any],
        seed: int = 42,
        *,
        catalog: "MarketFactory | None" = None,
        peer_agents: dict[str, int] | None = None,
    ):
        super().__init__(
            agent_id,
            "seller",
            tenant_context,
            scheduling_config,
            seed,
            catalog=catalog,
            peer_agents=peer_agents,
        )
        self.pending_incoming: dict[UUID, dict[str, Any]] = {}
        self.orders: dict[UUID, dict[str, Any]] = {}
        self.pending_restocks: dict[UUID, dict[str, Any]] = {}
        self.sales_cache: dict[str, Any] = {}

    def _send_message(
        self, msg_type: str, to_agent: int, payload: dict[str, Any], tick: int
    ) -> InterAgentMessage:
        return InterAgentMessage(
            msg_id=uuid4(),
            msg_type=msg_type,
            from_agent=self.agent_id,
            to_agent=to_agent,
            from_tenant=self.tenant_id,
            tick_sent=tick,
            payload=payload,
        )

    def on_place_order(
        self, payload: dict[str, Any], from_agent: int, tick: int
    ) -> list[ActionEvent]:
        order_request_id = payload["order_request_id"]
        sku_id = payload["sku_id"]
        qty = payload["qty"]
        offered_price = payload.get("offered_price")

        self.pending_incoming[order_request_id] = {
            "sku_id": sku_id,
            "qty": qty,
            "consumer_id": from_agent,
            "offered_price": offered_price,
            "status": "queued",
        }

        req = self.emit_query(
            "inventory_check",
            {"seller_id": self.agent_id, "sku_id": sku_id},
            {"order_request_id": order_request_id},
        )
        return [
            self._emitter.emit(
                "query_request_event",
                tick,
                reads=[ReadPattern("inventory_check", {"sku_id": sku_id})],
                queries=[req],
            )
        ]

    def on_inventory_check_result(
        self, data: dict[str, Any], context: dict[str, Any], tick: int
    ) -> list[ActionEvent]:
        order_request_id = context["order_request_id"]
        order = self.pending_incoming.pop(order_request_id, None)
        if not order:
            return []

        sku_id = order["sku_id"]
        qty = order["qty"]
        price = order["offered_price"]
        consumer_id = order["consumer_id"]

        store_order_id = abs(hash(order_request_id)) % 10**8
        self.orders[order_request_id] = {
            **order,
            "store_order_id": store_order_id,
            "status": "accepted",
        }

        event = self._emitter.emit(
            "store_order_accepted",
            tick,
            writes=[
                WritePattern(
                    "insert_store_order",
                    {
                        "order_request_id": order_request_id,
                        "sku_id": sku_id,
                        "qty": qty,
                        "price": price,
                        "consumer_id": consumer_id,
                        "status": "accepted",
                    },
                ),
                WritePattern("update_inventory", {"sku_id": sku_id, "qty_delta": -qty}),
            ],
            messages=[
                self._send_message(
                    "order_accepted",
                    consumer_id,
                    {
                        "order_request_id": order_request_id,
                        "store_order_id": store_order_id,
                        "confirmed_price": price,
                        "eta_ticks": 5,
                    },
                    tick,
                )
            ],
        )
        return [event]

    def on_payment(self, payload: dict[str, Any], from_agent: int, tick: int) -> list[ActionEvent]:
        order_request_id = payload["order_request_id"]
        store_order_id = payload["store_order_id"]
        amount = payload["amount"]

        order = self.orders.get(order_request_id)
        if not order or order["status"] != "accepted":
            return []

        order["status"] = "paid"
        transport_agent_id = self.peer_agents.get("transport")

        messages = []
        if transport_agent_id:
            messages.append(
                self._send_message(
                    "ship_request",
                    transport_agent_id,
                    {
                        "shipment_request_id": str(uuid4()),
                        "store_order_id": store_order_id,
                        "origin_id": self.agent_id,
                        "destination_id": from_agent,
                        "items": [{"sku_id": order["sku_id"], "qty": order["qty"]}],
                        "shipment_type": "consumer_order",
                    },
                    tick,
                )
            )

        gov_agent_id = self.peer_agents.get("government")
        if gov_agent_id:
            messages.append(
                self._send_message(
                    "order_report",
                    gov_agent_id,
                    {
                        "store_order_id": store_order_id,
                        "seller_id": self.agent_id,
                        "sku_id": order["sku_id"],
                        "qty": order["qty"],
                        "amount": amount,
                        "tick": tick,
                    },
                    tick,
                )
            )

        event = self._emitter.emit(
            "store_payment_received",
            tick,
            writes=[
                WritePattern(
                    "insert_payment_log",
                    {
                        "store_order_id": store_order_id,
                        "amount": amount,
                        "payer_id": from_agent,
                        "tick": tick,
                    },
                )
            ],
            messages=messages,
        )
        return [event]

    def on_delivery_complete(
        self, payload: dict[str, Any], from_agent: int, tick: int
    ) -> list[ActionEvent]:
        shipment_type = payload.get("shipment_type")
        if shipment_type != "consumer_order":
            return []

        store_order_id = payload.get("store_order_id")
        order_request_id = None
        for rid, o in self.orders.items():
            if o.get("store_order_id") == store_order_id:
                order_request_id = rid
                break

        if not order_request_id:
            return []

        self.orders[order_request_id]["status"] = "delivered"

        msg = self._send_message(
            "shipment_notification",
            self.orders[order_request_id]["consumer_id"],
            {
                "order_request_id": order_request_id,
                "store_order_id": store_order_id,
                "shipment_id": payload["shipment_id"],
                "delivered_tick": tick,
            },
            tick,
        )

        return [self._emitter.emit("store_delivery_confirmed", tick, messages=[msg])]

    def on_restock_delivered(
        self, payload: dict[str, Any], from_agent: int, tick: int
    ) -> list[ActionEvent]:
        restock_order_id = payload["restock_order_id"]
        sku_id = payload["sku_id"]
        qty = payload["qty"]

        if restock_order_id in self.pending_restocks:
            self.pending_restocks[restock_order_id]["status"] = "received"

        event = self._emitter.emit(
            "store_inventory_update",
            tick,
            writes=[WritePattern("update_inventory", {"sku_id": sku_id, "qty_delta": qty})],
        )
        return [event]

    def on_cancel_request(
        self, payload: dict[str, Any], from_agent: int, tick: int
    ) -> list[ActionEvent]:
        order_request_id = payload["order_request_id"]
        order = self.orders.get(order_request_id)

        if not order:
            return []

        if order["status"] == "accepted":
            order["status"] = "cancelled"

            event = self._emitter.emit(
                "store_order_cancelled",
                tick,
                writes=[
                    WritePattern(
                        "update_store_order",
                        {"order_request_id": order_request_id, "status": "cancelled"},
                    ),
                    WritePattern(
                        "update_inventory", {"sku_id": order["sku_id"], "qty_delta": order["qty"]}
                    ),
                ],
                messages=[
                    self._send_message(
                        "cancel_confirmed", from_agent, {"order_request_id": order_request_id}, tick
                    )
                ],
            )
            return [event]
        else:
            msg = self._send_message(
                "cancel_rejected",
                from_agent,
                {"order_request_id": order_request_id, "reason": "order_in_transit_or_delivered"},
                tick,
            )
            return [self._emitter.emit("store_cancel_rejected", tick, messages=[msg])]

    def handle_evaluate_pricing(self, tick: int) -> list[ActionEvent]:
        req1 = self.emit_query(
            "sales_analytics", {"seller_id": self.agent_id, "window_ticks": 200}, {}
        )
        req2 = self.emit_query("competitor_prices", {"category": "general"}, {})

        return [
            self._emitter.emit(
                "query_request_event",
                tick,
                reads=[
                    ReadPattern("sales_analytics", {"seller_id": self.agent_id}),
                    ReadPattern("competitor_prices", {"category": "general"}),
                ],
                queries=[req1, req2],
            )
        ]

    def on_sales_analytics_result(
        self, data: dict[str, Any], context: dict[str, Any], tick: int
    ) -> list[ActionEvent]:
        self.sales_cache = data
        return []

    def on_competitor_prices_result(
        self, data: dict[str, Any], context: dict[str, Any], tick: int
    ) -> list[ActionEvent]:
        if not self.catalog:
            return []

        skus = self.catalog.consumer.get_skus_for_seller(self.agent_id)
        events = []

        for sku_info in skus:
            sku_id = sku_info["sku_id"]
            price_floor = sku_info.get("price_floor", 0.0)
            price_ceiling = sku_info.get("price_ceiling", 1000000.0)
            base_price = sku_info.get("base_price", 100.0)

            current_sales = self.sales_cache.get(str(sku_id), 0)
            price_change_percent = 0.0
            if current_sales > 10:
                price_change_percent = 0.05
            elif current_sales < 2:
                price_change_percent = -0.05

            new_price = base_price * (1 + price_change_percent)
            new_price = max(price_floor, min(price_ceiling, new_price))

            events.append(
                self._emitter.emit(
                    "store_price_update",
                    tick,
                    reads=[ReadPattern("select_current_price", {"sku_id": sku_id})],
                    writes=[
                        WritePattern(
                            "update_store_pricing",
                            {
                                "sku_id": sku_id,
                                "old_price": base_price,
                                "new_price": new_price,
                                "tick": tick,
                            },
                        )
                    ],
                )
            )
        return events

    def handle_evaluate_inventory(self, tick: int) -> list[ActionEvent]:
        req = self.emit_query("inventory_levels", {"seller_id": self.agent_id}, {})
        return [
            self._emitter.emit(
                "query_request_event",
                tick,
                reads=[ReadPattern("inventory_levels", {"seller_id": self.agent_id})],
                queries=[req],
            )
        ]

    def on_inventory_levels_result(
        self, data: dict[str, Any], context: dict[str, Any], tick: int
    ) -> list[ActionEvent]:
        messages = []
        for item in data.get("inventory", []):
            sku_id = item["sku_id"]
            qty = item["qty"]
            if qty < 10:
                supplier_id = None
                if self.catalog:
                    suppliers = self.catalog.industrial.get_suppliers_for_sku(sku_id)
                    primary_suppliers = [s for s in suppliers if s.get("is_primary")]
                    if primary_suppliers:
                        supplier_id = primary_suppliers[0].get("supplier_id")
                    elif suppliers:
                        supplier_id = suppliers[0].get("supplier_id")

                if supplier_id is None:
                    continue

                restock_order_id = uuid4()
                self.pending_restocks[restock_order_id] = {
                    "sku_id": sku_id,
                    "qty": 50,
                    "supplier_id": supplier_id,
                    "status": "ordered",
                }
                messages.append(
                    self._send_message(
                        "restock_order",
                        supplier_id,
                        {
                            "restock_order_id": str(restock_order_id),
                            "sku_id": sku_id,
                            "qty": 50,
                            "store_id": self.agent_id,
                        },
                        tick,
                    )
                )

        if messages:
            return [self._emitter.emit("store_restock_initiated", tick, messages=messages)]
        return []
