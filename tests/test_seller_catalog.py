import pytest
from uuid import uuid4
from unittest.mock import MagicMock
from bizsim.agents.seller import SellerAgent
from bizsim.domain import TenantContext
from bizsim.product_catalog import ProductCatalog


@pytest.fixture
def mock_catalog():
    catalog = MagicMock(spec=ProductCatalog)
    return catalog


@pytest.fixture
def seller_agent(mock_catalog):
    tenant_context = TenantContext(tenant_id="store_1")
    scheduling_config = {
        "seller": {
            "evaluate_pricing": {"cycle_ticks": 100, "jitter": 5},
            "evaluate_inventory": {"cycle_ticks": 100, "jitter": 5},
        }
    }
    peer_agents = {"transport": 5555, "government": 9999}
    return SellerAgent(
        agent_id=1,
        tenant_context=tenant_context,
        scheduling_config=scheduling_config,
        catalog=mock_catalog,
        peer_agents=peer_agents,
    )


def test_on_payment_peer_lookup(seller_agent):
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
    messages = events[0].messages

    ship_req = next(m for m in messages if m.msg_type == "ship_request")
    assert ship_req.to_agent == 5555

    order_rpt = next(m for m in messages if m.msg_type == "order_report")
    assert order_rpt.to_agent == 9999


def test_on_payment_missing_peers(seller_agent):
    seller_agent.peer_agents = {}
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
    assert len(events[0].messages) == 0


def test_rule_based_pricing(seller_agent, mock_catalog):
    mock_catalog.get_skus_for_seller.return_value = [
        {"sku_id": 101, "price_floor": 8.0, "price_ceiling": 15.0, "base_price": 10.0},
        {"sku_id": 102, "price_floor": 5.0, "price_ceiling": 20.0, "base_price": 18.0},
    ]

    seller_agent.sales_cache = {"101": 15}
    seller_agent.sales_cache["102"] = 1

    events = seller_agent.on_competitor_prices_result({}, {}, tick=100)

    assert len(events) == 2

    event_101 = next(e for e in events if e.writes[0].params["sku_id"] == 101)
    assert event_101.writes[0].params["new_price"] == pytest.approx(10.5)

    event_102 = next(e for e in events if e.writes[0].params["sku_id"] == 102)
    assert event_102.writes[0].params["new_price"] == pytest.approx(17.1)


def test_pricing_bounds(seller_agent, mock_catalog):
    mock_catalog.get_skus_for_seller.return_value = [
        {"sku_id": 101, "price_floor": 10.0, "price_ceiling": 10.2, "base_price": 10.0},
    ]

    seller_agent.sales_cache = {"101": 20}

    events = seller_agent.on_competitor_prices_result({}, {}, tick=100)
    assert events[0].writes[0].params["new_price"] == 10.2


def test_on_inventory_levels_supplier_lookup(seller_agent, mock_catalog):
    data = {"inventory": [{"sku_id": 101, "qty": 5}]}

    mock_catalog.get_suppliers_for_sku.return_value = [
        {"supplier_id": 2001, "is_primary": False},
        {"supplier_id": 2002, "is_primary": True},
    ]

    events = seller_agent.on_inventory_levels_result(data, {}, tick=50)

    assert len(events) == 1
    assert events[0].messages[0].to_agent == 2002
    assert (
        seller_agent.pending_restocks[list(seller_agent.pending_restocks.keys())[0]]["supplier_id"]
        == 2002
    )
