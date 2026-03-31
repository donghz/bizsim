# Agent Sandbox — Runtime Import Blocker

The sandbox is a **runtime import blocker** that enforces BizSim's most critical architectural rule: **P1 — agents must never directly access databases, networks, or the operating system.**

## Implementation

**File**: `bizsim/agents/_sandbox.py`

The sandbox uses two layers of defense, both activated by `install_sandbox()`:

### Layer 1: `SandboxFinder` (sys.meta_path hook)

Inserted at the front of `sys.meta_path`, which is where Python looks up modules during import. When any code tries to `import sqlite3` (or any forbidden module), Python asks the finder first. The sandbox finder raises `SandboxImportError` before Python even loads the module.

```python
class SandboxFinder:
    def find_spec(self, fullname, path, target=None):
        root_module = fullname.split(".")[0]
        if root_module in FORBIDDEN_MODULES:
            raise SandboxImportError(...)
        return None
```

### Layer 2: `_guarded_import` (builtins.__import__ wrapper)

Replaces `builtins.__import__` itself. This catches the case where a module is **already cached** in `sys.modules` (e.g., `sqlite3` is a C extension that gets pre-loaded). The `meta_path` hook only fires for fresh lookups, so without this second layer, a cached module would slip through.

```python
_original_import = builtins.__import__

def _guarded_import(name, *args, **kwargs):
    if _sandbox_active:
        root_module = name.split(".")[0]
        if root_module in FORBIDDEN_MODULES:
            raise SandboxImportError(...)
    return _original_import(name, *args, **kwargs)
```

### Why Two Layers?

During development, we discovered that `sqlite3` is a built-in C extension that gets cached in `sys.modules` before the sandbox activates. The `meta_path` hook never fires for cached modules, so `import sqlite3` would succeed silently. The `builtins.__import__` wrapper was added as a second interception point to close this gap.

## Blocked Modules

The 11 forbidden modules fall into three categories:

| Category | Modules | Why Blocked |
|----------|---------|-------------|
| **Database access** | `sqlite3`, `sqlalchemy`, `psycopg2`, `mysql` | Agents must emit domain events, not write SQL — the Go translator handles all DB access |
| **Network access** | `requests`, `urllib`, `http.client`, `smtplib`, `socket` | Agents cannot make external calls — all communication goes through Ch.1/2/3 channels |
| **OS access** | `os`, `subprocess` | Agents cannot touch the filesystem or spawn processes |

## Architectural Purpose

The core architectural insight of BizSim is that **agents think in domain concepts** (place order, ship item, check inventory) while **the Go translator thinks in SQL**. The sandbox enforces this separation at runtime — if an agent tries to `import sqlite3` and run its own query, it gets a `SandboxImportError` immediately, rather than silently violating the architecture.

## Enforcement Layers

The sandbox is one of three enforcement mechanisms for P1:

| Layer | Mechanism | When It Catches Violations |
|-------|-----------|---------------------------|
| **Runtime** | `_sandbox.py` (this file) | During execution — raises `SandboxImportError` |
| **Static analysis** | `.github/workflows/arch-guard.yml` (G1) | At CI time — grep for forbidden import statements |
| **Code review** | `AGENTS.md` knowledge base | During development — documents the invariant for AI and human developers |

## Usage

The sandbox is activated once at engine startup:

```python
from bizsim.agents._sandbox import install_sandbox

install_sandbox()  # Call once before running any agents
```

After activation, any agent code that attempts a forbidden import will raise:

```
SandboxImportError: Import of forbidden module 'sqlite3' is blocked in agent sandbox
```
