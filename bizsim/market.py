import sqlite3
from typing import Any, Protocol

from bizsim.markets.consumer_market import SqliteConsumerMarket
from bizsim.markets.industrial_market import SqliteIndustrialMarket


class ConsumerMarket(Protocol):
    def browse_skus(
        self, category: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]: ...

    def get_sku(self, sku_id: int) -> dict[str, Any] | None: ...

    def get_sellers_for_sku(self, sku_id: int) -> list[dict[str, Any]]: ...

    def get_skus_for_seller(self, seller_id: int) -> list[dict[str, Any]]: ...


class IndustrialMarket(Protocol):
    def get_suppliers_for_sku(self, sku_id: int) -> list[dict[str, Any]]: ...

    def get_bom(self, sku_id: int) -> list[dict[str, Any]]: ...

    def get_parts_for_supplier(self, supplier_id: int) -> list[dict[str, Any]]: ...


class MarketFactory:
    def __init__(self, conn: sqlite3.Connection, tenant_id: int) -> None:
        self._conn = conn
        self._tenant_id = tenant_id
        self._consumer_market = SqliteConsumerMarket(conn, tenant_id)
        self._industrial_market = SqliteIndustrialMarket(conn, tenant_id)

    @property
    def consumer(self) -> ConsumerMarket:
        return self._consumer_market

    @property
    def industrial(self) -> IndustrialMarket:
        return self._industrial_market
