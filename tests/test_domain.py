import pytest
from uuid import uuid4
from bizsim.domain import TenantContext, ActionEvent, ReadPattern, WritePattern
from bizsim.events import EventEmitter, QueryRequest, QueryResult
from bizsim.channels import InterAgentMessage


def test_tenant_context_immutable():
    ctx = TenantContext(tenant_id="tenant-1")
    assert ctx.tenant_id == "tenant-1"
    with pytest.raises(AttributeError):
        ctx.tenant_id = "tenant-2"  # type: ignore


def test_action_event_sql_guard_read():
    with pytest.raises(ValueError, match="Forbidden SQL keyword"):
        ActionEvent(
            event_id=uuid4(),
            event_type="test",
            agent_id=1,
            tenant_id="t1",
            tick=1,
            reads=[ReadPattern(pattern="p", params={"q": "SELECT * FROM users"})],
        )


def test_action_event_sql_guard_write():
    with pytest.raises(ValueError, match="Forbidden SQL keyword"):
        ActionEvent(
            event_id=uuid4(),
            event_type="test",
            agent_id=1,
            tenant_id="t1",
            tick=1,
            writes=[WritePattern(pattern="p", params={"q": "DROP TABLE events"})],
        )


def test_action_event_sql_guard_nested():
    with pytest.raises(ValueError, match="Forbidden SQL keyword"):
        ActionEvent(
            event_id=uuid4(),
            event_type="test",
            agent_id=1,
            tenant_id="t1",
            tick=1,
            writes=[WritePattern(pattern="p", params={"nested": {"sql": "DELETE FROM table"}})],
        )


def test_event_emitter_sets_tenant():
    ctx = TenantContext(tenant_id="restricted-tenant")
    emitter = EventEmitter(tenant=ctx, agent_id=42)
    event = emitter.emit(event_type="consumer_browse", tick=100)

    assert event.tenant_id == "restricted-tenant"
    assert event.agent_id == 42
    assert event.tick == 100
    assert event.event_type == "consumer_browse"


def test_inter_agent_message_fields():
    msg_id = uuid4()
    msg = InterAgentMessage(
        msg_id=msg_id,
        msg_type="place_order",
        from_agent=1,
        to_agent=2,
        from_tenant="t1",
        tick_sent=10,
        payload={"sku_id": 101},
    )
    assert msg.msg_id == msg_id
    assert msg.payload["sku_id"] == 101


def test_query_request_fields():
    req = QueryRequest(
        query_id="q-123",
        agent_id=1,
        query_template="product_details",
        params={"sku_id": 1},
        tick_issued=5,
    )
    assert req.query_id == "q-123"
    assert req.event_type == "query_request"


def test_query_result_fields():
    res = QueryResult(
        query_id="q-123",
        agent_id=1,
        query_template="product_details",
        tick_issued=5,
        tick_available=6,
        data={"price": 10.5},
    )
    assert res.query_id == "q-123"
    assert res.event_type == "query_result"
    assert res.tick_available == 6
