import sqlite3
import pytest
from typing import Any
from bizsim.product_system import create_tables, seed_catalog

try:
    from bizsim.product_catalog import SqliteProductCatalog
except ImportError:
    pass


@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    return conn


@pytest.fixture
def catalog(db_conn):
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
        {
            "sku_id": 102,
            "name": "Mouse",
            "category": "Electronics",
            "base_price": 20.0,
            "price_floor": 15.0,
            "price_ceiling": 30.0,
        },
        {
            "sku_id": 103,
            "name": "Keyboard",
            "category": "Electronics",
            "base_price": 50.0,
            "price_floor": 40.0,
            "price_ceiling": 80.0,
        },
        {
            "sku_id": 104,
            "name": "Bread",
            "category": "Food",
            "base_price": 2.0,
            "price_floor": 1.5,
            "price_ceiling": 3.0,
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
    sellers = [
        {"sku_id": 101, "seller_id": 1001, "is_primary": True},
        {"sku_id": 101, "seller_id": 1002, "is_primary": False},
        {"sku_id": 102, "seller_id": 1001, "is_primary": True},
    ]
    suppliers = [
        {"sku_id": 101, "supplier_id": 2001, "part_id": 501, "is_primary": True},
        {"sku_id": 101, "supplier_id": 2002, "part_id": 502, "is_primary": False},
    ]

    seed_catalog(db_conn, tenant_id, skus, parts, bom, sellers, suppliers)

    seed_catalog(
        db_conn,
        2,
        [
            {
                "sku_id": 999,
                "name": "Hidden",
                "category": "Secret",
                "base_price": 0.0,
                "price_floor": 0.0,
                "price_ceiling": 0.0,
            }
        ],
    )

    return SqliteProductCatalog(db_conn, tenant_id)


def test_browse_skus(catalog):
    skus = catalog.browse_skus()
    assert len(skus) == 4
    sku_ids = {s["sku_id"] for s in skus}
    assert sku_ids == {101, 102, 103, 104}
    assert 999 not in sku_ids


def test_browse_skus_by_category(catalog):
    skus = catalog.browse_skus(category="Electronics")
    assert len(skus) == 3
    for s in skus:
        assert s["category"] == "Electronics"

    skus_food = catalog.browse_skus(category="Food")
    assert len(skus_food) == 1
    assert skus_food[0]["sku_id"] == 104

    skus_none = catalog.browse_skus(category="Missing")
    assert len(skus_none) == 0


def test_browse_skus_limit(catalog):
    skus = catalog.browse_skus(limit=2)
    assert len(skus) == 2


def test_get_sku(catalog):
    sku = catalog.get_sku(101)
    assert sku is not None
    assert sku["name"] == "Laptop"

    sku_missing = catalog.get_sku(999)
    assert sku_missing is None


def test_get_sellers_for_sku(catalog):
    sellers = catalog.get_sellers_for_sku(101)
    assert len(sellers) == 2
    seller_ids = {s["seller_id"] for s in sellers}
    assert seller_ids == {1001, 1002}


def test_get_suppliers_for_sku(catalog):
    suppliers = catalog.get_suppliers_for_sku(101)
    assert len(suppliers) == 2
    supplier_ids = {s["supplier_id"] for s in suppliers}
    assert supplier_ids == {2001, 2002}


def test_get_bom(catalog):
    bom = catalog.get_bom(101)
    assert len(bom) == 2
    part_ids = {b["part_id"] for b in bom}
    assert part_ids == {501, 502}


def test_get_skus_for_seller(catalog):
    skus = catalog.get_skus_for_seller(1001)
    assert len(skus) == 2
    sku_ids = {s["sku_id"] for s in skus}
    assert sku_ids == {101, 102}


def test_get_parts_for_supplier(catalog):
    parts = catalog.get_parts_for_supplier(2001)
    assert len(parts) == 1
    assert parts[0]["part_id"] == 501
