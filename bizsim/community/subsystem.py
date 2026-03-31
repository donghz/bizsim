import random
import uuid
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from bizsim.domain import ActionEvent, WritePattern


@dataclass(frozen=True)
class SharePurchaseData:
    consumer_id: int
    category: str
    satisfaction: float


@runtime_checkable
class ConsumerProtocol(Protocol):
    consumer_id: int
    trend_multiplier: dict[str, float]


@dataclass
class CommunityConfig:
    k_max_hops: int = 3
    boost_increment: float = 0.3
    trend_max: float = 3.0
    decay_rate: float = 0.98
    edge_strengthen_delta: float = 0.01
    max_edge_weight: float = 0.5
    max_activations_per_tick: int = 10000
    initial_edge_weight_range: tuple[float, float] = (0.01, 0.5)
    avg_degree: int = 6


class CommunitySubsystem:
    def __init__(self, consumer_ids: list[int], config: CommunityConfig, seed: int = 42):
        self._config = config
        self._rng = random.Random(seed)
        self._activation_queue: list[SharePurchaseData] = []
        self._graph: dict[int, dict[int, dict[str, Any]]] = {cid: {} for cid in consumer_ids}
        self._initialize_graph(consumer_ids)

    def _initialize_graph(self, consumer_ids: list[int]) -> None:
        if not consumer_ids:
            return

        num_consumers = len(consumer_ids)
        k = min(self._config.avg_degree, num_consumers - 1)
        for i, source_id in enumerate(consumer_ids):
            for j in range(1, k // 2 + 1):
                target_idx = (i + j) % num_consumers
                self._add_edge(source_id, consumer_ids[target_idx])
                target_idx = (i - j) % num_consumers
                self._add_edge(source_id, consumer_ids[target_idx])

    def _add_edge(self, source_id: int, target_id: int) -> None:
        if source_id == target_id:
            return
        if target_id not in self._graph[source_id]:
            weight = self._rng.uniform(*self._config.initial_edge_weight_range)
            self._graph[source_id][target_id] = {"weight": weight, "topic_weights": {}}

    def enqueue_activation(self, data: SharePurchaseData) -> None:
        self._activation_queue.append(data)

    def run_propagation(
        self, tick: int, consumers: dict[int, ConsumerProtocol]
    ) -> list[ActionEvent]:
        activations = self._activation_queue[: self._config.max_activations_per_tick]
        self._activation_queue = []

        topic_activations: dict[str, set[int]] = {}
        for act in activations:
            if act.category not in topic_activations:
                topic_activations[act.category] = set()
            topic_activations[act.category].add(act.consumer_id)

        all_newly_activated: dict[str, set[int]] = {}
        successful_edges: list[tuple[int, int]] = []

        for topic, seeds in topic_activations.items():
            activated_this_topic = set(seeds)
            current_hop_seeds = set(seeds)

            for _ in range(self._config.k_max_hops):
                next_hop_seeds = set()
                for source_id in current_hop_seeds:
                    if source_id not in self._graph:
                        continue

                    for target_id, edge_data in self._graph[source_id].items():
                        if target_id in activated_this_topic:
                            continue

                        topic_weight = edge_data["topic_weights"].get(topic, 1.0)
                        p_activate = edge_data["weight"] * topic_weight

                        if self._rng.random() < p_activate:
                            next_hop_seeds.add(target_id)
                            activated_this_topic.add(target_id)
                            successful_edges.append((source_id, target_id))

                if not next_hop_seeds:
                    break
                current_hop_seeds = next_hop_seeds

            all_newly_activated[topic] = activated_this_topic - seeds

        self._apply_decay(consumers)

        for topic, newly_activated in all_newly_activated.items():
            for cid in newly_activated:
                if cid in consumers:
                    c = consumers[cid]
                    current = c.trend_multiplier.get(topic, 1.0)
                    c.trend_multiplier[topic] = min(
                        current + self._config.boost_increment, self._config.trend_max
                    )

        updated_edges_payload = []
        for source, target in successful_edges:
            edge = self._graph[source][target]
            new_weight = min(
                edge["weight"] + self._config.edge_strengthen_delta, self._config.max_edge_weight
            )
            edge["weight"] = new_weight
            updated_edges_payload.append(
                {"source": source, "target": target, "new_weight": new_weight}
            )

        if not updated_edges_payload:
            return []

        return [
            ActionEvent(
                event_id=uuid.uuid4(),
                event_type="community_propagation_batch",
                agent_id=0,
                tenant_id="social_graph",
                tick=tick,
                writes=[
                    WritePattern(
                        pattern="batch_update_influence_edges",
                        params={"edges": updated_edges_payload},
                    )
                ],
            )
        ]

    def _apply_decay(self, consumers: dict[int, ConsumerProtocol]) -> None:
        for c in consumers.values():
            for topic in list(c.trend_multiplier.keys()):
                val = c.trend_multiplier[topic]
                if val > 1.0:
                    new_val = max(val * self._config.decay_rate, 1.0)
                    if new_val == 1.0:
                        del c.trend_multiplier[topic]
                    else:
                        c.trend_multiplier[topic] = new_val
