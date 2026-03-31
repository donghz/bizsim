from unittest.mock import MagicMock

import pytest

from bizsim.agents.consumer import ConsumerAgent
from bizsim.domain import TenantContext
from bizsim.events import QueryResult


@pytest.fixture
def tenant_context():
    return TenantContext(tenant_id="consumer_tenant")


@pytest.fixture
def scheduling_config():
    return {
        "consumer": {
            "shopping": {"cycle_ticks": 10, "jitter": 0},
            "order_history_check": {"cycle_ticks": 50, "jitter": 0},
        }
    }


@pytest.fixture
def consumer_profile():
    return {"interest": {"Groceries": 1.0}, "price_sensitivity": 0.5, "urgency": {"Groceries": 0.9}}


def _make_mock_catalog():
    consumer = MagicMock()
    catalog = MagicMock()
    catalog.consumer = consumer
    catalog.industrial = MagicMock()
    return catalog


def test_consumer_no_catalog_degradation(tenant_context, scheduling_config, consumer_profile):
    agent = ConsumerAgent(1, tenant_context, scheduling_config, consumer_profile, catalog=None)

    events = agent.step(10)
    assert any(e.event_type == "consumer_browse" for e in events)

    assert agent._skus_to_view == []

    events = agent.step(11)
    assert not any(e.event_type == "query_request" for e in events)


def test_consumer_uses_catalog_browse(tenant_context, scheduling_config, consumer_profile):
    catalog = _make_mock_catalog()
    catalog.consumer.browse_skus.return_value = [{"sku_id": 101, "category": "Groceries"}]

    agent = ConsumerAgent(1, tenant_context, scheduling_config, consumer_profile, catalog=catalog)
    agent.rng.seed(42)

    events = agent.step(10)

    catalog.consumer.browse_skus.assert_called_with("Groceries", limit=3)
    query_events = [e for e in events if e.event_type == "query_request"]
    assert any(
        q.query_template == "product_details" and q.params["sku_id"] == 101
        for e in query_events
        for q in e.queries
    )


def test_consumer_uses_catalog_get_sku_for_price(
    tenant_context, scheduling_config, consumer_profile
):
    catalog = _make_mock_catalog()
    catalog.consumer.get_sku.return_value = {"sku_id": 101, "base_price": 200.0}
    catalog.consumer.get_sellers_for_sku.return_value = [{"seller_id": 99}]

    agent = ConsumerAgent(1, tenant_context, scheduling_config, consumer_profile, catalog=catalog)
    agent.rng.seed(42)

    query_id = "test-query"
    agent.pending_queries[query_id] = MagicMock(
        context={"sku_id": 101, "category": "Groceries"}, issued_tick=10
    )

    result = QueryResult(
        query_id=query_id,
        agent_id=1,
        query_template="product_details",
        tick_issued=10,
        tick_available=11,
        data={"current_price": 105.0, "avg_review": 5.0},
    )
    agent.inbox.append(result)

    agent.step(12)

    catalog.consumer.get_sku.assert_called_with(101)
    assert any(o["sku_id"] == 101 for o in agent.pending_orders.values())


def test_consumer_uses_catalog_get_sellers_for_purchase(
    tenant_context, scheduling_config, consumer_profile
):
    catalog = _make_mock_catalog()
    catalog.consumer.get_sku.return_value = {"sku_id": 101, "base_price": 100.0}
    catalog.consumer.get_sellers_for_sku.return_value = [{"seller_id": 99}]

    agent = ConsumerAgent(1, tenant_context, scheduling_config, consumer_profile, catalog=catalog)
    agent.rng.seed(42)

    query_id = "test-query"
    agent.pending_queries[query_id] = MagicMock(
        context={"sku_id": 101, "category": "Groceries"}, issued_tick=10
    )

    result = QueryResult(
        query_id=query_id,
        agent_id=1,
        query_template="product_details",
        tick_issued=10,
        tick_available=11,
        data={"current_price": 90.0, "avg_review": 5.0},
    )
    agent.inbox.append(result)

    events = agent.step(12)

    catalog.consumer.get_sellers_for_sku.assert_called_with(101)

    purchase_events = [e for e in events if e.event_type == "consumer_purchase_intent"]
    assert len(purchase_events) == 1
    assert purchase_events[0].messages[0].to_agent == 99

    order = list(agent.pending_orders.values())[0]
    assert order["seller_id"] == 99


def test_consumer_cancel_order_no_seller_fallback(
    tenant_context, scheduling_config, consumer_profile
):
    agent = ConsumerAgent(1, tenant_context, scheduling_config, consumer_profile)

    events = agent._cancel_order("unknown_order", 100)

    assert events == []
