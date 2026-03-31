# BizSim

> Tick-based multi-agent market simulator with event-driven architecture

BizSim simulates a complete economic ecosystem — consumers, sellers, suppliers, transport, and government — using discrete-tick simulation with deterministic replay. Designed to generate realistic, diverse database workloads for benchmarking distributed databases like TiDB.

## Features

- **Multi-agent simulation** — 5 agent types with distinct behaviors and intelligence tiers
- **Three-channel architecture** — Ch.1 (persistence events), Ch.2 (inter-agent messaging), Ch.3 (async query pipeline)
- **Tenant write sovereignty** — Each agent writes only to its own tenant's data
- **Agent sandbox** — Agents are isolated from direct DB access (P1 enforcement)
- **Go workload translator** — YAML-driven operation catalog translates domain events to SQL
- **Community influence** — Independent Cascade model for social network propagation
- **Deterministic simulation** — Same seed = same event stream, fully reproducible
- **CI guardrails** — Automated architectural invariant enforcement

## Architecture

The simulation and database are separated by a bidirectional domain boundary — the Workload Translator. Agents never see SQL, rows, or schema. TiDB never sees agent logic.

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            SIMULATION ENGINE                                        │
│                                                                                     │
│   Agent A ──── Ch.2: Inter-Agent Message ────► Agent B's inbox                      │
│      │                (intra-sim, no DB)           │                                │
│      │                                             │                                │
│      ▼                                             ▼                                │
│   Ch.1: Action Events                          Ch.1: Action Events                  │
│   (writes to OWN tenant)                       (writes to OWN tenant)               │
│      │                                             │                                │
│   Ch.3: Query Requests                         Ch.3: Query Requests                 │
│   (reads from OWN tenant)                      (reads from OWN tenant)              │
│      │         ▲                                   │         ▲                      │
│└──────┼─────────┼───────────────────────────────────┼─────────┼──────────────────────┘
       │         │                                   │         │
       ▼         │ domain answers                    ▼         │ domain answers
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                          WORKLOAD TRANSLATOR                                         │
│     schema, tenant mapping, query templates, result reduction, connection mgmt       │
└──────────────────┬──────────────────────────────────────────────┬────────────────────┘
                   │ SQL                                          │ SQL
                   ▼                                              ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                                  TiDB                                                │
└──────────────────┴──────────────────────────────────────────────┴────────────────────┘
```

### Three Channels

| Channel | Direction | What flows | Touches DB? |
|---------|-----------|------------|-------------|
| Ch.1: Action Events | Agent → Translator → DB | Domain events (order_accepted, shipment_created) | Yes |
| Ch.2: Inter-Agent Messages | Agent → Agent (via inbox) | Domain requests (PlaceOrder, ShipRequest) | No |
| Ch.3: Query Requests | Agent → Translator → DB → Agent | Domain questions + reduced answers | Yes |

### Agent Types

| Agent | Intelligence | Role |
|-------|-------------|------|
| Consumer | Rule-based + social influence | Purchase funnel (browse → view → cart → purchase) |
| Seller | Hybrid (rules + LLM hook) | Pricing, inventory, order processing |
| Supplier | Rule-based + stochastic | Restock fulfillment, production |
| Transport | Discrete state machine | Shipment lifecycle (pending → in_transit → delivered) |
| Government | Aggregate statistics | Market indicators, economic reporting |

## Quick Start

### Prerequisites
- Python >= 3.10
- Go >= 1.26.1
- uv (recommended) or pip

### Installation
```bash
git clone https://github.com/donghz/bizsim.git
cd bizsim
uv sync --dev          # or: pip install -e ".[dev]"
```

### Run Tests
```bash
# Python tests (56 unit + 1 integration)
pytest

# Go translator tests
cd go-translator && go test ./...
```

### Run a Simulation
```python
from bizsim.engine import TickEngine
from bizsim.agents.consumer import ConsumerAgent
from bizsim.agents.seller import SellerAgent
from bizsim.domain import TenantContext

# Create agents with a shared tenant context
tenant = TenantContext(tenant_id="demo_tenant")

# Initialize engine with agents
agents = [
    ConsumerAgent(agent_id=1, tenant=tenant),
    SellerAgent(agent_id=2, tenant=tenant),
]
engine = TickEngine(agents=agents)

# Run simulation for 100 ticks
for _ in range(100):
    engine.step()
```

## Project Structure

```
bizsim/                      # Python simulation package
  agents/                    # Agent implementations
    _sandbox.py              # Import blocker (P1 enforcement)
    base.py                  # BaseAgent, AgentProtocol
    consumer.py              # Consumer agent
    seller.py                # Seller agent
    supplier.py              # Supplier agent
    transport.py             # Transport agent
    government.py            # Government agent
    runner.py                # Agent execution utilities
  community/
    subsystem.py             # Social influence (Independent Cascade)
  engine.py                  # TickEngine — tick loop orchestration
  domain.py                  # Core types (TenantContext, ActionEvent)
  events.py                  # EventEmitter, QueryRequest, QueryResult
  channels.py                # InterAgentMessage, InboxItem
  product_system.py          # SQLite schema, SKU catalog

go-translator/               # Go workload translator
  operations/                # YAML operation catalog
  pkg/catalog/               # Catalog loading & validation
  pkg/executor/              # SQL execution (only DB access point)
  pkg/handler/               # Agent-facing handler (no DB imports)
  pkg/reducers/              # Result reduction logic

specs/                       # 14 specification files
tests/                       # 57 tests (56 unit + 1 integration)
```

## Architectural Invariants

These invariants are enforced by CI guardrails (.github/workflows/arch-guard.yml):

- **P1**: Agents cannot import sqlite3, sqlalchemy, or any DB library
- **P4**: Agents write only to their own tenant — enforced by TenantContext
- **P9**: Only the Go translator's executor package accesses database/sql
- **Channel isolation**: Go translator never handles Ch.2 inter-agent messages

## Development

```bash
# Linting
ruff check bizsim/ tests/

# Type checking
mypy --strict bizsim/

# All tests
pytest tests/
cd go-translator && go test ./...
```

## Specs

Detailed specifications live in `specs/`:

| File | Content |
|------|---------|
| ARCHITECTURE.md | System design, three channels, tick loop |
| CONTRACTS.md | Python types, protocols, interface contracts |
| AGENT_BASE.md | Detailed lifecycle and scheduling logic |
| GO_TRANSLATOR.md | Go translator, YAML catalog, guardrails |
| MESSAGES.md | Registry of all Channel 2 inter-agent message types |
| EVENTS.md | Registry of all Channel 1 action event types |
| QUERIES.md | Registry of all Channel 3 query templates and result schemas |
| CONSUMER.md | Consumer agent behavior, purchase funnel |
| SELLER.md | Seller agent, pricing, order processing |
| SUPPLIER.md | Supplier production and restock logic |
| TRANSPORT.md | Logistics state machines and shipment tracking |
| GOVERNMENT.md | Aggregation logic and policy intervention rules |
| COMMUNITY.md | Social influence model and network diffusion logic |
| PRODUCT_SYSTEM.md | Catalog structure and SKU management rules |
