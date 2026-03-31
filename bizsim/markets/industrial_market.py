import sqlite3
from typing import Any


class SqliteIndustrialMarket:
    def __init__(self, conn: sqlite3.Connection, tenant_id: int) -> None:
        self.conn: sqlite3.Connection = conn
        self.tenant_id: int = tenant_id

    def _execute_query(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_suppliers_for_sku(self, sku_id: int) -> list[dict[str, Any]]:
        query = "SELECT * FROM sku_supplier_mapping WHERE tenant_id = ? AND sku_id = ?"
        return self._execute_query(query, (self.tenant_id, sku_id))

    def get_bom(self, sku_id: int) -> list[dict[str, Any]]:
        query = """
            SELECT b.*, p.name as part_name, p.category as part_category
            FROM bill_of_materials b
            JOIN parts p ON b.tenant_id = p.tenant_id AND b.part_id = p.part_id
            WHERE b.tenant_id = ? AND b.sku_id = ?
        """
        return self._execute_query(query, (self.tenant_id, sku_id))

    def get_parts_for_supplier(self, supplier_id: int) -> list[dict[str, Any]]:
        query = """
            SELECT p.* FROM parts p
            JOIN sku_supplier_mapping m ON p.tenant_id = m.tenant_id AND p.part_id = m.part_id
            WHERE p.tenant_id = ? AND m.supplier_id = ?
        """
        return self._execute_query(query, (self.tenant_id, supplier_id))
