from bizsim.agents._sandbox import install_sandbox
from bizsim.agents.base import AgentProtocol
from bizsim.domain import ActionEvent


def run_agent_tick(agent: AgentProtocol, tick: int) -> list[ActionEvent]:
    install_sandbox()
    return agent.step(tick)
