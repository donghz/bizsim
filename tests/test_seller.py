import pytest
from uuid import uuid4
from unittest.mock import MagicMock
from bizsim.agents.seller import SellerAgent
from bizsim.domain import TenantContext
from bizsim.product_catalog import ProductCatalog


@pytest.fixture
def seller_agent():
    tenant_context = TenantContext(tenant_id="store_1")
    scheduling_config = {
        "seller": {
            "evaluate_pricing": {"cycle_ticks": 100, "jitter": 5},
            "evaluate_inventory": {"cycle_ticks": 100, "jitter": 5},
        }
    }
    peer_agents = {"transport": 5000, "government": 9000}
    return SellerAgent(
        agent_id=1,
        tenant_context=tenant_context,
        scheduling_config=scheduling_config,
        peer_agents=peer_agents,
    )


def test_on_place_order(seller_agent):
    order_request_id = uuid4()
    payload = {"order_request_id": order_request_id, "sku_id": 101, "qty": 2, "offered_price": 10.5}
    events = seller_agent.on_place_order(payload, from_agent=2, tick=1)

    assert len(events) == 1
    assert events[0].event_type == "query_request_event"
    assert order_request_id in seller_agent.pending_incoming
    assert seller_agent.pending_incoming[order_request_id]["sku_id"] == 101


def test_on_inventory_check_result(seller_agent):
    order_request_id = uuid4()
    seller_agent.pending_incoming[order_request_id] = {
        "sku_id": 101,
        "qty": 2,
        "consumer_id": 2,
        "offered_price": 10.5,
        "status": "queued",
    }

    events = seller_agent.on_inventory_check_result(
        data={"qty": 10}, context={"order_request_id": order_request_id}, tick=2
    )

    assert len(events) == 1
    assert events[0].event_type == "store_order_accepted"
    assert order_request_id in seller_agent.orders
    assert seller_agent.orders[order_request_id]["status"] == "accepted"

    # Check if OrderAccepted message is present
    messages = events[0].messages
    assert len(messages) == 1
    assert messages[0].msg_type == "order_accepted"


def test_on_payment(seller_agent):
    order_request_id = uuid4()
    store_order_id = 12345
    seller_agent.orders[order_request_id] = {
        "sku_id": 101,
        "qty": 2,
        "consumer_id": 2,
        "offered_price": 10.5,
        "store_order_id": store_order_id,
        "status": "accepted",
    }

    payload = {
        "order_request_id": order_request_id,
        "store_order_id": store_order_id,
        "amount": 21.0,
        "payer_id": 2,
    }

    events = seller_agent.on_payment(payload, from_agent=2, tick=3)

    assert len(events) == 1
    assert events[0].event_type == "store_payment_received"
    assert seller_agent.orders[order_request_id]["status"] == "paid"

    # Should have ShipRequest and OrderReport messages
    messages = events[0].messages
    assert any(m.msg_type == "ship_request" for m in messages)
    assert any(m.msg_type == "order_report" for m in messages)


def test_on_delivery_complete(seller_agent):
    order_request_id = uuid4()
    store_order_id = 12345
    seller_agent.orders[order_request_id] = {
        "sku_id": 101,
        "qty": 2,
        "consumer_id": 2,
        "offered_price": 10.5,
        "store_order_id": store_order_id,
        "status": "paid",
    }

    payload = {
        "shipment_id": str(uuid4()),
        "store_order_id": store_order_id,
        "shipment_type": "consumer_order",
    }

    events = seller_agent.on_delivery_complete(payload, from_agent=5000, tick=10)

    assert len(events) == 1
    assert events[0].event_type == "store_delivery_confirmed"
    assert seller_agent.orders[order_request_id]["status"] == "delivered"


def test_handle_evaluate_inventory(seller_agent):
    events = seller_agent.handle_evaluate_inventory(tick=20)
    assert len(events) == 1
    assert events[0].event_type == "query_request_event"
    assert any(
        q.query_template == "inventory_levels" for q in seller_agent.pending_queries.values()
    )


def test_on_inventory_levels_result(seller_agent):
    mock_catalog = MagicMock(spec=ProductCatalog)
    mock_catalog.get_suppliers_for_sku.return_value = [{"supplier_id": 2000, "is_primary": True}]
    seller_agent.catalog = mock_catalog

    data = {
        "inventory": [
            {"sku_id": 101, "qty": 5},  # Below threshold (10)
            {"sku_id": 102, "qty": 20},  # Above threshold
        ]
    }

    events = seller_agent.on_inventory_levels_result(data, context={}, tick=21)

    assert len(events) == 1
    assert events[0].event_type == "store_restock_initiated"
    assert len(events[0].messages) == 1
    assert events[0].messages[0].msg_type == "restock_order"
    assert events[0].messages[0].payload["sku_id"] == 101
