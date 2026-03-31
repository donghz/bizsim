from typing import Any

from bizsim.agents.base import BaseAgent
from bizsim.domain import ActionEvent, TenantContext, WritePattern


class GovernmentAgent(BaseAgent):
    def __init__(
        self,
        agent_id: int,
        agent_type: str,
        tenant_context: TenantContext,
        scheduling_config: dict[str, Any],
        seed: int = 42,
    ):
        super().__init__(agent_id, agent_type, tenant_context, scheduling_config, seed)

    def on_order_report(
        self, payload: dict[str, Any], from_agent: int, tick: int
    ) -> list[ActionEvent]:
        write = WritePattern(
            pattern="insert_gov_record",
            params={
                "entity_type": "seller",
                "entity_id": payload.get("seller_id"),
                "report_type": "order",
                "metrics_json": payload,
                "tick": tick,
            },
        )
        return [self._emitter.emit("gov_record_insert", tick, writes=[write])]

    def on_disruption_report(
        self, payload: dict[str, Any], from_agent: int, tick: int
    ) -> list[ActionEvent]:
        write = WritePattern(
            pattern="insert_gov_record",
            params={
                "entity_type": "supplier",
                "entity_id": payload.get("supplier_id"),
                "report_type": "disruption",
                "metrics_json": payload,
                "tick": tick,
            },
        )
        return [self._emitter.emit("gov_record_insert", tick, writes=[write])]

    def handle_compute_statistics(self, tick: int) -> list[ActionEvent]:
        period_ticks = self._scheduling.get("compute_statistics", {}).get("cycle_ticks", 10)

        self.emit_query(
            query_template="gov_economic_indicators",
            params={"period_ticks": period_ticks},
            context={"tick_triggered": tick},
        )

        return [self._emitter.emit("statistics_collection_started", tick)]

    def on_gov_economic_indicators_result(
        self, data: dict[str, Any], context: dict[str, Any], tick: int
    ) -> list[ActionEvent]:
        write = WritePattern(
            pattern="insert_statistics",
            params={
                "period": context.get("tick_triggered", tick),
                "gdp": data.get("gdp"),
                "transaction_volume": data.get("transaction_volume"),
                "avg_price_index": data.get("avg_price_index"),
                "active_sellers": data.get("active_entities"),
                "active_consumers": 0,
                "tick": tick,
            },
        )

        return [self._emitter.emit("statistics_published", tick, writes=[write])]
