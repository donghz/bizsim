from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class TenantContext:
    """Immutable tenant context."""

    tenant_id: str


@dataclass
class ReadPattern:
    """Mode 1 correlated read operation."""

    pattern: str
    params: dict[str, Any]


@dataclass
class WritePattern:
    """Mode 1 write operation."""

    pattern: str
    params: dict[str, Any]


@dataclass
class ActionEvent:
    """Channel 1: Action event translated to SQL by Go translator."""

    event_id: UUID
    event_type: str
    agent_id: int
    tenant_id: str
    tick: int
    reads: list[ReadPattern] = field(default_factory=list)
    writes: list[WritePattern] = field(default_factory=list)
    messages: list[Any] = field(
        default_factory=list
    )  # Any to avoid circular import with InterAgentMessage
    queries: list[Any] = field(default_factory=list)

    def __post_init__(self) -> None:
        """SQL keyword guard for event payloads."""
        forbidden = {
            "SELECT",
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "TRUNCATE",
            "ALTER",
            "CREATE",
        }

        def _check(data: Any) -> None:
            if isinstance(data, str):
                if any(kw in data.upper() for kw in forbidden):
                    raise ValueError(f"Forbidden SQL keyword in action event payload: {data}")
            elif isinstance(data, dict):
                for v in data.values():
                    _check(v)
            elif isinstance(data, list):
                for item in data:
                    _check(item)

        for read in self.reads:
            _check(read.params)
        for write in self.writes:
            _check(write.params)
