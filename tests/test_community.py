import pytest
import uuid
from bizsim.community.subsystem import CommunitySubsystem, CommunityConfig, SharePurchaseData


class MockConsumer:
    def __init__(self, consumer_id):
        self.consumer_id = consumer_id
        self.trend_multiplier = {}


def test_community_initialization():
    consumer_ids = [1, 2, 3, 4, 5]
    config = CommunityConfig(avg_degree=2)
    subsystem = CommunitySubsystem(consumer_ids, config)

    assert len(subsystem._graph) == 5
    for cid in consumer_ids:
        assert len(subsystem._graph[cid]) == 2


def test_enqueue_activation():
    subsystem = CommunitySubsystem([1], CommunityConfig())
    data = SharePurchaseData(consumer_id=1, category="electronics", satisfaction=1.0)
    subsystem.enqueue_activation(data)
    assert len(subsystem._activation_queue) == 1
    assert subsystem._activation_queue[0].consumer_id == 1


def test_propagation_and_boost():
    consumer_ids = [1, 2]
    config = CommunityConfig(
        k_max_hops=1, boost_increment=0.5, initial_edge_weight_range=(1.0, 1.0)
    )
    subsystem = CommunitySubsystem(consumer_ids, config, seed=42)
    subsystem._graph[1] = {2: {"weight": 1.0, "topic_weights": {}}}

    consumers = {1: MockConsumer(1), 2: MockConsumer(2)}

    subsystem.enqueue_activation(SharePurchaseData(1, "food", 1.0))
    events = subsystem.run_propagation(tick=1, consumers=consumers)

    assert consumers[2].trend_multiplier["food"] == 1.5
    assert "food" not in consumers[1].trend_multiplier

    assert len(events) == 1
    assert events[0].event_type == "community_propagation_batch"
    assert events[0].writes[0].params["edges"][0]["source"] == 1
    assert events[0].writes[0].params["edges"][0]["target"] == 2


def test_trend_decay():
    consumer_ids = [1]
    config = CommunityConfig(decay_rate=0.9)
    subsystem = CommunitySubsystem(consumer_ids, config)

    consumer = MockConsumer(1)
    consumer.trend_multiplier["electronics"] = 2.0
    consumers = {1: consumer}

    subsystem.run_propagation(tick=1, consumers=consumers)
    assert consumer.trend_multiplier["electronics"] == 1.8

    subsystem.run_propagation(tick=2, consumers=consumers)
    assert consumer.trend_multiplier["electronics"] == pytest.approx(1.62)


def test_max_hops():
    consumer_ids = [1, 2, 3]
    config = CommunityConfig(
        k_max_hops=2, boost_increment=0.3, initial_edge_weight_range=(1.0, 1.0)
    )
    subsystem = CommunitySubsystem(consumer_ids, config, seed=42)
    subsystem._graph[1] = {2: {"weight": 1.0, "topic_weights": {}}}
    subsystem._graph[2] = {3: {"weight": 1.0, "topic_weights": {}}}
    subsystem._graph[3] = {}

    consumers = {i: MockConsumer(i) for i in consumer_ids}

    subsystem.enqueue_activation(SharePurchaseData(1, "tech", 1.0))
    subsystem.run_propagation(tick=1, consumers=consumers)

    assert consumers[2].trend_multiplier["tech"] == 1.3
    assert consumers[3].trend_multiplier["tech"] == 1.3


def test_determinism():
    consumer_ids = list(range(10))
    config = CommunityConfig()

    sub1 = CommunitySubsystem(consumer_ids, config, seed=123)
    sub2 = CommunitySubsystem(consumer_ids, config, seed=123)

    assert sub1._graph == sub2._graph

    consumers1 = {i: MockConsumer(i) for i in consumer_ids}
    consumers2 = {i: MockConsumer(i) for i in consumer_ids}

    sub1.enqueue_activation(SharePurchaseData(1, "test", 1.0))
    sub2.enqueue_activation(SharePurchaseData(1, "test", 1.0))

    sub1.run_propagation(tick=1, consumers=consumers1)
    sub2.run_propagation(tick=1, consumers=consumers2)

    for i in consumer_ids:
        assert consumers1[i].trend_multiplier == consumers2[i].trend_multiplier
