package handler

import (
	"context"
	"github.com/DATA-DOG/go-sqlmock"
	"github.com/bizsim/go-translator/pkg/catalog"
	"github.com/bizsim/go-translator/pkg/executor"
	"github.com/bizsim/go-translator/pkg/reducers"
	"testing"
)

func TestHandler(t *testing.T) {
	db, mock, _ := sqlmock.New()
	defer db.Close()

	cat := catalog.New()
	cat.LoadFromYAML("../../operations/store.yaml")
	reds := reducers.GetStandardReducers()
	redKeys := make([]string, 0, len(reds))
	for k := range reds {
		redKeys = append(redKeys, k)
	}
	cat.Validate(redKeys)
	ex, _ := executor.NewExecutor(db, cat, reds)
	h := New(ex)

	// ActionEvent Test
	mock.ExpectQuery("SELECT qty FROM t1.inventory WHERE sku_id = \\?").WithArgs(1).WillReturnRows(sqlmock.NewRows([]string{"qty"}).AddRow(10))
	mock.ExpectExec("UPDATE t1.inventory SET qty = qty \\+ \\?").WithArgs(-5, 1).WillReturnResult(sqlmock.NewResult(1, 1))
	mock.ExpectExec("INSERT INTO t1.store_orders").WillReturnResult(sqlmock.NewResult(1, 1))

	err := h.HandleActionEvent(context.Background(), ActionEvent{
		EventType: "store_order_accepted",
		TenantID:  "t1",
		Writes: []OpPattern{
			{Pattern: "update_inventory", Params: map[string]any{"sku_id": 1, "qty_delta": -5}},
			{Pattern: "insert_store_order", Params: map[string]any{"order_request_id": "o1", "sku_id": 1, "qty": 5, "price": 10.0, "consumer_id": 1, "status": "accepted"}},
		},
		Reads: []OpPattern{
			{Pattern: "check_inventory", Params: map[string]any{"sku_id": 1}},
		},
	})
	if err != nil {
		t.Fatalf("HandleActionEvent failed: %v", err)
	}

	// QueryRequest Test
	mock.ExpectQuery("SELECT qty as qty_available FROM t1.inventory").WillReturnRows(sqlmock.NewRows([]string{"qty_available"}).AddRow(20))
	res, err := h.HandleQueryRequest(context.Background(), "t1", QueryRequest{
		QueryID:       "q1",
		QueryTemplate: "inventory_check",
		Params:        map[string]any{"seller_id": 1, "sku_id": 1},
	})
	if err != nil {
		t.Fatalf("HandleQueryRequest failed: %v", err)
	}
	data := res.Data.(map[string]any)
	if data["qty_available"] != int64(20) {
		t.Errorf("expected 20, got %v", data["qty_available"])
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Errorf("expectations not met: %v", err)
	}
}
