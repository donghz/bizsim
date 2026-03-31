from collections import deque
from typing import Any
from uuid import uuid4

from bizsim.channels import InterAgentMessage
from bizsim.domain import ActionEvent, ReadPattern
from bizsim.engine import TickEngine
from bizsim.events import PendingQuery, QueryRequest, QueryResult


class MockAgent:
    def __init__(self, agent_id: int, agent_type: str, tenant_id: str):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.tenant_id = tenant_id
        self.inbox = deque()
        self.pending_queries = {}
        self.actions_to_emit = []
        self.queries_to_emit = []
        self.processed_items = []

    def step(self, tick: int) -> list[ActionEvent]:
        while self.inbox:
            item = self.inbox.popleft()
            self.processed_items.append(item)

        for _q in self.queries_to_emit:
            pass

        res = self.actions_to_emit
        self.actions_to_emit = []
        return res

    def emit_query(
        self,
        query_template: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> QueryRequest:
        query_id = str(uuid4())
        req = QueryRequest(
            query_id=query_id,
            agent_id=self.agent_id,
            query_template=query_template,
            params=params,
            tick_issued=0,
        )
        self.pending_queries[query_id] = PendingQuery(
            query_id=query_id, query_template=query_template, context=context, issued_tick=0
        )
        return req


def test_engine_init():
    agent = MockAgent(1, "consumer", "t1")
    engine = TickEngine([agent])
    assert engine.current_tick == 0
    assert len(engine.agents) == 1


def test_engine_phase_1_inbox_ordering():
    agent = MockAgent(1, "consumer", "t1")
    engine = TickEngine([agent])

    msg1 = InterAgentMessage(uuid4(), "type1", 2, 1, "t2", 1, {})
    msg2 = InterAgentMessage(uuid4(), "type2", 3, 1, "t3", 1, {})
    res1 = QueryResult("q2", 1, "tmpl", 1, 2, {})
    res2 = QueryResult("q1", 1, "tmpl", 1, 2, {})

    agent.inbox.append(msg1)
    agent.inbox.append(res1)
    agent.inbox.append(msg2)
    agent.inbox.append(res2)

    engine._prepare_agent_inboxes()

    ordered = list(agent.inbox)
    assert ordered[0].query_id == "q1"
    assert ordered[1].query_id == "q2"
    assert ordered[2].from_agent == 2
    assert ordered[3].from_agent == 3


def test_engine_ch2_routing():
    a1 = MockAgent(1, "consumer", "t1")
    a2 = MockAgent(2, "seller", "t2")
    engine = TickEngine([a1, a2])

    msg = InterAgentMessage(uuid4(), "Order", 1, 2, "t1", 1, {"item": "apple"})
    event = ActionEvent(uuid4(), "purchase", 1, "t1", 1, messages=[msg])

    a1.actions_to_emit = [event]
    engine.step()

    assert len(a2.inbox) == 1
    assert isinstance(a2.inbox[0], InterAgentMessage)
    assert a2.inbox[0].payload["item"] == "apple"


def test_engine_ch3_query_pipeline():
    agent = MockAgent(1, "consumer", "t1")

    def mock_query_handler(req: QueryRequest) -> QueryResult:
        return QueryResult(
            req.query_id, req.agent_id, req.query_template, req.tick_issued, 2, {"data": "ok"}
        )

    engine = TickEngine([agent], query_handler=mock_query_handler)

    req = QueryRequest("q1", 1, "test_tmpl", {}, 1)
    engine.register_query(req)

    engine.step()

    assert len(agent.inbox) == 1
    assert isinstance(agent.inbox[0], QueryResult)
    assert agent.inbox[0].data["data"] == "ok"


def test_determinism():
    def run_sim(seed):
        a1 = MockAgent(1, "consumer", "t1")
        a2 = MockAgent(2, "seller", "t2")
        engine = TickEngine([a1, a2], seed=seed)

        for i in range(3):
            msg = InterAgentMessage(uuid4(), "msg", 1, 2, "t1", engine.current_tick + 1, {"val": i})
            a1.actions_to_emit = [
                ActionEvent(uuid4(), "act", 1, "t1", engine.current_tick + 1, messages=[msg])
            ]
            engine.step()
        return [(type(e), getattr(e, "event_id", None)) for e in engine.action_log]

    res1 = run_sim(42)
    res2 = run_sim(42)
    assert len(res1) == len(res2)
    assert [r[0] for r in res1] == [r[0] for r in res2]


def test_community_hook():
    hook_called = []

    def my_hook(event):
        hook_called.append(event)

    a1 = MockAgent(1, "consumer", "t1")
    engine = TickEngine([a1], community_hook=my_hook)

    event = ActionEvent(uuid4(), "social_post", 1, "t1", 1)
    a1.actions_to_emit = [event]

    engine.step()
    assert len(hook_called) == 1
    assert hook_called[0].event_type == "social_post"


def test_dual_mode_reads_orchestration():
    agent = MockAgent(1, "consumer", "t1")

    def mock_query_handler(req):
        return QueryResult(
            req.query_id, req.agent_id, req.query_template, req.tick_issued, 2, {"mode": 2}
        )

    engine = TickEngine([agent], query_handler=mock_query_handler)

    read = ReadPattern("browse_catalog", {"cat": 1})
    event = ActionEvent(uuid4(), "purchase", 1, "t1", 1, reads=[read])
    agent.actions_to_emit = [event]

    req = QueryRequest("q_mode2", 1, "history", {}, 1)
    engine.register_query(req)

    engine.step()

    assert len(engine.action_log) == 1
    assert engine.action_log[0].reads[0].pattern == "browse_catalog"
    assert any(isinstance(item, QueryResult) and item.data.get("mode") == 2 for item in agent.inbox)
