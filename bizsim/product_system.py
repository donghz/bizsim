import sqlite3
from typing import Any, Protocol


class ProductSystem(Protocol):
    pass


def create_tables(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sku_catalog (
        tenant_id     INTEGER NOT NULL,
        sku_id        INTEGER NOT NULL,
        name          TEXT NOT NULL,
        category      TEXT NOT NULL,
        subcategory   TEXT,
        base_price    REAL NOT NULL,
        price_floor   REAL NOT NULL,
        price_ceiling REAL NOT NULL,
        weight_kg     REAL,
        brand         TEXT,
        tags          TEXT,
        created_tick  INTEGER DEFAULT 0,
        PRIMARY KEY (tenant_id, sku_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sku_seller_mapping (
        tenant_id  INTEGER NOT NULL,
        sku_id     INTEGER NOT NULL,
        seller_id  INTEGER NOT NULL,
        is_primary BOOLEAN DEFAULT FALSE,
        PRIMARY KEY (tenant_id, sku_id, seller_id),
        FOREIGN KEY (tenant_id, sku_id) REFERENCES sku_catalog(tenant_id, sku_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS parts (
        tenant_id  INTEGER NOT NULL,
        part_id    INTEGER NOT NULL,
        name       TEXT NOT NULL,
        category   TEXT NOT NULL,
        unit_cost  REAL,
        PRIMARY KEY (tenant_id, part_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sku_supplier_mapping (
        tenant_id       INTEGER NOT NULL,
        sku_id          INTEGER NOT NULL,
        supplier_id     INTEGER NOT NULL,
        part_id         INTEGER,
        is_primary      BOOLEAN DEFAULT FALSE,
        lead_time_ticks INTEGER DEFAULT 10,
        PRIMARY KEY (tenant_id, sku_id, supplier_id),
        FOREIGN KEY (tenant_id, sku_id) REFERENCES sku_catalog(tenant_id, sku_id),
        FOREIGN KEY (tenant_id, part_id) REFERENCES parts(tenant_id, part_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bill_of_materials (
        tenant_id  INTEGER NOT NULL,
        bom_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        sku_id     INTEGER NOT NULL,
        part_id    INTEGER NOT NULL,
        qty        INTEGER NOT NULL DEFAULT 1,
        layer      INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (tenant_id, sku_id) REFERENCES sku_catalog(tenant_id, sku_id),
        FOREIGN KEY (tenant_id, part_id) REFERENCES parts(tenant_id, part_id)
    );
    """)

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sku_category ON sku_catalog(tenant_id, category);"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_sku_seller ON sku_seller_mapping(tenant_id, seller_id);"
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_sku_supplier
        ON sku_supplier_mapping(tenant_id, supplier_id);
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_bom_sku ON bill_of_materials(tenant_id, sku_id);"
    )

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_bom_part ON bill_of_materials(tenant_id, part_id);"
    )

    conn.commit()


def seed_catalog(
    conn: sqlite3.Connection,
    tenant_id: int,
    skus: list[dict[str, Any]],
    parts_list: list[dict[str, Any]] | None = None,
    bom_list: list[dict[str, Any]] | None = None,
    seller_mappings: list[dict[str, Any]] | None = None,
    supplier_mappings: list[dict[str, Any]] | None = None,
) -> None:
    cursor = conn.cursor()

    if skus:
        sku_defaults = {
            "subcategory": None,
            "weight_kg": None,
            "brand": None,
            "tags": None,
            "created_tick": 0,
        }
        cursor.executemany(
            """
        INSERT INTO sku_catalog (
            tenant_id, sku_id, name, category, subcategory, base_price,
            price_floor, price_ceiling, weight_kg, brand, tags, created_tick
        ) VALUES (
            :tenant_id, :sku_id, :name, :category, :subcategory, :base_price,
            :price_floor, :price_ceiling, :weight_kg, :brand, :tags, :created_tick
        )
        """,
            [{**sku_defaults, **s, "tenant_id": tenant_id} for s in skus],
        )

    if parts_list:
        parts_defaults = {"unit_cost": None}
        cursor.executemany(
            """
        INSERT INTO parts (tenant_id, part_id, name, category, unit_cost)
        VALUES (:tenant_id, :part_id, :name, :category, :unit_cost)
        """,
            [{**parts_defaults, **p, "tenant_id": tenant_id} for p in parts_list],
        )

    if bom_list:
        bom_defaults = {"qty": 1, "layer": 0}
        cursor.executemany(
            """
        INSERT INTO bill_of_materials (tenant_id, sku_id, part_id, qty, layer)
        VALUES (:tenant_id, :sku_id, :part_id, :qty, :layer)
        """,
            [{**bom_defaults, **b, "tenant_id": tenant_id} for b in bom_list],
        )

    if seller_mappings:
        seller_defaults = {"is_primary": False}
        cursor.executemany(
            """
        INSERT INTO sku_seller_mapping (tenant_id, sku_id, seller_id, is_primary)
        VALUES (:tenant_id, :sku_id, :seller_id, :is_primary)
        """,
            [{**seller_defaults, **sm, "tenant_id": tenant_id} for sm in seller_mappings],
        )

    if supplier_mappings:
        supplier_defaults = {"part_id": None, "is_primary": False, "lead_time_ticks": 10}
        cursor.executemany(
            """
        INSERT INTO sku_supplier_mapping
            (tenant_id, sku_id, supplier_id, part_id, is_primary, lead_time_ticks)
        VALUES (:tenant_id, :sku_id, :supplier_id, :part_id, :is_primary, :lead_time_ticks)
        """,
            [{**supplier_defaults, **sum_m, "tenant_id": tenant_id} for sum_m in supplier_mappings],
        )

    conn.commit()


def lookup_sku(conn: sqlite3.Connection, tenant_id: int, sku_id: int) -> dict[str, Any] | None:
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM sku_catalog WHERE tenant_id = ? AND sku_id = ?", (tenant_id, sku_id)
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def lookup_bom(conn: sqlite3.Connection, tenant_id: int, sku_id: int) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT b.*, p.name as part_name, p.category as part_category
        FROM bill_of_materials b
        JOIN parts p ON b.tenant_id = p.tenant_id AND b.part_id = p.part_id
        WHERE b.tenant_id = ? AND b.sku_id = ?
    """,
        (tenant_id, sku_id),
    )
    return [dict(row) for row in cursor.fetchall()]


def lookup_sku_supplier_mapping(
    conn: sqlite3.Connection, tenant_id: int, sku_id: int
) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM sku_supplier_mapping WHERE tenant_id = ? AND sku_id = ?", (tenant_id, sku_id)
    )
    return [dict(row) for row in cursor.fetchall()]
