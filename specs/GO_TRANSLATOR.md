# Go Workload Translator — Operation Catalog & Guardrails

> Extracted from: vision.md P9 (lines 928–1085), G1 (lines 1109–1199), G2 (lines 1204–1249), G3 (lines 1252–1299)

## The Coherence Problem

The Go translator unifies three previously implicit registries into a single, explicit operation catalog. Every named operation with typed parameters—whether used for correlated reads, standalone writes, or async analytical queries—is defined here.

Prior to this unification, event types, read/write patterns, and query templates lived in separate namespaces. This created hidden coupling where an event might require a pattern that wasn't registered, leading to runtime errors. P9 solves this by making every operation a first-class entry in a unified catalog.

## Unified Operation Definition

Every operation is an entry in a YAML file. The `events.requires` declaration ensures that all patterns needed by an event type exist at startup.

```yaml
# operations/store.yaml
domain: store
operations:
  # Sync patterns (used inside Mode 1 action events)
  - name: check_inventory
    mode: read
    params: { product_id: int }
    sql: "SELECT qty FROM {tenant}.inventory WHERE product_id = :product_id"
    returns: { qty: int }

  - name: insert_store_order
    mode: write
    params: { order_request_id: string, product_id: int, qty: int, price: decimal }
    sql: "INSERT INTO {tenant}.store_orders (order_request_id, product_id, qty, price) VALUES (:order_request_id, :product_id, :qty, :price)"

  - name: update_inventory
    mode: write
    params: { product_id: int, qty_delta: int }
    sql: "UPDATE {tenant}.inventory SET qty = qty + :qty_delta WHERE product_id = :product_id"

  # Async query templates (Mode 2 — same catalog, different execution mode)
  - name: sales_analytics
    mode: query
    params: { seller_id: int, window: duration }
    sql: |
      SELECT product_id, SUM(qty), SUM(revenue)
      FROM {tenant}.store_orders
      WHERE seller_id = :seller_id AND created_at > NOW() - :window
      GROUP BY product_id ORDER BY revenue DESC
    reducer: aggregation_summary
    returns: { revenue: decimal, top_products: list, trend: string }

# Event compositions — make implicit coupling explicit
events:
  - name: store_accept_order
    requires: [check_inventory, insert_store_order, update_inventory]
  - name: seller_reprices
    requires: [update_store_pricing]
```

## Event Compositions

The `events.requires` declaration turns hidden coupling into **startup-time validation**. When the Go translator boots, `Catalog.Validate()` checks that:
- Every event type's required patterns exist in the catalog.
- Every query-mode operation has a registered reducer.
- Every parameter type is valid.

## Domain-Partitioned Files

Operations are split into domain-specific YAML files within the `operations/` directory. Adding a new agent type only requires a new YAML file and schema migration, with no Go code changes needed for standard behaviors.

- `operations/store.yaml`: `check_inventory`, `insert_store_order`, `sales_analytics`
- `operations/consumer.yaml`: `insert_consumer_order`, `order_history`
- `operations/logistics.yaml`: `insert_shipment`, `shipment_tracking`
- `operations/payment.yaml`: `insert_transaction`
- `operations/government.yaml`: `insert_gov_record`, `gov_economic_indicators`
- `operations/supplier.yaml`: `update_capacity`, `fulfillment_overdue`

## Go Types

The Go implementation uses a single definition type for all operations.

```go
// One definition type for all operations
type OperationDef struct {
    Name       string            `yaml:"name"`
    Mode       OpMode            `yaml:"mode"`        // read | write | query
    Params     map[string]string `yaml:"params"`       // name -> type (validated at startup)
    SQL        string            `yaml:"sql"`          // single-statement
    SQLSeq     []string          `yaml:"sql_sequence"` // multi-statement (transactional writes)
    ReducerKey string            `yaml:"reducer"`      // query mode only
    Returns    map[string]string `yaml:"returns"`      // documentation + validation
}

type OpMode string
const (
    OpRead  OpMode = "read"
    OpWrite OpMode = "write"
    OpQuery OpMode = "query"
)

// The catalog: loaded once at startup from YAML files
type Catalog struct {
    ops      map[string]OperationDef  // "check_inventory" -> def
    events   map[string][]string      // "store_accept_order" -> [required op names]
    reducers map[string]ReducerFunc   // "aggregation_summary" -> func
}

// ReducerFunc: escape hatch for custom aggregation logic
type ReducerFunc func(rows *sql.Rows) (map[string]any, error)
```

## Catalog API

The `Catalog` type provides the following methods for lifecycle management:
- `LoadFromYAML(paths ...string) error`: Loads domain definitions from the `operations/` directory.
- `RegisterReducer(name string, fn ReducerFunc)`: Registers custom Go logic for complex aggregations.
- `Validate() error`: Performs a full consistency check of all operations and event requirements. Must pass before the executor can start.

## Standard Reducer Library

Standard reducers cover the vast majority of query template requirements.

| Reducer | Input | Output | Used by |
|---------|-------|--------|---------|
| `single_row` | 1 row, N columns | `map[string]any` | shipment_tracking, fulfillment_overdue |
| `list_with_count` | N rows | `{items: [...], count: int}` | order_history |
| `aggregation_summary` | GROUP BY result | `{metrics: {...}, top_N: [...]}` | sales_analytics, gov_economic_indicators |
| `passthrough` | raw rows | `[]map[string]any` | debugging / ad-hoc |

## What Requires Go Code vs What Doesn't

| Change | Go code required? |
|--------|-------------------|
| New read/write pattern (simple SQL) | No — YAML only |
| New query template with existing reducer shape | No — YAML only |
| New event type composing existing patterns | No — YAML only |
| New reducer with custom aggregation logic | Yes — register a `ReducerFunc` |
| New tenant routing strategy | Yes — register a `RouterFunc` |

## Boundary Conditions

- **No conditional logic in the catalog.** Logic belongs in the Python agent. The catalog is purely declarative.
- **No cross-tenant operations.** SQL uses `{tenant}` as a single schema prefix. Cross-tenant writes are forbidden.
- **SQL injection prevention.** Structural expansion for `{tenant}` is restricted to the internal registry. All other values must use parameterized queries (`:param` → `?`).

## Guardrails Section

Structural enforcement ensures that architectural principles are physically impossible to violate or caught at compile/startup time.

### G1: P1 Boundary — Agents Cannot Touch SQL

Python agents only emit named events. No agent code ever sees SQL.

**Python — Import Firewall (Tier S)**:
The runner installs an import blocker before loading any agent modules.

```python
# bizsim/agents/_sandbox.py
import sys, importlib.abc

_BLOCKED_MODULES = frozenset({
    "sqlalchemy", "sqlite3", "psycopg2", "pymysql",
    "mysql.connector", "bizsim.translator", "bizsim.db", "subprocess",
})

class _ImportBlocker(importlib.abc.MetaPathFinder):
    def find_module(self, fullname, path=None):
        for blocked in _BLOCKED_MODULES:
            if fullname == blocked or fullname.startswith(blocked + "."):
                return self
    def load_module(self, fullname):
        raise ImportError(
            f"P1 VIOLATION: agents cannot import '{fullname}'. "
            f"Emit a named event instead."
        )

def activate():
    sys.meta_path.insert(0, _ImportBlocker())
```

**Python — SQL-Unrepresentable Event Type (Tier A)**:
The `Event` dataclass rejects parameters containing SQL keywords.

```python
# bizsim/events.py
@dataclass(frozen=True)
class Event:
    event_type: str
    tenant_id: str
    params: dict[str, int | float | str | bool]  # scalar values only

    def __post_init__(self):
        SQL_KEYWORDS = {"SELECT ", "INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER "}
        for v in self.params.values():
            if isinstance(v, str) and any(kw in v.upper() for kw in SQL_KEYWORDS):
                raise ValueError(f"P1 VIOLATION: SQL-like string in event params: {v!r}")
```

**Go — `*sql.DB` is Unexported (Tier A)**:
The `handler` package cannot import `database/sql` and has no access to the raw DB connection.

**CI Checks (Tier B)**:
Grep checks prevent SQL imports in agent code and verify sandbox integrity.

```yaml
# .github/workflows/arch-guard.yml
- name: P1 — No SQL import in agent code
  run: |
    VIOLATIONS=$(grep -rn 'import.*\(sqlalchemy\|sqlite3\|psycopg2\|pymysql\)' \
      bizsim/agents/ --include='*.py' || true)
    [ -z "$VIOLATIONS" ] || { echo "P1 VIOLATION: $VIOLATIONS"; exit 1; }

- name: P1 — Sandbox integrity check
  run: |
    python -c "
    import ast, sys
    src = open('bizsim/agents/_sandbox.py').read()
    tree = ast.parse(src)
    required = {'sqlalchemy', 'sqlite3', 'psycopg2', 'pymysql', 'bizsim.translator'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'frozenset':
            found = {e.value for e in node.args[0].elts if isinstance(e, ast.Constant)}
            missing = required - found
            if missing: sys.exit(f'SANDBOX TAMPERED: missing: {missing}')
    "
```

### G2: P4 Tenant Sovereignty — No Cross-Tenant Writes

Agents must only write to their own tenant's tables.

**Go — Unforgeable `TenantScope` Capability Token (Tier S)**:
`TenantScope` is an opaque token that cannot be constructed outside `pkg/executor`.

```go
// pkg/executor/tenant.go
type TenantScope struct {
    tenantID string  // unexported
}

func newTenantScope(id string) TenantScope { return TenantScope{tenantID: id} }

// executor ignores tenant_id in params and uses scope
func (e *Executor) Execute(ctx context.Context, scope TenantScope, op string, params map[string]any) (Result, error) {
    params["tenant_id"] = scope.tenantID  // overwrite unconditionally
    // ...
}
```

**Python — EventEmitter with Baked-in Tenant (Tier A)**:
Agents receive a pre-bound `EventEmitter` where the tenant is immutable.

```python
# bizsim/domain.py
class EventEmitter:
    def __init__(self, tenant: TenantContext):
        self._tenant = tenant

    def emit(self, event_type: str, params: dict) -> Event:
        return Event(event_type=event_type, tenant_id=self._tenant.tenant_id, params=params)
```

### G3: P9 Operation Catalog — No Ad-Hoc SQL in Go

All SQL must live in the YAML catalog.

**Go Package Layout (Tier A)**:
`handler/` cannot execute SQL directly; it must go through `executor.Execute()`. The raw execution method `run()` is unexported.

```go
// pkg/executor/executor.go
type Executor struct {
    db      *sql.DB          // unexported
    catalog *catalog.Catalog // unexported
}

func (e *Executor) run(ctx context.Context, def catalog.OperationDef, params map[string]any) (Result, error) {
    query, args := def.Expand(params)  // SQL comes from YAML
    rows, err := e.db.QueryContext(ctx, query, args...)
    // ...
}
```

**`NewExecutor` Requires Validated Catalog (Tier A)**:
An `Executor` cannot be constructed with an unvalidated catalog.

```go
// pkg/catalog/catalog.go
type Catalog struct {
    ops       map[string]OperationDef
    events    map[string]bool
    validated bool  // only Validate() sets this
}

// pkg/executor/executor.go
func NewExecutor(db *sql.DB, cat *catalog.Catalog) (*Executor, error) {
    if !cat.IsValidated() {
        return nil, errors.New("P9: catalog must be validated before use")
    }
    return &Executor{db: db, catalog: cat}, nil
}
```

## Enforcement Tier Hierarchy

| Tier | Mechanism | Cannot be bypassed by editing... |
|------|-----------|----------------------------------|
| **S — Physically impossible** | Go unexported fields/types, Python import blocker | Single file (requires coordinated multi-file edits) |
| **A — Compile/startup time** | `NewExecutor` requires validated catalog; Go package layout blocks `database/sql` import | Application logic (type system rejects it) |
| **B — CI (external)** | grep checks in CI pipeline | Anything — CI is outside agent's edit scope |
| **C — Test floor** | CI enforces minimum test counts | Any single test file |
| **D — Tests** | Unit + integration tests | Test files |

## Cross-References

- [ARCHITECTURE.md](ARCHITECTURE.md) — For channel definitions and Mode 1 vs Mode 2 details.
- [CONTRACTS.md](CONTRACTS.md) — For Python interface contracts and sandbox implementation.
- [EVENTS.md](EVENTS.md) — For event type definitions and Mode 1 payload structure.
