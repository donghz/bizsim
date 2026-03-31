package catalog

import (
	"testing"
)

func TestCatalogLoadAndValidate(t *testing.T) {
	cat := New()
	err := cat.LoadFromYAML("../../operations/*.yaml")
	if err != nil {
		t.Fatalf("failed to load operations: %v", err)
	}

	reducers := []string{"single_row", "list_with_count", "aggregation_summary", "passthrough"}
	err = cat.Validate(reducers)
	if err != nil {
		t.Fatalf("validation failed: %v", err)
	}

	if !cat.IsValidated() {
		t.Error("expected catalog to be validated")
	}

	op, ok := cat.GetOp("check_inventory")
	if !ok {
		t.Error("expected check_inventory operation to exist")
	}
	if op.Mode != OpRead {
		t.Errorf("expected OpRead mode, got %s", op.Mode)
	}

	reqs, ok := cat.GetEventRequires("store_order_accepted")
	if !ok {
		t.Error("expected store_order_accepted event to exist")
	}
	if len(reqs) != 3 {
		t.Errorf("expected 3 requirements, got %d", len(reqs))
	}
}

func TestExpandSQL(t *testing.T) {
	sql := "SELECT * FROM {tenant}.table WHERE id = :id AND type = :type"
	params := map[string]any{"id": 123, "type": "test"}
	tenant := "t1"

	query, args, err := ExpandSQL(sql, tenant, params)
	if err != nil {
		t.Fatalf("expand failed: %v", err)
	}

	expectedQuery := "SELECT * FROM t1.table WHERE id = ? AND type = ?"
	if query != expectedQuery {
		t.Errorf("expected query %s, got %s", expectedQuery, query)
	}

	if len(args) != 2 {
		t.Fatalf("expected 2 args, got %d", len(args))
	}
	if args[0] != 123 || args[1] != "test" {
		t.Errorf("unexpected args: %v", args)
	}
}
