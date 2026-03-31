# AGENTS.md — BizSim Developer Knowledge Base

## Project Overview
BizSim is a tick-based multi-agent market simulator with an event-driven architecture. It combines a Python simulation layer with a Go workload translator to generate realistic database workloads for TiDB benchmarking. Agents simulate economic behaviors (buying, selling, producing) that result in complex, concurrent database operations.

## Architecture
- **Three-Channel Event System**:
    - **Ch.1 Action Events**: Agent-to-DB writes. Translated by the Go translator into SQL (INSERT/UPDATE/SELECT Mode 1).
    - **Ch.2 Inter-Agent Messaging**: Agent-to-Agent in-memory communication. No DB impact, processed by the simulation engine.
    - **Ch.3 Query Pipeline**: Agent-to-DB async reads. Translated by Go into SQL, reduced to domain structs, and delivered to agent inboxes in future ticks.
- **Tick-Based Engine**: The `TickEngine` orchestrates discrete ticks. Each tick includes inbox draining, agent decision cycles, and event routing.
- **Workload Translator**: A Go service that mediates all database access. Agents never write SQL; they emit domain patterns that the translator maps to SQL via a YAML operation catalog.
- **Multi-Tenant Isolation**: Enforced via `TenantContext`. Each agent is bound to a specific tenant and can only write to its own tenant's tables.

## Directory Structure
- `bizsim/`: Core Python simulation package.
- `bizsim/agents/`: Agent implementations (`consumer`, `seller`, `supplier`, `transport`, `government`).
- `bizsim/agents/base.py`: `BaseAgent` and `AgentProtocol` defining the lifecycle.
- `bizsim/agents/_sandbox.py`: Security layer blocking dangerous imports.
- `bizsim/markets/`: Market subsystem implementations (B2C and B2B).
- `bizsim/markets/schema.py`: SQLite DDL, catalog seeding, and lookup helpers.
- `bizsim/markets/consumer_market.py`: `SqliteConsumerMarket` — B2C operations (browse, SKU, sellers).
- `bizsim/markets/industrial_market.py`: `SqliteIndustrialMarket` — B2B operations (suppliers, BOM, parts).
- `bizsim/market.py`: Market facade — `ConsumerMarket`/`IndustrialMarket` Protocols + `MarketFactory`.
- `bizsim/society/`: Society subsystem implementations.
- `bizsim/society/community.py`: `CommunitySubsystem` — social influence (Independent Cascade model).
- `bizsim/society/media.py`: Media subsystem (V2 placeholder).
- `bizsim/social.py`: Society facade — re-exports `CommunitySubsystem`, `CommunityConfig`, etc.
- `bizsim/engine.py`: `TickEngine` orchestrating the tick loop and event routing.
- `bizsim/domain.py`: Core types including `TenantContext`, `ActionEvent`, and SQL keyword guards.
- `bizsim/events.py`: `EventEmitter`, `QueryRequest`, and `QueryResult`.
- `bizsim/channels.py`: Definitions for `InterAgentMessage` and `InboxItem`.
- `go-translator/`: Go workload translator that converts domain events into SQL.
- `specs/`: 14 detailed specification files defining protocols and behaviors.
- `tests/`: Test suite containing unit and integration tests.
- `.github/workflows/arch-guard.yml`: CI guardrails (G1-G6) enforcing architectural invariants.

## Key Conventions
- **Frozen Dataclasses**: Core domain types like `TenantContext` use `frozen=True` for immutability.
- **Sandbox Restrictions**: Agents cannot import modules that allow direct system or DB access. **FORBIDDEN_MODULES**: `sqlite3`, `sqlalchemy`, `psycopg2`, `mysql`, `requests`, `urllib`, `http.client`, `smtplib`, `os`, `subprocess`, `socket`.
- **Tenant Write Sovereignty**: Enforced by `EventEmitter`. Agents only write to their own tenant (P4).
- **No SQL in Logic**: SQL lives in the Go operation catalog, never in Go code literals or Python agent code (P9).
- **Deterministic Randomness**: Controlled via random seeds for reproducibility.
- **Method Patterns**:
    - Inbox handlers: `on_{msg_type}(payload, from_agent, tick) -> list[ActionEvent]`
    - Query handlers: `on_{template}_result(data, context, tick) -> list[ActionEvent]`
    - Scheduled actions: `handle_{action_name}(tick) -> list[ActionEvent]`

## Development Commands
- `pytest tests/`: Run all Python tests (unit and integration).
- `cd go-translator && go test ./...`: Run all Go translator tests.
- `mypy --strict bizsim/`: Run strict type checking.
- `ruff check bizsim/ tests/`: Run linting and style checks.

## Architectural Invariants (NEVER VIOLATE)
- **P1**: No SQL/ORM imports in `bizsim/agents/`. Enforced by `_sandbox.py` and CI.
- **P4**: `TenantContext` is immutable. `tenant_id` is baked into the `EventEmitter` and cannot be forged by agents.
- **P9**: Only `go-translator/pkg/executor/` and `pkg/internal/db/` are permitted to touch `database/sql`.
- **Community Subsystem**: This is not an agent; it is a simulation engine subsystem called during the tick loop.
- **Channel 2 Isolation**: Inter-agent messages are in-memory only and must never cross the translator boundary or touch the DB.

## Adding a New Agent
1. **Extend BaseAgent**: Create `bizsim/agents/{name}.py` and inherit from `BaseAgent`.
2. **Implement Handlers**: Add `on_` methods for messages/queries and `handle_` methods for scheduled tasks.
3. **Configure Scheduling**: Define `cycle_ticks` and `jitter` in the agent's scheduling configuration.
4. **Define Tests**: Add unit tests in `tests/test_{name}.py`.
5. **Register Agent**: Add the new agent type to the `TickEngine` initialization.

## Spec Files Reference
- `ARCHITECTURE.md`: High-level system design, channels, and tick loop sequence.
- `CONTRACTS.md`: Definitions for all shared Python dataclasses and protocols.
- `AGENT_BASE.md`: Detailed lifecycle and scheduling logic for all agents.
- `GO_TRANSLATOR.md`: Translator architecture and the SQL operation catalog.
- `MESSAGES.md`: Registry of all Channel 2 inter-agent message types.
- `EVENTS.md`: Registry of all Channel 1 action event types.
- `QUERIES.md`: Registry of all Channel 3 query templates and result schemas.
- `CONSUMER.md`: Consumer agent behavior and purchase funnel logic.
- `SELLER.md`: Seller agent pricing strategy and inventory management.
- `SUPPLIER.md`: Supplier production and restock logic.
- `TRANSPORT.md`: Logistics state machines and shipment tracking.
- `GOVERNMENT.md`: Aggregation logic and policy intervention rules.
- `COMMUNITY.md`: Social influence model and network diffusion logic.
- `PRODUCT_SYSTEM.md`: Catalog structure and SKU management rules.
