from uuid import uuid4
import pytest
from bizsim.agents.supplier import SupplierAgent
from bizsim.domain import TenantContext
from bizsim.channels import InterAgentMessage


@pytest.fixture
def supplier_agent():
    tenant_context = TenantContext(tenant_id="supplier_tenant_1")
    scheduling_config = {"Supplier": {"produce_goods": {"cycle_ticks": 10}}}
    return SupplierAgent(
        agent_id=500,
        agent_type="Supplier",
        tenant_context=tenant_context,
        scheduling_config=scheduling_config,
    )


def test_on_restock_order(supplier_agent):
    restock_order_id = uuid4()
    payload = {"sku_id": 1, "qty": 100, "store_id": 200, "restock_order_id": restock_order_id}

    events = supplier_agent.on_restock_order(payload, from_agent=300, tick=1)

    assert len(events) == 1
    event = events[0]
    assert event.event_type == "supplier_restock_fulfilled"
    assert len(event.writes) == 1
    assert event.writes[0].pattern == "insert_purchase_order"
    assert event.writes[0].params["restock_order_id"] == str(restock_order_id)

    assert len(event.messages) == 1
    msg = event.messages[0]
    assert msg.msg_type == "ship_request"
    assert msg.payload["restock_order_id"] == str(restock_order_id)
    assert msg.payload["shipment_type"] == "restock"


def test_on_delivery_complete(supplier_agent):
    restock_order_id = uuid4()
    # First, need to have the order in memory
    supplier_agent.on_restock_order(
        {"sku_id": 1, "qty": 100, "store_id": 200, "restock_order_id": restock_order_id},
        from_agent=300,
        tick=1,
    )

    payload = {"restock_order_id": restock_order_id, "delivered_tick": 10, "shipment_id": uuid4()}

    events = supplier_agent.on_delivery_complete(payload, from_agent=1000, tick=11)

    assert len(events) == 1
    event = events[0]
    assert event.event_type == "supplier_restock_delivered"
    assert event.writes[0].pattern == "update_purchase_order"
    assert event.writes[0].params["status"] == "delivered"

    assert len(event.messages) == 1
    msg = event.messages[0]
    assert msg.msg_type == "restock_delivered"
    assert msg.to_agent == 300
    assert msg.payload["delivered_tick"] == 10


def test_handle_produce_goods(supplier_agent):
    events = supplier_agent.handle_produce_goods(tick=10)

    assert len(events) == 1
    event = events[0]
    assert event.event_type == "supplier_production_update"
    assert any(w.pattern == "update_supplier_capacity" for w in event.writes)


def test_step_processing(supplier_agent):
    restock_order_id = uuid4()
    msg = InterAgentMessage(
        msg_id=uuid4(),
        msg_type="restock_order",
        from_agent=300,
        to_agent=500,
        from_tenant="seller_tenant",
        tick_sent=1,
        payload={"sku_id": 1, "qty": 100, "store_id": 200, "restock_order_id": restock_order_id},
    )
    supplier_agent.inbox.append(msg)

    # Tick 2: drain inbox and process message
    events = supplier_agent.step(tick=2)

    # Check if on_restock_order was called and events returned
    assert any(e.event_type == "supplier_restock_fulfilled" for e in events)
