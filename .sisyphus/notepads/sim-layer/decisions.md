## Decisions

- Lowered 'requires-python' from '>=3.12' to '>=3.10' in 'pyproject.toml' to match the current environment (Python 3.10.16). Updated 'tool.ruff.target-version' and 'tool.mypy.python_version' accordingly.

## Seller Agent Architecture
- **Order ID Generation**: Used a hash of the `order_request_id` for `store_order_id` to maintain consistency without a database in V1.
- **Mocked IDs**: Hardcoded transport (5000), government (9000), and supplier (2000) IDs for V1 inter-agent communication.
- **Inventory Decision**: Followed V1 spec of "always accept" for orders, while still performing the inventory check query to simulate production DB patterns.

## Consumer Agent Design (Task 9)
- Decided to handle `_skus_to_view` in `step()` to continue the browse->view pipeline across ticks.
- Simulation of "viewing" products in V1 uses faked SKU IDs generated during the browse step, as the actual database results from translator are not available in the agent's local scope.
- Funnel probabilities are simplified for V1 (e.g., trend_multiplier=1.0).

### Government Agent Events (Task 10)
- Decided to use `statistics_collection_started` and `statistics_published` as event types per requirement 4, even though they were not explicitly in the initial `specs/EVENTS.md` list.
- `gov_record_insert` is used for individual reports as per `specs/GOVERNMENT.md`.
## Community Subsystem Decisions
- Used a dictionary-based graph structure instead of NetworkX to minimize dependencies and improve performance for the simulation loop.
- Simplified the Watts-Strogatz initialization to a directed ring with optional random rewiring (implemented ring for now).
- Decay is applied globally to all consumers in the tick to ensure trends fade naturally.
## Community Subsystem Decisions
- Used a dictionary-based graph structure instead of NetworkX to minimize dependencies and improve performance for the simulation loop.
- Simplified the Watts-Strogatz initialization to a directed ring with optional random rewiring (implemented ring for now).
- Decay is applied globally to all consumers in the tick to ensure trends fade naturally.

