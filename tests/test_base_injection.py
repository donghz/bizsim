from bizsim.agents.base import BaseAgent
from bizsim.domain import TenantContext
import pytest


def test_base_agent_injection():
    tenant_context = TenantContext(tenant_id="test_tenant")
    # scheduling_config uses agent_type as key, then action names as subkeys
    scheduling_config = {"test": {"some_action": {"cycle_ticks": 10}}}

    # Test without injection (backward compatibility)
    agent_basic = BaseAgent(
        agent_id=1,
        agent_type="test",
        tenant_context=tenant_context,
        scheduling_config=scheduling_config,
    )
    assert agent_basic.catalog is None
    assert agent_basic.peer_agents == {}

    # Test with injection
    mock_catalog = object()
    peer_agents = {"seller": 2, "supplier": 3}
    agent_injected = BaseAgent(
        agent_id=1,
        agent_type="test",
        tenant_context=tenant_context,
        scheduling_config=scheduling_config,
        catalog=mock_catalog,
        peer_agents=peer_agents,
    )
    assert agent_injected.catalog is mock_catalog
    assert agent_injected.peer_agents == peer_agents


if __name__ == "__main__":
    pytest.main([__file__])
