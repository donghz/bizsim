- Implemented ProductCatalog Protocol and SqliteProductCatalog.
- SqliteProductCatalog binds tenant_id at construction and uses it for all queries.
- browse_skus uses ORDER BY RANDOM() as per specification.
- Unit tests verify all methods and tenant isolation.
- Updated ProductCatalog.browse_skus to support optional category filtering.
- Implemented dynamic SQL query building in SqliteProductCatalog.browse_skus.
- Added test_browse_skus_by_category to tests/test_product_catalog.py.

## Agent Injection Pattern
- Modified `BaseAgent.__init__` to support optional injection of `ProductCatalog` and `peer_agents`.
- Used keyword-only arguments to maintain backward compatibility.
- Leveraged `TYPE_CHECKING` for `ProductCatalog` to avoid runtime dependencies on prohibited modules (P1).
- Default `peer_agents` to `{}` ensures robustness.

## ConsumerAgent Catalog Integration
- Injected `ProductCatalog` via `BaseAgent` constructor using `TYPE_CHECKING` for type hints to avoid runtime DB dependency in agents.
- Updated `handle_browse_catalog` to use `catalog.browse_skus` for realistic SKU discovery.
- Enhanced `on_product_details_result` to use `catalog.get_sku` for fetching `base_price`, enabling more realistic purchase decisions based on price relative to base.
- Refined `_initiate_purchase` to pick a real `seller_id` from `catalog.get_sellers_for_sku`.
- Removed dangerous fallback `seller_id = 1` in `_cancel_order`, returning empty list if order context is missing.
- Verified that the agent gracefully handles cases where `catalog` is None or returns empty results.

## SellerAgent ProductCatalog Integration
- Integrated `ProductCatalog` and `peer_agents` into `SellerAgent`.
- Replaced hardcoded IDs with lookups from `self.peer_agents`.
- Implemented rule-based pricing using `self.catalog.get_skus_for_seller` and `sales_cache`.
- Pricing respects `price_floor` and `price_ceiling` from the catalog.
- Restock logic now uses `self.catalog.get_suppliers_for_sku` to identify the primary supplier.
- Added graceful degradation for cases where `catalog` or `peer_agents` are not provided.
- Regression tests for `SellerAgent` were updated to mock the catalog and provide peer IDs.

### SupplierAgent ProductCatalog Integration
- Wire  into  for BOM and part enrichment.
- Use  to dynamically lookup transport agent IDs.
- Handle missing  or  gracefully to maintain base functionality.
- Explicitly type dictionary payloads as `dict[str, Any]` when using `basedpyright` to avoid strict type inference errors when mixing types in dictionaries.

### SupplierAgent ProductCatalog Integration
- Wire `ProductCatalog` into `SupplierAgent` for BOM and part enrichment.
- Use `self.peer_agents.get("transport")` to dynamically lookup transport agent IDs.
- Handle missing `catalog` or `transport` gracefully to maintain base functionality.
- Explicitly type dictionary payloads as `dict[str, Any]` when using `basedpyright` to avoid strict type inference errors when mixing types in dictionaries.

## Dependency Injection in TickEngine
- **Pattern**:  now acts as a dependency injector for agents.
- **Mechanism**: Uses  to check if an agent supports  or  before setting them. This preserves backward compatibility for agents that haven't been updated to support these attributes yet.
- **Type Safety**: Used  and string forward references () in  to avoid circular imports and runtime dependencies on  (since  protocol lives in a file that might eventually import it, although currently it's a protocol).
- **Flexibility**: The injection logic is isolated in a private  method called during .

## Dependency Injection in TickEngine
- **Pattern**: TickEngine now acts as a dependency injector for agents.
- **Mechanism**: Uses hasattr to check if an agent supports catalog or peer_agents before setting them. This preserves backward compatibility for agents that haven't been updated to support these attributes yet.
- **Type Safety**: Used TYPE_CHECKING and string forward references ("ProductCatalog | None") in engine.py to avoid circular imports and runtime dependencies on sqlite3 (since ProductCatalog protocol lives in a file that might eventually import it, although currently it's a protocol).
- **Flexibility**: The injection logic is isolated in a private _inject_dependencies method called during __init__.

### Integration Testing with ProductCatalog
- The 'SqliteProductCatalog' requires an active sqlite3 connection and a 'tenant_id'.
- In tests, use 'sqlite3.connect(":memory:")' and 'create_tables(conn)' to initialize the schema.
- 'seed_catalog' is the primary way to programmatically inject data into the catalog for testing.
- Aligning 'tenant_id' types between 'TenantContext' (string) and 'ProductCatalog' (integer) is crucial for consistency.
- 'TickEngine' now successfully injects 'catalog' and 'peer_agents_config' into all registered agents.
- Verification of complex agent interactions (like restocks) should check 'InterAgentMessage' types in the 'action_log'. Note that message types like 'restock_order' are lowercase in the current implementation.
