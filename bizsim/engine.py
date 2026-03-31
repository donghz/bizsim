import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bizsim.market import MarketFactory

from bizsim.channels import InterAgentMessage
from bizsim.domain import ActionEvent
from bizsim.events import QueryRequest, QueryResult


class TickEngine:
    def __init__(
        self,
        agents: list[Any],
        seed: int = 42,
        query_handler: Any = None,
        community_hook: Any = None,
        catalog: "MarketFactory | None" = None,
        peer_agents_config: dict[str, int] | None = None,
    ) -> None:
        self.agents: dict[int, Any] = {a.agent_id: a for a in agents}

        self.current_tick = 0
        self.random = random.Random(seed)
        self.query_handler = query_handler
        self.community_hook = community_hook
        self.catalog = catalog
        self.peer_agents_config = peer_agents_config

        self._inject_dependencies()

        self.action_log: list[ActionEvent] = []
        self._current_tick_query_requests: list[QueryRequest] = []

    def _inject_dependencies(self) -> None:
        for agent in self.agents.values():
            if hasattr(agent, "catalog") and self.catalog is not None:
                agent.catalog = self.catalog
            if hasattr(agent, "peer_agents") and self.peer_agents_config is not None:
                agent.peer_agents = self.peer_agents_config

    def register_query(self, request: QueryRequest) -> None:
        self._current_tick_query_requests.append(request)

    def step(self) -> None:
        self.current_tick += 1

        self._prepare_agent_inboxes()

        self._process_external_events()

        agent_ids = sorted(self.agents.keys())
        all_actions: list[ActionEvent] = []
        for aid in agent_ids:
            actions = self.agents[aid].step(self.current_tick)
            all_actions.extend(actions)

        self._advance_transport_state()

        self._compute_community_influence(all_actions)

        self._run_government_aggregation()

        self._emit_and_route(all_actions)
        self._current_tick_query_requests = []

    def _prepare_agent_inboxes(self) -> None:
        for agent in self.agents.values():
            query_results = [item for item in agent.inbox if isinstance(item, QueryResult)]
            inter_messages = [item for item in agent.inbox if isinstance(item, InterAgentMessage)]

            query_results.sort(key=lambda x: x.query_id)
            inter_messages.sort(key=lambda x: (x.tick_sent, x.from_agent))

            agent.inbox.clear()
            agent.inbox.extend(query_results)
            agent.inbox.extend(inter_messages)

    def _process_external_events(self) -> None:
        pass

    def _advance_transport_state(self) -> None:
        pass

    def _compute_community_influence(self, actions: list[ActionEvent]) -> None:
        if self.community_hook:
            for action in actions:
                self.community_hook(action)

    def _run_government_aggregation(self) -> None:
        pass

    def _emit_and_route(self, actions: list[ActionEvent]) -> None:
        self.action_log.extend(actions)

        for action in actions:
            for req in action.queries:
                self.register_query(req)

        all_messages: list[InterAgentMessage] = []
        for action in actions:
            for msg in action.messages:
                if isinstance(msg, InterAgentMessage):
                    all_messages.append(msg)

        all_messages.sort(key=lambda m: (m.tick_sent, m.from_agent))

        for msg in all_messages:
            if msg.to_agent in self.agents:
                self.agents[msg.to_agent].inbox.append(msg)

        if self.query_handler:
            for req in self._current_tick_query_requests:
                result = self.query_handler(req)
                if result.agent_id in self.agents:
                    self.agents[result.agent_id].inbox.append(result)
