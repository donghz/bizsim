from typing import Any
from uuid import uuid4

from bizsim.agents.base import BaseAgent
from bizsim.channels import InterAgentMessage
from bizsim.domain import ActionEvent, ReadPattern, WritePattern


class SupplierAgent(BaseAgent):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._orders: dict[str, dict[str, Any]] = {}

    def on_restock_order(
        self, payload: dict[str, Any], from_agent: int, tick: int
    ) -> list[ActionEvent]:
        sku_id = payload["sku_id"]
        qty = payload["qty"]
        store_id = payload["store_id"]
        restock_order_id = payload["restock_order_id"]

        self._orders[str(restock_order_id)] = {
            "seller_id": from_agent,
            "sku_id": sku_id,
            "qty": qty,
        }

        params = {
            "restock_order_id": str(restock_order_id),
            "sku_id": sku_id,
            "qty": qty,
            "store_id": store_id,
            "status": "fulfilled",
        }

        if self.catalog:
            bom: list[dict[str, Any]] = self.catalog.industrial.get_bom(sku_id)
            if bom:
                params["bom"] = bom

        write = WritePattern(
            pattern="insert_purchase_order",
            params=params,
        )

        messages = []
        transport_id = self.peer_agents.get("transport")

        if transport_id:
            msg = InterAgentMessage(
                msg_id=uuid4(),
                msg_type="ship_request",
                from_agent=self.agent_id,
                to_agent=transport_id,
                from_tenant=self.tenant_id,
                tick_sent=tick,
                payload={
                    "restock_order_id": str(restock_order_id),
                    "origin_id": self.agent_id,
                    "destination_id": store_id,
                    "items": [{"sku_id": sku_id, "qty": qty}],
                    "shipment_type": "restock",
                },
            )
            messages.append(msg)

        event = self._emitter.emit(
            event_type="supplier_restock_fulfilled",
            tick=tick,
            writes=[write],
            messages=messages,
        )
        return [event]

    def on_delivery_complete(
        self, payload: dict[str, Any], from_agent: int, tick: int
    ) -> list[ActionEvent]:
        """
        Processes DeliveryComplete from Transport and notifies Seller.
        """
        restock_order_id = payload["restock_order_id"]
        delivered_tick = payload["delivered_tick"]

        order_info = self._orders.get(str(restock_order_id))
        if not order_info:
            return []

        # Ch.1: Mark order as delivered.
        write = WritePattern(
            pattern="update_purchase_order",
            params={
                "restock_order_id": str(restock_order_id),
                "status": "delivered",
            },
        )

        # Ch.2: Forward RestockDelivered to Seller.
        msg = InterAgentMessage(
            msg_id=uuid4(),
            msg_type="restock_delivered",
            from_agent=self.agent_id,
            to_agent=order_info["seller_id"],
            from_tenant=self.tenant_id,
            tick_sent=tick,
            payload={
                "restock_order_id": str(restock_order_id),
                "sku_id": order_info["sku_id"],
                "qty": order_info["qty"],
                "delivered_tick": delivered_tick,
            },
        )

        event = self._emitter.emit(
            event_type="supplier_restock_delivered",
            tick=tick,
            writes=[write],
            messages=[msg],
        )
        return [event]

    def handle_produce_goods(self, tick: int) -> list[ActionEvent]:
        """
        Handles periodic production bookkeeping.
        """
        params: dict[str, Any] = {
            "supplier_id": self.agent_id,
            "produced_qty": 0,
            "current_capacity": 1000000,
        }

        if self.catalog:
            produced_parts = self.catalog.industrial.get_parts_for_supplier(self.agent_id)
            if produced_parts:
                params["produced_parts"] = produced_parts

        event = self._emitter.emit(
            event_type="supplier_production_update",
            tick=tick,
            reads=[ReadPattern(pattern="select_capacity", params={"supplier_id": self.agent_id})],
            writes=[
                WritePattern(
                    pattern="update_supplier_capacity",
                    params=params,
                )
            ],
        )
        return [event]
