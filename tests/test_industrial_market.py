import sqlite3

import pytest

from bizsim.market import MarketFactory
from bizsim.markets.schema import create_tables, seed_catalog


@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    return conn


@pytest.fixture
def factory(db_conn) -> MarketFactory:
    tenant_id = 1
    skus = [
        {
            "sku_id": 101,
            "name": "Laptop",
            "category": "Electronics",
            "base_price": 1000.0,
            "price_floor": 800.0,
            "price_ceiling": 1500.0,
        },
    ]
    parts = [
        {"part_id": 501, "name": "CPU", "category": "Component", "unit_cost": 200.0},
        {"part_id": 502, "name": "RAM", "category": "Component", "unit_cost": 50.0},
    ]
    bom = [
        {"sku_id": 101, "part_id": 501, "qty": 1},
        {"sku_id": 101, "part_id": 502, "qty": 2},
    ]
    suppliers = [
        {"sku_id": 101, "supplier_id": 2001, "part_id": 501, "is_primary": True},
        {"sku_id": 101, "supplier_id": 2002, "part_id": 502, "is_primary": False},
    ]

    seed_catalog(db_conn, tenant_id, skus, parts, bom, supplier_mappings=suppliers)

    return MarketFactory(db_conn, tenant_id)


def test_get_suppliers_for_sku(factory):
    suppliers = factory.industrial.get_suppliers_for_sku(101)
    assert len(suppliers) == 2
    supplier_ids = {s["supplier_id"] for s in suppliers}
    assert supplier_ids == {2001, 2002}


def test_get_bom(factory):
    bom = factory.industrial.get_bom(101)
    assert len(bom) == 2
    part_ids = {b["part_id"] for b in bom}
    assert part_ids == {501, 502}


def test_get_parts_for_supplier(factory):
    parts = factory.industrial.get_parts_for_supplier(2001)
    assert len(parts) == 1
    assert parts[0]["part_id"] == 501
