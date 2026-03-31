import random
import sqlite3
from typing import Any

from bizsim.agents.consumer import ConsumerAgent
from bizsim.agents.government import GovernmentAgent
from bizsim.agents.seller import SellerAgent
from bizsim.agents.supplier import SupplierAgent
from bizsim.agents.transport import TransportAgent
from bizsim.domain import TenantContext
from bizsim.engine import TickEngine
from bizsim.events import QueryRequest, QueryResult
from bizsim.market import MarketFactory
from bizsim.markets.schema import create_tables, seed_catalog


def test_minimum_viable_purchase_scenario():
    """
    E2E Integration Test: Minimum Viable Purchase scenario.
    1. Initialize engine with 1 tenant, 1 consumer, 1 seller, 1 supplier, 2 transport, 1 government.
    2. Seed product catalog with 3 SKUs.
    3. Run simulation for 100 ticks.
    4. Assert full purchase and restock lifecycles.
    """
    # Deterministic seed
    seed = 42
    random.seed(seed)

    # Align tenant_id types: Use integer 1
    tenant_id_int = 1
    tenant_id_str = str(tenant_id_int)
    tenant_context = TenantContext(tenant_id=tenant_id_str)

    # Agent IDs
    CONSUMER_ID = 1
    SELLER_ID = 10
    SUPPLIER_ID = 2000
    TRANSPORT_ID = 5000
    GOVERNMENT_ID = 9000

    # In-process SQLite for catalog
    conn = sqlite3.connect(":memory:")
    create_tables(conn)

    # Seed catalog with 3 SKUs
    skus = [
        {
            "sku_id": 101,
            "name": "Wireless Earbuds",
            "category": "electronics",
            "base_price": 100.0,
            "price_floor": 80.0,
            "price_ceiling": 150.0,
        },
        {
            "sku_id": 102,
            "name": "Bluetooth Speaker",
            "category": "electronics",
            "base_price": 50.0,
            "price_floor": 40.0,
            "price_ceiling": 80.0,
        },
        {
            "sku_id": 103,
            "name": "Headphones",
            "category": "electronics",
            "base_price": 200.0,
            "price_floor": 150.0,
            "price_ceiling": 300.0,
        },
    ]
    seller_mappings = [
        {"sku_id": 101, "seller_id": SELLER_ID, "is_primary": True},
        {"sku_id": 102, "seller_id": SELLER_ID, "is_primary": True},
        {"sku_id": 103, "seller_id": SELLER_ID, "is_primary": True},
    ]
    supplier_mappings = [
        {"sku_id": 101, "supplier_id": SUPPLIER_ID, "is_primary": True},
        {"sku_id": 102, "supplier_id": SUPPLIER_ID, "is_primary": True},
        {"sku_id": 103, "supplier_id": SUPPLIER_ID, "is_primary": True},
    ]

    seed_catalog(
        conn,
        tenant_id=tenant_id_int,
        skus=skus,
        seller_mappings=seller_mappings,
        supplier_mappings=supplier_mappings,
    )

    catalog = MarketFactory(conn, tenant_id=tenant_id_int)

    # Inventory state (mocked via query handler)
    # Start with low inventory for all SKUs to trigger restock
    inventory = {SELLER_ID: {101: 5, 102: 5, 103: 5}}

    def query_handler(request: QueryRequest) -> QueryResult:
        data: dict[str, Any] = {}
        if request.query_template == "product_details":
            sku_id = request.params["sku_id"]
            sku_info = catalog.consumer.get_sku(sku_id)
            data = {
                "sku_id": sku_id,
                "current_price": sku_info["base_price"] if sku_info else 100.0,
                "avg_review": 4.5,
            }
        elif request.query_template == "inventory_check":
            seller_id = request.params.get("seller_id", SELLER_ID)
            sku_id = request.params["sku_id"]
            qty = inventory.get(seller_id, {}).get(sku_id, 0)
            data = {"sku_id": sku_id, "available_qty": qty}
        elif request.query_template == "inventory_levels":
            seller_id = request.params["seller_id"]
            inv_list: list[dict[str, Any]] = []
            for sku, qty in inventory.get(seller_id, {}).items():
                inv_list.append({"sku_id": sku, "qty": qty})
            data = {"inventory": inv_list}
        elif request.query_template == "sales_analytics":
            data = {"total_sales": 0}
        elif request.query_template == "competitor_prices":
            data = {"competitors": []}
        elif request.query_template == "gov_economic_indicators":
            data = {
                "gdp": 1000.0,
                "transaction_volume": 50,
                "avg_price_index": 1.0,
                "active_entities": 2,
            }

        return QueryResult(
            query_id=request.query_id,
            agent_id=request.agent_id,
            query_template=request.query_template,
            tick_issued=request.tick_issued,
            tick_available=request.tick_issued + 1,
            data=data,
        )

    # Configure agents
    scheduling_config = {
        "consumer": {"shopping": {"cycle_ticks": 5, "jitter": 0}},
        "seller": {
            "evaluate_inventory": {"cycle_ticks": 10, "jitter": 0},
            "evaluate_pricing": {"cycle_ticks": 50, "jitter": 0},
        },
        "supplier": {"produce_goods": {"cycle_ticks": 20, "jitter": 0}},
        "transport": {"update_tracking": {"cycle_ticks": 1, "jitter": 0, "base_transit_ticks": 2}},
        "government": {"compute_statistics": {"cycle_ticks": 30, "jitter": 0}},
    }

    consumer = ConsumerAgent(
        agent_id=CONSUMER_ID,
        tenant_context=tenant_context,
        scheduling_config=scheduling_config,
        profile={
            "interest": {"electronics": 1.0},
            "price_sensitivity": 0.5,
            "urgency": {"electronics": 1.0},
        },
        seed=seed,
    )

    seller = SellerAgent(
        agent_id=SELLER_ID,
        tenant_context=tenant_context,
        scheduling_config=scheduling_config,
        seed=seed,
    )

    supplier = SupplierAgent(
        agent_id=SUPPLIER_ID,
        agent_type="supplier",
        tenant_context=tenant_context,
        scheduling_config=scheduling_config,
        seed=seed,
    )

    transport = TransportAgent(
        agent_id=TRANSPORT_ID,
        agent_type="transport",
        tenant_context=tenant_context,
        scheduling_config=scheduling_config,
        seed=seed,
    )

    government = GovernmentAgent(
        agent_id=GOVERNMENT_ID,
        agent_type="government",
        tenant_context=tenant_context,
        scheduling_config=scheduling_config,
        seed=seed,
    )

    peer_agents_config = {"transport": TRANSPORT_ID, "government": GOVERNMENT_ID}

    engine = TickEngine(
        agents=[consumer, seller, supplier, transport, government],
        query_handler=query_handler,
        seed=seed,
        catalog=catalog,
        peer_agents_config=peer_agents_config,
    )

    # Run simulation
    ticks = 100
    for _t in range(ticks):
        engine.step()

        for event in engine.action_log:
            if event.tick == engine.current_tick:
                for write in event.writes:
                    if write.pattern == "update_inventory":
                        sku_id = write.params["sku_id"]
                        delta = write.params["qty_delta"]
                        if sku_id not in inventory[SELLER_ID]:
                            inventory[SELLER_ID][sku_id] = 100
                        inventory[SELLER_ID][sku_id] += delta

    # Assertions

    # 1. Check if consumer received product (completed_orders)
    assert len(consumer.completed_orders) > 0, "Consumer should have completed at least one order"
    assert any(o["status"] == "delivered" for o in consumer.completed_orders)

    # Verify that consumer completed orders contain real SKU IDs from catalog
    catalog_sku_ids = {s["sku_id"] for s in skus}
    for order in consumer.completed_orders:
        assert order["sku_id"] in catalog_sku_ids

    # 2. Check if seller triggered restock
    assert len(seller.pending_restocks) > 0 or any(
        v["status"] == "received" for v in seller.pending_restocks.values()
    )

    # Verify that seller triggered restocks to the real supplier ID
    # In SellerAgent, restock messages are sent to the supplier.
    # We can check the action log for restock messages or check
    # seller's pending_restocks if they store supplier_id.
    # Actually, SellerAgent.handle_evaluate_inventory gets supplier_id from catalog.
    # Let's check action log for messages sent to SUPPLIER_ID.
    restock_requests = [
        msg
        for event in engine.action_log
        for msg in event.messages
        if msg.to_agent == SUPPLIER_ID and msg.msg_type == "restock_order"
    ]
    assert len(restock_requests) > 0, "Seller should have sent restock requests to Supplier"

    # 3. Check for satisfaction event (consumer_order_status_update with delivered)
    delivered_events = [
        e for e in engine.action_log if e.event_type == "consumer_order_status_update"
    ]
    assert len(delivered_events) > 0

    # 4. Assert P4 Sovereignty: All events have correct tenant_id
    for event in engine.action_log:
        assert event.tenant_id == tenant_id_str, (
            f"Event {event.event_type} has wrong tenant_id: {event.tenant_id}"
        )
        for msg in event.messages:
            assert msg.from_tenant == tenant_id_str

    # 5. Verify inventory lifecycle
    inv_updates = []
    for event in engine.action_log:
        for write in event.writes:
            if write.pattern == "update_inventory":
                inv_updates.append(write.params["qty_delta"])

    assert any(d < 0 for d in inv_updates), "Should have at least one inventory decrease (sale)"
    assert any(d > 0 for d in inv_updates), "Should have at least one inventory increase (restock)"

    # 6. Verify Government received reports
    gov_records = [
        w for event in engine.action_log for w in event.writes if w.pattern == "insert_gov_record"
    ]
    assert len(gov_records) > 0, "Government should have received reports"

    print("Integration test passed successfully!")


if __name__ == "__main__":
    test_minimum_viable_purchase_scenario()
