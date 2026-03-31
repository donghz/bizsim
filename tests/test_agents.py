from uuid import uuid4

import pytest

from bizsim.agents._sandbox import SandboxImportError
from bizsim.agents.base import AgentProtocol, BaseAgent
from bizsim.agents.runner import run_agent_tick
from bizsim.channels import InterAgentMessage
from bizsim.domain import TenantContext
from bizsim.events import QueryResult


@pytest.fixture
def scheduling_config():
    return {"consumer": {"browse_catalog": {"cycle_ticks": 10, "jitter": 3}}}


@pytest.fixture
def tenant_context():
    return TenantContext(tenant_id="tenant_1")


def test_base_agent_init(tenant_context, scheduling_config):
    agent = BaseAgent(
        agent_id=1,
        agent_type="consumer",
        tenant_context=tenant_context,
        scheduling_config=scheduling_config,
    )
    assert agent.agent_id == 1
    assert agent.agent_type == "consumer"
    assert agent.tenant_id == "tenant_1"
    assert isinstance(agent, AgentProtocol)


def test_scheduling_jitter_determinism(tenant_context, scheduling_config):
    agent1 = BaseAgent(1, "consumer", tenant_context, scheduling_config, seed=42)
    agent2 = BaseAgent(1, "consumer", tenant_context, scheduling_config, seed=42)
    assert agent1._jitter_offsets == agent2._jitter_offsets

    BaseAgent(2, "consumer", tenant_context, scheduling_config, seed=42)
    # Different agent_id should likely have different jitter if jitter > 0
    # but we just care it's deterministic per (seed, agent_id)


def test_inbox_ordering(tenant_context, scheduling_config):
    agent = BaseAgent(1, "consumer", tenant_context, scheduling_config)

    msg1 = InterAgentMessage(uuid4(), "type_a", 2, 1, "t1", 5, {})
    msg2 = InterAgentMessage(uuid4(), "type_b", 1, 1, "t1", 5, {})
    res1 = QueryResult("query_b", 1, "tpl", 4, 5, {})
    res2 = QueryResult("query_a", 1, "tpl", 4, 5, {})

    # Add in mixed order
    agent.inbox.append(msg1)
    agent.inbox.append(res1)
    agent.inbox.append(msg2)
    agent.inbox.append(res2)

    processed_order = []

    # Mock handlers to track order
    agent.on_tpl_result = lambda data, ctx, tick: processed_order.append(f"res_{data['id']}")
    agent.on_type_a = lambda payload, from_agent, tick: processed_order.append(
        f"msg_a_{from_agent}"
    )
    agent.on_type_b = lambda payload, from_agent, tick: processed_order.append(
        f"msg_b_{from_agent}"
    )

    # Inject IDs for tracking
    res1.data = {"id": "b"}
    res2.data = {"id": "a"}

    # Mock pending query for results to be processed
    agent.pending_queries["query_a"] = type("PQ", (), {"context": {}, "issued_tick": 4})()
    agent.pending_queries["query_b"] = type("PQ", (), {"context": {}, "issued_tick": 4})()

    agent.step(6)

    # Order: QueryResults (sorted by query_id: query_a, query_b)
    # Then InterAgentMessages (sorted by tick_sent, from_agent: (5, 1), (5, 2))
    assert processed_order == ["res_a", "res_b", "msg_b_1", "msg_a_2"]


def test_scheduling_activation(tenant_context, scheduling_config):
    agent = BaseAgent(1, "consumer", tenant_context, scheduling_config)

    fired = []
    agent.handle_browse_catalog = lambda tick: (fired.append(tick), [])[1]

    # cycle_ticks = 10. last_fired initialized to -10.
    # jitter is in [-3, 3]. Suppose jitter is 0 for this example if we were lucky,
    # but we can't assume. Let's just step until it fires.

    found = False
    for t in range(20):
        agent.step(t)
        if fired:
            found = True
            break
    assert found


def test_pipeline_correlation_and_ttl(tenant_context, scheduling_config):
    agent = BaseAgent(1, "consumer", tenant_context, scheduling_config)

    # Emit query at tick 1
    agent.step(1)
    req = agent.emit_query("test_tpl", {"p": 1}, {"ctx": "val"})
    assert req.query_id in agent.pending_queries

    # Result arrives at tick 12 (TTL=10, so it should be expired at tick 12)
    # Current tick 1: issued_tick = 1.
    # Tick 11: 11 - 1 = 10. Not expired yet (spec says > 10).
    # Tick 12: 12 - 1 = 11. Expired.

    agent.step(11)
    assert req.query_id in agent.pending_queries

    agent.step(12)
    assert req.query_id not in agent.pending_queries


def test_sandbox_blocks_imports():

    class EvilAgent(BaseAgent):
        def step(self, tick):
            import sqlite3  # noqa: F401

            return []

    agent = EvilAgent(1, "consumer", TenantContext("t1"), {})
    with pytest.raises(SandboxImportError):
        run_agent_tick(agent, 1)


def test_emit_query_records_correct_tick(tenant_context, scheduling_config):
    agent = BaseAgent(1, "consumer", tenant_context, scheduling_config)
    agent.step(5)
    req = agent.emit_query("test", {}, {})
    assert req.tick_issued == 5
    assert agent.pending_queries[req.query_id].issued_tick == 5
