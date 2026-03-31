from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from bizsim.domain import ActionEvent, ReadPattern, TenantContext, WritePattern

if TYPE_CHECKING:
    from bizsim.channels import InterAgentMessage


@dataclass
class PendingQuery:
    query_id: str
    query_template: str
    context: dict[str, Any]
    issued_tick: int


@dataclass
class QueryRequest:
    query_id: str
    agent_id: int
    query_template: str
    params: dict[str, Any]
    tick_issued: int
    event_type: str = "query_request"


@dataclass
class QueryResult:
    query_id: str
    agent_id: int
    query_template: str
    tick_issued: int
    tick_available: int
    data: dict[str, Any]
    event_type: str = "query_result"


class EventEmitter:
    def __init__(self, tenant: TenantContext, agent_id: int):
        self._tenant = tenant
        self._agent_id = agent_id

    def emit(
        self,
        event_type: str,
        tick: int,
        reads: list[ReadPattern] | None = None,
        writes: list[WritePattern] | None = None,
        messages: list["InterAgentMessage"] | None = None,
        queries: list[QueryRequest] | None = None,
    ) -> ActionEvent:
        return ActionEvent(
            event_id=uuid4(),
            event_type=event_type,
            agent_id=self._agent_id,
            tenant_id=self._tenant.tenant_id,
            tick=tick,
            reads=reads or [],
            writes=writes or [],
            messages=messages or [],
            queries=queries or [],
        )
