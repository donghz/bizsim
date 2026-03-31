from typing import Any
from uuid import uuid4

from bizsim.agents.base import BaseAgent
from bizsim.channels import InterAgentMessage
from bizsim.domain import ActionEvent, TenantContext, WritePattern


class TransportAgent(BaseAgent):
    def __init__(
        self,
        agent_id: int,
        agent_type: str,
        tenant_context: TenantContext,
        scheduling_config: dict[str, Any],
        seed: int = 42,
    ):
        super().__init__(agent_id, agent_type, tenant_context, scheduling_config, seed)
        self.active_shipments: dict[str, dict[str, Any]] = {}
        self._pending_events: list[ActionEvent] = []

    def on_ship_request(self, payload: dict[str, Any], from_agent: int, tick: int) -> None:
        shipment_id = str(uuid4())

        config = self._scheduling.get("update_tracking", {})
        base_transit_ticks = config.get("base_transit_ticks", 10)
        jitter = hash(shipment_id) % 3
        transit_ticks = base_transit_ticks + jitter

        origin_id = payload["origin_id"]
        destination_id = payload["destination_id"]
        shipment_type = payload["shipment_type"]

        order_id = payload.get("store_order_id") or payload.get("restock_order_id")

        self.active_shipments[shipment_id] = {
            "shipment_id": shipment_id,
            "order_id": order_id,
            "origin_id": origin_id,
            "destination_id": destination_id,
            "items": payload["items"],
            "shipment_type": shipment_type,
            "start_tick": tick,
            "eta_tick": tick + transit_ticks,
            "status": "in_transit",
            "from_agent": from_agent,
            "milestones_reached": set(),
        }

        write_shipment = WritePattern(
            pattern="insert_shipment",
            params={
                "shipment_id": shipment_id,
                "order_id": order_id,
                "origin_id": origin_id,
                "dest_id": destination_id,
                "carrier_id": self.agent_id,
                "status": "in_transit",
                "eta_tick": tick + transit_ticks,
            },
        )
        write_tracking = WritePattern(
            pattern="insert_tracking_event",
            params={
                "shipment_id": shipment_id,
                "status": "picked_up",
                "location": origin_id,
                "tick": tick,
            },
        )

        event = self._emitter.emit(
            event_type="transport_shipment_created",
            tick=tick,
            writes=[write_shipment, write_tracking],
        )
        self._pending_events.append(event)

    def handle_update_tracking(self, tick: int) -> list[ActionEvent]:
        events = []
        events.extend(self._pending_events)
        self._pending_events = []

        completed_shipments = []

        for shipment_id, shipment in self.active_shipments.items():
            if shipment["status"] != "in_transit":
                continue

            if tick >= shipment["eta_tick"]:
                events.append(self._complete_delivery(shipment_id, tick))
                completed_shipments.append(shipment_id)
                continue

            total_duration = shipment["eta_tick"] - shipment["start_tick"]
            elapsed = tick - shipment["start_tick"]
            progress = elapsed / total_duration if total_duration > 0 else 1.0

            milestone = None
            if progress >= 0.75 and 75 not in shipment["milestones_reached"]:
                milestone = 75
            elif progress >= 0.50 and 50 not in shipment["milestones_reached"]:
                milestone = 50
            elif progress >= 0.25 and 25 not in shipment["milestones_reached"]:
                milestone = 25

            if milestone:
                shipment["milestones_reached"].add(milestone)
                location_estimate = f"Progress {milestone}%"
                write_tracking = WritePattern(
                    pattern="insert_tracking_event",
                    params={
                        "shipment_id": shipment_id,
                        "status": "in_transit",
                        "location_estimate": location_estimate,
                        "tick": tick,
                    },
                )
                events.append(
                    self._emitter.emit(
                        event_type="transport_tracking_update",
                        tick=tick,
                        writes=[write_tracking],
                    )
                )

        for sid in completed_shipments:
            self.active_shipments.pop(sid)

        return events

    def _complete_delivery(self, shipment_id: str, tick: int) -> ActionEvent:
        shipment = self.active_shipments[shipment_id]
        shipment["status"] = "delivered"

        write_shipment = WritePattern(
            pattern="update_shipment",
            params={
                "shipment_id": shipment_id,
                "status": "delivered",
                "delivered_tick": tick,
            },
        )
        write_tracking = WritePattern(
            pattern="insert_tracking_event",
            params={
                "shipment_id": shipment_id,
                "status": "delivered",
                "location": shipment["destination_id"],
                "tick": tick,
            },
        )

        recipient_id = shipment["from_agent"]

        payload = {
            "shipment_id": shipment_id,
            "delivered_tick": tick,
            "shipment_type": shipment["shipment_type"],
        }
        if shipment["shipment_type"] == "consumer_order":
            payload["store_order_id"] = shipment["order_id"]
        else:
            payload["restock_order_id"] = shipment["order_id"]

        message = InterAgentMessage(
            msg_id=uuid4(),
            msg_type="delivery_complete",
            from_agent=self.agent_id,
            to_agent=recipient_id,
            from_tenant=self.tenant_id,
            tick_sent=tick,
            payload=payload,
        )

        return self._emitter.emit(
            event_type="transport_delivery_complete",
            tick=tick,
            writes=[write_shipment, write_tracking],
            messages=[message],
        )
