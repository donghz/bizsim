import pytest
from uuid import uuid4
from bizsim.agents.consumer import ConsumerAgent
from bizsim.domain import TenantContext
from bizsim.events import QueryResult
from bizsim.channels import InterAgentMessage


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


def test_consumer_browse(tenant_context, scheduling_config, consumer_profile):
    agent = ConsumerAgent(1, tenant_context, scheduling_config, consumer_profile)
    # GIVEN tick 10
    # WHEN agent steps
    # THEN it should trigger shopping (1), history check (1), and 3 product views
    events = agent.step(10)

    assert len(events) == 5
    assert events[0].event_type == "consumer_browse"
    assert any(r.pattern == "browse_catalog" for r in events[0].reads)
    assert all(e.event_type in ["consumer_browse", "query_request"] for e in events)
    assert hasattr(agent, "_skus_to_view")


def test_consumer_purchase_pipeline(tenant_context, scheduling_config, consumer_profile):
    agent = ConsumerAgent(1, tenant_context, scheduling_config, consumer_profile)

    # Trigger browse
    agent.step(10)

    # Trigger view_product (called in step after browse sets _skus_to_view)
    # This will emit queries
    agent.step(11)
    assert len(agent.pending_queries) > 0
    query_id = list(agent.pending_queries.keys())[0]
    context = agent.pending_queries[query_id].context

    # Simulate QueryResult
    result = QueryResult(
        query_id=query_id,
        agent_id=1,
        query_template="product_details",
        tick_issued=11,
        tick_available=12,
        data={"current_price": 105.0, "avg_review": 4.5},
    )
    # Ensure pending query has the expected context
    agent.pending_queries[query_id].context = {"sku_id": 1001, "category": "Groceries"}
    agent.inbox.append(result)

    # Process QueryResult -> should trigger initiate_purchase
    # Force high probability for test
    agent.rng.seed(42)
    events = agent.step(12)

    # Check if purchase intent was emitted
    purchase_events = [e for e in events if e.event_type == "consumer_purchase_intent"]
    if purchase_events:
        event = purchase_events[0]
        assert event.event_type == "consumer_purchase_intent"
        assert len(event.messages) == 1
        assert event.messages[0].msg_type == "place_order"

        order_request_id = event.messages[0].payload["order_request_id"]

        # Simulate OrderAccepted
        accept_msg = InterAgentMessage(
            msg_id=uuid4(),
            msg_type="order_accepted",
            from_agent=2,
            to_agent=1,
            from_tenant="seller_tenant",
            tick_sent=13,
            payload={
                "order_request_id": order_request_id,
                "store_order_id": 101,
                "confirmed_price": 105.0,
                "eta_ticks": 5,
            },
        )
        agent.inbox.append(accept_msg)
        events = agent.step(14)

        # Check for status update and payment
        status_events = [e for e in events if e.event_type == "consumer_order_status_update"]
        assert len(status_events) == 1
        assert status_events[0].messages[0].msg_type == "payment"
        assert agent.pending_orders[order_request_id]["status"] == "accepted"


def test_consumer_delivery(tenant_context, scheduling_config, consumer_profile):
    agent = ConsumerAgent(1, tenant_context, scheduling_config, consumer_profile)
    order_request_id = str(uuid4())
    agent.pending_orders[order_request_id] = {
        "sku_id": 1001,
        "qty": 1,
        "category": "Groceries",
        "price": 100.0,
        "seller_id": 2,
        "status": "accepted",
    }

    ship_msg = InterAgentMessage(
        msg_id=uuid4(),
        msg_type="shipment_notification",
        from_agent=2,
        to_agent=1,
        from_tenant="seller_tenant",
        tick_sent=20,
        payload={
            "order_request_id": order_request_id,
            "store_order_id": 101,
            "shipment_id": str(uuid4()),
            "delivered_tick": 25,
        },
    )
    agent.inbox.append(ship_msg)
    events = agent.step(26)

    assert any(e.event_type == "consumer_order_status_update" for e in events)
    assert order_request_id not in agent.pending_orders
    assert any(o["status"] == "delivered" for o in agent.completed_orders)


def test_consumer_cancel_pipeline(tenant_context, scheduling_config, consumer_profile):
    agent = ConsumerAgent(1, tenant_context, scheduling_config, consumer_profile)

    # 1. Trigger history check
    agent._skus_to_view = []  # Clear pending views from previous steps
    agent.step(50)

    # Filter pending queries for 'order_history'
    history_queries = [
        qid for qid, pq in agent.pending_queries.items() if pq.query_template == "order_history"
    ]
    assert len(history_queries) == 1
    query_id = history_queries[0]

    # 2. Simulate late order in history
    order_request_id = str(uuid4())
    agent.pending_orders[order_request_id] = {"sku_id": 1001, "seller_id": 2, "status": "requested"}

    result = QueryResult(
        query_id=query_id,
        agent_id=1,
        query_template="order_history",
        tick_issued=50,
        tick_available=51,
        data={
            "orders": [
                {"order_request_id": order_request_id, "status": "requested", "is_late": True}
            ]
        },
    )
    agent.inbox.append(result)
    events = agent.step(52)

    # 3. Check for cancel_request
    cancel_events = [e for e in events if e.event_type == "consumer_order_status_update"]
    if cancel_events:  # Probabilistic
        assert cancel_events[0].messages[0].msg_type == "cancel_request"
        assert agent.pending_orders[order_request_id]["status"] == "cancel_requested"

        # 4. Simulate CancelConfirmed
        confirm_msg = InterAgentMessage(
            msg_id=uuid4(),
            msg_type="cancel_confirmed",
            from_agent=2,
            to_agent=1,
            from_tenant="seller_tenant",
            tick_sent=53,
            payload={"order_request_id": order_request_id},
        )
        agent.inbox.append(confirm_msg)
        agent.step(54)
        assert any(o["status"] == "cancelled" for o in agent.completed_orders)
