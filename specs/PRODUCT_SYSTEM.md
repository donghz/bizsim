# Product System & Common Knowledge

> Extracted from: agent-behavior.md §2 (lines 104–219)

## Design Overview

The Product System is a **global, read-only SQLite database** loaded into simulation memory at startup. It serves as shared reference data ("common knowledge") that all agents can query in-process. It does NOT go through the Go translator, does NOT generate TiDB workload, and does NOT cross the IPC boundary.

```
┌───────────────────────────────────────────────────────┐
│                 Simulation Process                    │
│                                                       │
│  ┌───────────────────────────────────┐                │
│  │   Product System (SQLite, r/o)    │                │
│  │                                   │                │
│  │  ┌─────────────┐ ┌──────────────┐ │                │
│  │  │ SKU Catalog │ │ Parts / BOM  │ │                │
│  │  └─────────────┘ └──────────────┘ │                │
│  └──────────┬────────────────────────┘                │
│             │ in-process queries                      │
│     ┌───────┼───────┬──────────┬──────────┐           │
│     ▼       ▼       ▼          ▼          ▼           │
│  Consumer  Seller  Supplier  Transport  Government    │
│                                                       │
│  (agents read SKU names, categories, seller mappings, │
│   BOM data — zero DB cost, zero IPC cost)             │
└───────────────────────────────────────────────────────┘
```

## SKU Catalog Schema

```sql
CREATE TABLE sku_catalog (
    sku_id        INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,           -- "Wireless Earbuds Pro X1"
    category      TEXT NOT NULL,           -- "Electronics > Audio > Earbuds"
    subcategory   TEXT,                    -- "True Wireless"
    base_price    REAL NOT NULL,           -- 49.99 (reference price, sellers set actual)
    price_floor   REAL NOT NULL,           -- 25.00 (minimum allowed price)
    price_ceiling REAL NOT NULL,           -- 99.99 (maximum allowed price)
    weight_kg     REAL,                    -- 0.15
    brand         TEXT,                    -- "AudioTech"
    tags          TEXT,                    -- JSON array: ["trending", "gift", "portable"]
    created_tick  INTEGER DEFAULT 0
);

CREATE TABLE sku_seller_mapping (
    sku_id     INTEGER NOT NULL REFERENCES sku_catalog(sku_id),
    seller_id  INTEGER NOT NULL,
    is_primary BOOLEAN DEFAULT FALSE,     -- primary seller for this SKU
    PRIMARY KEY (sku_id, seller_id)
);

CREATE TABLE sku_supplier_mapping (
    sku_id      INTEGER NOT NULL REFERENCES sku_catalog(sku_id),
    supplier_id INTEGER NOT NULL,
    part_id     INTEGER REFERENCES parts(part_id),  -- which part this supplier provides for this SKU
    is_primary  BOOLEAN DEFAULT FALSE,
    lead_time_ticks INTEGER DEFAULT 10,              -- expected delivery time
    PRIMARY KEY (sku_id, supplier_id)
);

CREATE INDEX idx_sku_category ON sku_catalog(category);
CREATE INDEX idx_sku_seller ON sku_seller_mapping(seller_id);
CREATE INDEX idx_sku_supplier ON sku_supplier_mapping(supplier_id);
```

## Usage Patterns

- Consumer `browse_catalog`: `SELECT sku_id, name, base_price FROM sku_catalog WHERE category = ? ORDER BY RANDOM() LIMIT 20`
- Consumer `pick_seller`: `SELECT s.seller_id, s.is_primary FROM sku_seller_mapping s WHERE s.sku_id = ? ORDER BY RANDOM() LIMIT 1`
  (V1: random selection. V2: weighted by price/reviews)
- Seller `get_my_skus`: `SELECT sku_id FROM sku_seller_mapping WHERE seller_id = ?`
- Seller LLM context: `SELECT name, base_price, price_floor, price_ceiling FROM sku_catalog WHERE sku_id IN (?)`

## Parts / BOM Schema

Provides common terminology across the supply chain. Reference-only in V1 (no production constraints).

```sql
CREATE TABLE parts (
    part_id    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,              -- "Lithium Polymer Battery 500mAh"
    category   TEXT NOT NULL,              -- "Electronics > Batteries"
    unit_cost  REAL                        -- reference cost per unit
);

CREATE TABLE bill_of_materials (
    bom_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id     INTEGER NOT NULL REFERENCES sku_catalog(sku_id),
    part_id    INTEGER NOT NULL REFERENCES parts(part_id),
    qty        INTEGER NOT NULL DEFAULT 1, -- how many of this part per SKU
    layer      INTEGER NOT NULL DEFAULT 0  -- 0=raw, 1=component, 2=assembly, 3=finished
);

CREATE INDEX idx_bom_sku ON bill_of_materials(sku_id);
CREATE INDEX idx_bom_part ON bill_of_materials(part_id);
```

**V1 usage**: Sellers and Suppliers can look up "what parts are needed for SKU X" and "what SKUs use part Y" for terminology alignment and LLM context enrichment. No actual production constraint enforcement.

## Initialization

The SQLite database is generated once from a configuration seed file (YAML or JSON) and loaded at simulation start:

```yaml
# products_seed.yaml
categories:
  - name: "Electronics > Audio > Earbuds"
    sku_count: 50
    price_range: [20, 150]
    sellers_per_sku: [1, 5]    # uniform random range
  - name: "Apparel > Shoes > Running"
    sku_count: 100
    price_range: [40, 300]
    sellers_per_sku: [2, 8]
# ... generates ~1000-10000 SKUs total
```
