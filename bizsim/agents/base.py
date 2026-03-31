import random
from collections import deque
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from bizsim.channels import InboxItem, InterAgentMessage
from bizsim.domain import ActionEvent, TenantContext
from bizsim.events import EventEmitter, PendingQuery, QueryRequest, QueryResult

QUERY_TTL = 10


@runtime_checkable
class AgentProtocol(Protocol):
    agent_id: int
    agent_type: str
    tenant_id: str
    inbox: deque[InboxItem]
    pending_queries: dict[str, Any]

    def step(self, tick: int) -> list[ActionEvent]: ...

    def emit_query(
        self, query_template: str, params: dict[str, Any], context: dict[str, Any]
    ) -> QueryRequest: ...


class BaseAgent:
    def __init__(
        self,
        agent_id: int,
        agent_type: str,
        tenant_context: TenantContext,
        scheduling_config: dict[str, Any],
        seed: int = 42,
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.tenant_id = tenant_context.tenant_id
        self.inbox: deque[InboxItem] = deque()
        self.pending_queries: dict[str, PendingQuery] = {}
        self._emitter = EventEmitter(tenant_context, agent_id)

        self._scheduling = scheduling_config.get(agent_type, {})
        self._last_fired: dict[str, int] = {}
        self._jitter_offsets: dict[str, int] = {}
        self._current_tick: int = 0

        rng = random.Random(seed + agent_id)
        for action, config in self._scheduling.items():
            jitter = config.get("jitter", 0)
            self._jitter_offsets[action] = rng.randint(-jitter, jitter)
            self._last_fired[action] = -config.get("cycle_ticks", 0)

    def step(self, tick: int) -> list[ActionEvent]:
        self._current_tick = tick
        inbox_events = self._drain_inbox(tick)
        self._expire_pending_queries(tick)

        actions_to_fire = []
        for action, config in self._scheduling.items():
            cycle_ticks = config.get("cycle_ticks", 0)
            if self._last_fired[action] + cycle_ticks + self._jitter_offsets[action] <= tick:
                actions_to_fire.append(action)
                self._last_fired[action] = tick

        events = list(inbox_events)
        for action in actions_to_fire:
            method_name = f"handle_{action}"
            if hasattr(self, method_name):
                action_events = getattr(self, method_name)(tick)
                if action_events:
                    events.extend(action_events)
        return events

    def _drain_inbox(self, tick: int) -> list[ActionEvent]:
        query_results = []
        messages = []

        while self.inbox:
            item = self.inbox.popleft()
            if isinstance(item, QueryResult):
                query_results.append(item)
            elif isinstance(item, InterAgentMessage):
                messages.append(item)

        query_results.sort(key=lambda x: x.query_id)
        events = []
        for result in query_results:
            result_events = self._process_query_result(result, tick)
            if result_events:
                events.extend(result_events)

        messages.sort(key=lambda x: (x.tick_sent, x.from_agent))
        for msg in messages:
            msg_events = self._process_message(msg, tick)
            if msg_events:
                events.extend(msg_events)
        return events

    def _process_query_result(self, result: QueryResult, tick: int) -> list[ActionEvent] | None:
        pending = self.pending_queries.pop(result.query_id, None)
        if not pending:
            return None

        method_name = f"on_{result.query_template}_result"
        if hasattr(self, method_name):
            events = getattr(self, method_name)(result.data, pending.context, tick)
            if isinstance(events, list):
                return events
        return None

    def _process_message(self, msg: InterAgentMessage, tick: int) -> list[ActionEvent] | None:
        method_name = f"on_{msg.msg_type}"
        if hasattr(self, method_name):
            events = getattr(self, method_name)(msg.payload, msg.from_agent, tick)
            if isinstance(events, list):
                return events
        return None

    def _expire_pending_queries(self, tick: int) -> None:
        expired_ids = [
            qid for qid, pq in self.pending_queries.items() if tick - pq.issued_tick > QUERY_TTL
        ]
        for qid in expired_ids:
            self.pending_queries.pop(qid)

    def emit_query(
        self, query_template: str, params: dict[str, Any], context: dict[str, Any]
    ) -> QueryRequest:
        query_id = str(uuid4())
        pq = PendingQuery(
            query_id=query_id,
            query_template=query_template,
            context=context,
            issued_tick=self._current_tick,
        )
        self.pending_queries[query_id] = pq
        return QueryRequest(
            query_id=query_id,
            agent_id=self.agent_id,
            query_template=query_template,
            params=params,
            tick_issued=self._current_tick,
        )
