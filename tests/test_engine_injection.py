from typing import Any

from bizsim.engine import TickEngine


class MockAgent:
    def __init__(self, agent_id: int):
        self.agent_id = agent_id
        self.inbox: list[Any] = []
        self.catalog: Any = None
        self.peer_agents: Any = None

    def step(self, tick: int) -> list[Any]:
        return []


class UnsupportedAgent:
    def __init__(self, agent_id: int):
        self.agent_id = agent_id
        self.inbox: list[Any] = []

    def step(self, tick: int) -> list[Any]:
        return []


class MockCatalog:
    def __init__(self) -> None:
        self.consumer = _ConsumerSub()
        self.industrial = _IndustrialSub()


class _ConsumerSub:
    def browse_skus(self, category: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return []

    def get_sku(self, sku_id: int) -> dict[str, Any] | None:
        return None

    def get_sellers_for_sku(self, sku_id: int) -> list[dict[str, Any]]:
        return []

    def get_skus_for_seller(self, seller_id: int) -> list[dict[str, Any]]:
        return []


class _IndustrialSub:
    def get_suppliers_for_sku(self, sku_id: int) -> list[dict[str, Any]]:
        return []

    def get_bom(self, sku_id: int) -> list[dict[str, Any]]:
        return []

    def get_parts_for_supplier(self, supplier_id: int) -> list[dict[str, Any]]:
        return []


def test_engine_injection():
    catalog = MockCatalog()
    peer_config = {"seller": 5, "consumer": 10}

    agent1 = MockAgent(1)
    agent2 = MockAgent(2)
    unsupported = UnsupportedAgent(3)

    agents = [agent1, agent2, unsupported]

    TickEngine(agents=agents, catalog=catalog, peer_agents_config=peer_config)

    assert agent1.catalog is catalog
    assert agent1.peer_agents == peer_config
    assert agent2.catalog is catalog
    assert agent2.peer_agents == peer_config

    assert not hasattr(unsupported, "catalog")
    assert not hasattr(unsupported, "peer_agents")


def test_engine_no_injection():
    agent = MockAgent(1)
    TickEngine(agents=[agent])

    assert agent.catalog is None
    assert agent.peer_agents is None


def test_engine_partial_injection_catalog_only():
    catalog = MockCatalog()
    agent = MockAgent(1)

    TickEngine(agents=[agent], catalog=catalog)
    assert agent.catalog is catalog
    assert agent.peer_agents is None


def test_engine_partial_injection_peers_only():
    agent = MockAgent(1)
    peer_config = {"seller": 1}
    TickEngine(agents=[agent], peer_agents_config=peer_config)
    assert agent.catalog is None
    assert agent.peer_agents == peer_config
