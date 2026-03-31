import sqlite3
import pytest
from bizsim.product_system import (
    create_tables,
    seed_catalog,
    lookup_sku,
    lookup_bom,
    lookup_sku_supplier_mapping,
)


@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    create_tables(conn)
    yield conn
    conn.close()


def test_seed_and_lookup_sku(db_conn):
    tenant_id = 1
    skus = [
        {
            "sku_id": 101,
            "name": "Test SKU",
            "category": "Electronics",
            "subcategory": "Gadgets",
            "base_price": 100.0,
            "price_floor": 80.0,
            "price_ceiling": 120.0,
            "weight_kg": 0.5,
            "brand": "TestBrand",
            "tags": '["test", "new"]',
            "created_tick": 0,
        }
    ]
    seed_catalog(db_conn, tenant_id, skus)

    result = lookup_sku(db_conn, tenant_id, 101)
    assert result is not None
    assert result["name"] == "Test SKU"
    assert result["base_price"] == 100.0


def test_multi_tenant_isolation(db_conn):
    skus_t1 = [
        {
            "sku_id": 1,
            "name": "T1 SKU",
            "category": "C",
            "base_price": 10,
            "price_floor": 5,
            "price_ceiling": 15,
        }
    ]
    skus_t2 = [
        {
            "sku_id": 1,
            "name": "T2 SKU",
            "category": "C",
            "base_price": 20,
            "price_floor": 10,
            "price_ceiling": 30,
        }
    ]

    seed_catalog(db_conn, 1, skus_t1)
    seed_catalog(db_conn, 2, skus_t2)

    res1 = lookup_sku(db_conn, 1, 1)
    res2 = lookup_sku(db_conn, 2, 1)

    assert res1["name"] == "T1 SKU"
    assert res2["name"] == "T2 SKU"


def test_bom_lookup(db_conn):
    tenant_id = 1
    skus = [
        {
            "sku_id": 101,
            "name": "Phone",
            "category": "Electronics",
            "base_price": 500,
            "price_floor": 400,
            "price_ceiling": 600,
        }
    ]
    parts = [{"part_id": 501, "name": "Battery", "category": "Components", "unit_cost": 20}]
    bom = [{"sku_id": 101, "part_id": 501, "qty": 1, "layer": 0}]

    seed_catalog(db_conn, tenant_id, skus, parts_list=parts, bom_list=bom)

    bom_res = lookup_bom(db_conn, tenant_id, 101)
    assert len(bom_res) == 1
    assert bom_res[0]["part_name"] == "Battery"
    assert bom_res[0]["qty"] == 1


def test_supplier_mapping_lookup(db_conn):
    tenant_id = 1
    skus = [
        {
            "sku_id": 101,
            "name": "Phone",
            "category": "Electronics",
            "base_price": 500,
            "price_floor": 400,
            "price_ceiling": 600,
        }
    ]
    suppliers = [{"sku_id": 101, "supplier_id": 99, "is_primary": True, "lead_time_ticks": 5}]

    seed_catalog(db_conn, tenant_id, skus, supplier_mappings=suppliers)

    sup_res = lookup_sku_supplier_mapping(db_conn, tenant_id, 101)
    assert len(sup_res) == 1
    assert sup_res[0]["supplier_id"] == 99
    assert bool(sup_res[0]["is_primary"]) is True


def test_lookup_nonexistent(db_conn):
    result = lookup_sku(db_conn, 1, 999)
    assert result is None

    bom_res = lookup_bom(db_conn, 1, 999)
    assert bom_res == []

    sup_res = lookup_sku_supplier_mapping(db_conn, 1, 999)
    assert sup_res == []
