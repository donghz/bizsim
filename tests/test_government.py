from uuid import uuid4

import pytest

from bizsim.agents.government import GovernmentAgent
from bizsim.channels import InterAgentMessage
from bizsim.domain import TenantContext
from bizsim.events import QueryResult


@pytest.fixture
def tenant_context():
    return TenantContext(tenant_id="analytics_1")


@pytest.fixture
def government_agent(tenant_context):
    scheduling_config = {"government": {"compute_statistics": {"cycle_ticks": 100, "jitter": 0}}}
    return GovernmentAgent(
        agent_id=1,
        agent_type="government",
        tenant_context=tenant_context,
        scheduling_config=scheduling_config,
    )


def test_government_agent_receive_order_report(government_agent):
    government_agent._last_fired["compute_statistics"] = 1

    payload = {
        "store_order_id": 101,
        "seller_id": 10,
        "sku_id": 5,
        "qty": 2,
        "amount": 50.0,
        "tick": 1,
    }
    msg = InterAgentMessage(
        msg_id=uuid4(),
        msg_type="order_report",
        from_agent=10,
        to_agent=1,
        from_tenant="store_10",
        tick_sent=1,
        payload=payload,
    )

    government_agent.inbox.append(msg)
    events = government_agent.step(1)

    assert len(events) == 1
    event = events[0]
    assert event.event_type == "gov_record_insert"
    assert len(event.writes) == 1
    assert event.writes[0].pattern == "insert_gov_record"
    assert event.writes[0].params["entity_type"] == "seller"
    assert event.writes[0].params["entity_id"] == 10
    assert event.writes[0].params["report_type"] == "order"


def test_government_agent_receive_disruption_report(government_agent):
    government_agent._last_fired["compute_statistics"] = 1

    payload = {"supplier_id": 20, "part_id": 3, "severity": "high", "tick": 1}
    msg = InterAgentMessage(
        msg_id=uuid4(),
        msg_type="disruption_report",
        from_agent=20,
        to_agent=1,
        from_tenant="supplier_20",
        tick_sent=1,
        payload=payload,
    )

    government_agent.inbox.append(msg)
    events = government_agent.step(1)

    assert len(events) == 1
    event = events[0]
    assert event.event_type == "gov_record_insert"
    assert event.writes[0].params["entity_type"] == "supplier"
    assert event.writes[0].params["entity_id"] == 20
    assert event.writes[0].params["report_type"] == "disruption"


def test_government_agent_compute_statistics_trigger(government_agent):
    events = government_agent.step(0)

    assert any(e.event_type == "statistics_collection_started" for e in events)

    assert len(government_agent.pending_queries) == 1
    query_id = list(government_agent.pending_queries.keys())[0]
    pq = government_agent.pending_queries[query_id]
    assert pq.query_template == "gov_economic_indicators"
    assert pq.context["tick_triggered"] == 0


def test_government_agent_on_query_result(government_agent):
    government_agent.handle_compute_statistics(10)
    query_id = list(government_agent.pending_queries.keys())[0]

    data = {
        "gdp": 1000.0,
        "transaction_volume": 500,
        "avg_price_index": 1.05,
        "trade_balance": 100.0,
        "active_entities": 50,
    }

    result = QueryResult(
        query_id=query_id,
        agent_id=1,
        query_template="gov_economic_indicators",
        tick_issued=10,
        tick_available=11,
        data=data,
    )

    government_agent.inbox.append(result)
    government_agent._last_fired["compute_statistics"] = 100
    events = government_agent.step(11)

    assert any(e.event_type == "statistics_published" for e in events)
    publish_event = next(e for e in events if e.event_type == "statistics_published")
    assert len(publish_event.writes) == 1
    write = publish_event.writes[0]
    assert write.pattern == "insert_statistics"
    assert write.params["gdp"] == 1000.0
    assert write.params["period"] == 10
    assert write.params["active_sellers"] == 50
