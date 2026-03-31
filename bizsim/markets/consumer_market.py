import sqlite3
from typing import Any


class SqliteConsumerMarket:
    def __init__(self, conn: sqlite3.Connection, tenant_id: int) -> None:
        self.conn: sqlite3.Connection = conn
        self.tenant_id: int = tenant_id

    def _execute_query(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def browse_skus(self, category: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = """
            SELECT * FROM sku_catalog
            WHERE tenant_id = ?
        """
        params: list[Any] = [self.tenant_id]

        if category is not None:
            query += " AND category = ?"
            params.append(category)

        query += """
            ORDER BY RANDOM()
            LIMIT ?
        """
        params.append(limit)
        return self._execute_query(query, tuple(params))

    def get_sku(self, sku_id: int) -> dict[str, Any] | None:
        query = "SELECT * FROM sku_catalog WHERE tenant_id = ? AND sku_id = ?"
        results = self._execute_query(query, (self.tenant_id, sku_id))
        return results[0] if results else None

    def get_sellers_for_sku(self, sku_id: int) -> list[dict[str, Any]]:
        query = "SELECT * FROM sku_seller_mapping WHERE tenant_id = ? AND sku_id = ?"
        return self._execute_query(query, (self.tenant_id, sku_id))

    def get_skus_for_seller(self, seller_id: int) -> list[dict[str, Any]]:
        query = """
            SELECT c.* FROM sku_catalog c
            JOIN sku_seller_mapping m ON c.tenant_id = m.tenant_id AND c.sku_id = m.sku_id
            WHERE c.tenant_id = ? AND m.seller_id = ?
        """
        return self._execute_query(query, (self.tenant_id, seller_id))
