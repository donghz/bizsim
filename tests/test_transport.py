
import pytest

from bizsim.agents.transport import TransportAgent
from bizsim.domain import TenantContext


@pytest.fixture
def transport_agent():
    tenant_context = TenantContext(tenant_id="logistics_1")
    scheduling_config = {
        "transport": {"update_tracking": {"cycle_ticks": 1, "jitter": 0, "base_transit_ticks": 10}}
    }
    return TransportAgent(
        agent_id=100,
        agent_type="transport",
        tenant_context=tenant_context,
        scheduling_config=scheduling_config,
        seed=42,
    )


def test_receive_ship_request(transport_agent):
    payload = {
        "store_order_id": 123,
        "origin_id": 1,
        "destination_id": 2,
        "items": [{"sku_id": 10, "qty": 1}],
        "shipment_type": "consumer_order",
    }

    transport_agent.on_ship_request(payload, from_agent=50, tick=10)

    assert len(transport_agent.active_shipments) == 1
    shipment = list(transport_agent.active_shipments.values())[0]
    assert shipment["order_id"] == 123
    assert shipment["status"] == "in_transit"
    assert shipment["shipment_type"] == "consumer_order"
    assert len(transport_agent._pending_events) == 1

    event = transport_agent._pending_events[0]
    assert event.event_type == "transport_shipment_created"
    assert len(event.writes) == 2
    assert event.writes[0].pattern == "insert_shipment"
    assert event.writes[1].pattern == "insert_tracking_event"


def test_update_tracking_milestones(transport_agent):
    payload = {
        "store_order_id": 123,
        "origin_id": 1,
        "destination_id": 2,
        "items": [{"sku_id": 10, "qty": 1}],
        "shipment_type": "consumer_order",
    }

    transport_agent.on_ship_request(payload, from_agent=50, tick=0)
    shipment_id = list(transport_agent.active_shipments.keys())[0]
    shipment = transport_agent.active_shipments[shipment_id]

    shipment["start_tick"] = 0
    shipment["eta_tick"] = 10

    events = transport_agent.handle_update_tracking(tick=3)
    assert any(e.event_type == "transport_tracking_update" for e in events)
    assert 25 in shipment["milestones_reached"]

    events = transport_agent.handle_update_tracking(tick=6)
    assert any(e.event_type == "transport_tracking_update" for e in events)
    assert 50 in shipment["milestones_reached"]

    events = transport_agent.handle_update_tracking(tick=8)
    assert any(e.event_type == "transport_tracking_update" for e in events)
    assert 75 in shipment["milestones_reached"]


def test_complete_delivery_consumer(transport_agent):
    payload = {
        "store_order_id": 123,
        "origin_id": 1,
        "destination_id": 2,
        "items": [{"sku_id": 10, "qty": 1}],
        "shipment_type": "consumer_order",
    }

    transport_agent.on_ship_request(payload, from_agent=50, tick=0)
    shipment_id = list(transport_agent.active_shipments.keys())[0]
    shipment = transport_agent.active_shipments[shipment_id]
    shipment["eta_tick"] = 10

    events = transport_agent.handle_update_tracking(tick=10)

    delivery_event = next(e for e in events if e.event_type == "transport_delivery_complete")
    assert delivery_event.writes[0].pattern == "update_shipment"
    assert delivery_event.writes[0].params["status"] == "delivered"

    assert len(delivery_event.messages) == 1
    msg = delivery_event.messages[0]
    assert msg.msg_type == "delivery_complete"
    assert msg.to_agent == 50
    assert msg.payload["shipment_type"] == "consumer_order"
    assert "store_order_id" in msg.payload

    assert shipment_id not in transport_agent.active_shipments


def test_complete_delivery_restock(transport_agent):
    payload = {
        "restock_order_id": "restock-uuid",
        "origin_id": 1,
        "destination_id": 2,
        "items": [{"sku_id": 10, "qty": 100}],
        "shipment_type": "restock",
    }

    transport_agent.on_ship_request(payload, from_agent=60, tick=0)
    shipment_id = list(transport_agent.active_shipments.keys())[0]
    shipment = transport_agent.active_shipments[shipment_id]
    shipment["eta_tick"] = 10

    events = transport_agent.handle_update_tracking(tick=10)

    delivery_event = next(e for e in events if e.event_type == "transport_delivery_complete")
    msg = delivery_event.messages[0]
    assert msg.to_agent == 60
    assert msg.payload["shipment_type"] == "restock"
    assert msg.payload["restock_order_id"] == "restock-uuid"
