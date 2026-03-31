from dataclasses import dataclass
from typing import Any
from uuid import UUID

from bizsim.events import QueryResult


@dataclass
class InterAgentMessage:
    msg_id: UUID
    msg_type: str
    from_agent: int
    to_agent: int
    from_tenant: str
    tick_sent: int
    payload: dict[str, Any]


InboxItem = InterAgentMessage | QueryResult
