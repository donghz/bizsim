import pytest
from typing import Any
from bizsim.engine import TickEngine
from bizsim.product_catalog import ProductCatalog


class MockAgent:
    def __init__(self, agent_id: int):
        self.agent_id = agent_id
        self.inbox = []
        self.catalog = None
        self.peer_agents = None

    def step(self, tick: int):
        return []


class UnsupportedAgent:
    def __init__(self, agent_id: int):
        self.agent_id = agent_id
        self.inbox = []

    def step(self, tick: int):
        return []


class MockCatalog:
    def browse_skus(self, category=None, limit=100):
        return []

    def get_sku(self, sku_id):
        return None

    def get_sellers_for_sku(self, sku_id):
        return []

    def get_suppliers_for_sku(self, sku_id):
        return []

    def get_bom(self, sku_id):
        return []

    def get_skus_for_seller(self, seller_id):
        return []

    def get_parts_for_supplier(self, supplier_id):
        return []


def test_engine_injection():
    catalog = MockCatalog()
    peer_config = {"seller": 5, "consumer": 10}

    agent1 = MockAgent(1)
    agent2 = MockAgent(2)
    unsupported = UnsupportedAgent(3)

    agents = [agent1, agent2, unsupported]

    engine = TickEngine(agents=agents, catalog=catalog, peer_agents_config=peer_config)

    assert agent1.catalog is catalog
    assert agent1.peer_agents == peer_config
    assert agent2.catalog is catalog
    assert agent2.peer_agents == peer_config

    assert not hasattr(unsupported, "catalog")
    assert not hasattr(unsupported, "peer_agents")


def test_engine_no_injection():
    agent = MockAgent(1)
    engine = TickEngine(agents=[agent])

    assert agent.catalog is None
    assert agent.peer_agents is None


def test_engine_partial_injection():
    catalog = MockCatalog()
    agent = MockAgent(1)

    engine = TickEngine(agents=[agent], catalog=catalog)
    assert agent.catalog is catalog
    assert agent.peer_agents is None

    agent2 = MockAgent(2)
    peer_config = {"seller": 1}
    engine2 = TickEngine(agents=[agent2], peer_agents_config=peer_config)
    assert agent2.catalog is None
    assert agent2.peer_agents == peer_config

    # Verify no error for unsupported agent
    assert not hasattr(unsupported, "catalog")
    assert not hasattr(unsupported, "peer_agents")


def test_engine_no_injection():
    # Verify backward compatibility (no arguments provided)
    agent = MockAgent(1)
    engine = TickEngine(agents=[agent])

    assert agent.catalog is None
    assert agent.peer_agents is None


def test_engine_partial_injection():
    catalog = MockCatalog()
    agent = MockAgent(1)

    # Only catalog
    engine = TickEngine(agents=[agent], catalog=catalog)
    assert agent.catalog is catalog
    assert agent.peer_agents is None

    # Only peer_agents_config
    agent2 = MockAgent(2)
    peer_config = {"seller": 1}
    engine2 = TickEngine(agents=[agent2], peer_agents_config=peer_config)
    assert agent2.catalog is None
    assert agent2.peer_agents == peer_config
