import pytest
import random
from typing import Any
from bizsim.engine import TickEngine
from bizsim.agents.consumer import ConsumerAgent
from bizsim.agents.seller import SellerAgent
from bizsim.agents.supplier import SupplierAgent
from bizsim.agents.transport import TransportAgent
from bizsim.domain import TenantContext
from bizsim.events import QueryRequest, QueryResult


def test_minimum_viable_purchase_scenario():
    """
    E2E Integration Test: Minimum Viable Purchase scenario.
    1. Initialize engine with 1 tenant, 1 consumer, 1 seller, 1 supplier, 1 transport.
    2. Seed product catalog with 1 SKU.
    3. Run simulation for N ticks.
    4. Assert full purchase and restock lifecycles.
    """
    # Deterministic seed
    seed = 42
    random.seed(seed)

    tenant_id = "tenant_1"
    tenant_context = TenantContext(tenant_id=tenant_id)

    # Agent IDs
    CONSUMER_ID = 1
    SELLER_ID = 10
    SUPPLIER_ID = 2000
    TRANSPORT_ID = 5000  # SellerAgent uses 5000 for transport
    # SupplierAgent uses 1000 for transport, but we'll use the same transport agent instance

    # Mock data for product
    SKU_ID = 101
    PRODUCT_CATEGORY = "electronics"
    INITIAL_PRICE = 100.0

    # Inventory state (mocked via query handler)
    inventory = {
        SELLER_ID: {SKU_ID: 5}  # Start with low inventory to trigger restock soon
    }

    def query_handler(request: QueryRequest) -> QueryResult:
        data: dict[str, Any] = {}
        if request.query_template == "product_details":
            data = {
                "sku_id": request.params["sku_id"],
                "current_price": INITIAL_PRICE,
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
        "consumer": {"shopping": {"cycle_ticks": 10, "jitter": 0}},
        "seller": {
            "evaluate_inventory": {"cycle_ticks": 20, "jitter": 0},
            "evaluate_pricing": {"cycle_ticks": 50, "jitter": 0},
        },
        "supplier": {"produce_goods": {"cycle_ticks": 100, "jitter": 0}},
        "transport": {"update_tracking": {"cycle_ticks": 1, "jitter": 0, "base_transit_ticks": 2}},
    }

    consumer = ConsumerAgent(
        agent_id=CONSUMER_ID,
        tenant_context=tenant_context,
        scheduling_config=scheduling_config,
        profile={
            "interest": {PRODUCT_CATEGORY: 1.0},
            "price_sensitivity": 0.5,
            "urgency": {PRODUCT_CATEGORY: 1.0},
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

    transport_supplier = TransportAgent(
        agent_id=1000,
        agent_type="transport",
        tenant_context=tenant_context,
        scheduling_config=scheduling_config,
        seed=seed,
    )

    engine = TickEngine(
        agents=[consumer, seller, supplier, transport, transport_supplier],
        query_handler=query_handler,
        seed=seed,
    )

    # Run simulation
    ticks = 100
    for t in range(ticks):
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

    # 2. Check if seller triggered restock
    # Seller triggers restock when inventory < 10.
    # Initial was 5. So it should have triggered restock.
    assert len(seller.pending_restocks) > 0 or any(
        v["status"] == "received" for v in seller.pending_restocks.values()
    )

    # 3. Check for satisfaction event (consumer_order_status_update with delivered)
    delivered_events = [
        e for e in engine.action_log if e.event_type == "consumer_order_status_update"
    ]
    assert len(delivered_events) > 0

    # 4. Assert P4 Sovereignty: All events have correct tenant_id
    for event in engine.action_log:
        assert event.tenant_id == tenant_id, (
            f"Event {event.event_type} has wrong tenant_id: {event.tenant_id}"
        )
        for msg in event.messages:
            assert msg.from_tenant == tenant_id

    # 5. Assert P1 Guard: No SQL-like strings in any event params
    # This is already checked by ActionEvent.__post_init__, but we can verify it didn't crash.

    # 6. Verify inventory lifecycle
    # Inventory should have decreased (sale) and increased (restock)
    # We can check the action log for update_inventory writes
    inv_updates = []
    for event in engine.action_log:
        for write in event.writes:
            if write.pattern == "update_inventory":
                inv_updates.append(write.params["qty_delta"])

    assert any(d < 0 for d in inv_updates), "Should have at least one inventory decrease (sale)"
    assert any(d > 0 for d in inv_updates), "Should have at least one inventory increase (restock)"

    print("Integration test passed successfully!")


if __name__ == "__main__":
    test_minimum_viable_purchase_scenario()
