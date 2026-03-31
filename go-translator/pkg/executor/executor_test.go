package executor

import (
	"context"
	"github.com/DATA-DOG/go-sqlmock"
	"github.com/bizsim/go-translator/pkg/catalog"
	"github.com/bizsim/go-translator/pkg/reducers"
	"testing"
)

func TestExecutorExecute(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("failed to open mock db: %v", err)
	}
	defer db.Close()

	cat := catalog.New()
	err = cat.LoadFromYAML("../../operations/store.yaml")
	if err != nil {
		t.Fatalf("load failed: %v", err)
	}

	reds := reducers.GetStandardReducers()
	redKeys := make([]string, 0, len(reds))
	for k := range reds {
		redKeys = append(redKeys, k)
	}

	if err := cat.Validate(redKeys); err != nil {
		t.Fatalf("validate failed: %v", err)
	}

	ex, err := NewExecutor(db, cat, reds)
	if err != nil {
		t.Fatalf("new executor failed: %v", err)
	}

	scope := NewTenantScope("tenant1")
	params := map[string]any{"sku_id": 1}

	// Test Read
	rows := sqlmock.NewRows([]string{"qty"}).AddRow(10)
	mock.ExpectQuery("SELECT qty FROM tenant1.inventory WHERE sku_id = \\?").WithArgs(1).WillReturnRows(rows)

	res, err := ex.Execute(context.Background(), scope, "check_inventory", params)
	if err != nil {
		t.Fatalf("execute read failed: %v", err)
	}

	items := res.Data.([]map[string]any)
	if len(items) != 1 || items[0]["qty"] != int64(10) {
		t.Errorf("unexpected result: %v", res.Data)
	}

	// Test Write
	mock.ExpectExec("INSERT INTO tenant1.store_orders").WillReturnResult(sqlmock.NewResult(1, 1))
	_, err = ex.Execute(context.Background(), scope, "insert_store_order", map[string]any{
		"order_request_id": "ord1",
		"sku_id":           1,
		"qty":              5,
		"price":            10.5,
		"consumer_id":      1,
		"status":           "accepted",
	})
	if err != nil {
		t.Fatalf("execute write failed: %v", err)
	}

	// Test Query
	rows = sqlmock.NewRows([]string{"qty_available"}).AddRow(20)
	mock.ExpectQuery("SELECT qty as qty_available FROM tenant1.inventory WHERE sku_id = \\?").WillReturnRows(rows)
	res, err = ex.Execute(context.Background(), scope, "inventory_check", map[string]any{"seller_id": 1, "sku_id": 1})
	if err != nil {
		t.Fatalf("execute query failed: %v", err)
	}
	data := res.Data.(map[string]any)
	if data["qty_available"] != int64(20) {
		t.Errorf("expected 20, got %v", data["qty_available"])
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("expectations not met: %v", err)
	}
}
