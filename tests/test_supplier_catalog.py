from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from bizsim.agents.supplier import SupplierAgent
from bizsim.domain import TenantContext


def _make_mock_catalog() -> MagicMock:
    catalog = MagicMock()
    catalog.industrial.get_bom.side_effect = lambda sku_id: (
        [{"part_id": 101, "quantity": 2}, {"part_id": 102, "quantity": 1}] if sku_id == 1 else []
    )
    catalog.industrial.get_parts_for_supplier.side_effect = lambda supplier_id: (
        [{"part_id": 101, "sku_id": 1001}, {"part_id": 102, "sku_id": 1002}]
        if supplier_id == 500
        else []
    )

    return catalog


@pytest.fixture
def supplier_agent_with_catalog():
    tenant_context = TenantContext(tenant_id="supplier_tenant_1")
    scheduling_config = {"Supplier": {"produce_goods": {"cycle_ticks": 10}}}
    catalog = _make_mock_catalog()
    peer_agents = {"transport": 1001}
    return SupplierAgent(
        agent_id=500,
        agent_type="Supplier",
        tenant_context=tenant_context,
        scheduling_config=scheduling_config,
        catalog=catalog,
        peer_agents=peer_agents,
    )


def test_on_restock_order_with_bom_enrichment(supplier_agent_with_catalog):
    restock_order_id = uuid4()
    payload = {"sku_id": 1, "qty": 100, "store_id": 200, "restock_order_id": restock_order_id}

    events = supplier_agent_with_catalog.on_restock_order(payload, from_agent=300, tick=1)

    assert len(events) == 1
    event = events[0]
    write = event.writes[0]
    assert write.pattern == "insert_purchase_order"
    assert "bom" in write.params
    assert write.params["bom"] == [{"part_id": 101, "quantity": 2}, {"part_id": 102, "quantity": 1}]

    assert len(event.messages) == 1
    assert event.messages[0].to_agent == 1001


def test_on_restock_order_without_transport(supplier_agent_with_catalog):
    supplier_agent_with_catalog.peer_agents = {}
    restock_order_id = uuid4()
    payload = {"sku_id": 1, "qty": 100, "store_id": 200, "restock_order_id": restock_order_id}

    events = supplier_agent_with_catalog.on_restock_order(payload, from_agent=300, tick=1)

    assert len(events) == 1
    event = events[0]
    assert len(event.messages) == 0


def test_handle_produce_goods_with_catalog_enrichment(supplier_agent_with_catalog):
    events = supplier_agent_with_catalog.handle_produce_goods(tick=10)

    assert len(events) == 1
    event = events[0]
    assert event.event_type == "supplier_production_update"

    write = next(w for w in event.writes if w.pattern == "update_supplier_capacity")
    assert "produced_parts" in write.params
    assert write.params["produced_parts"] == [
        {"part_id": 101, "sku_id": 1001},
        {"part_id": 102, "sku_id": 1002},
    ]
