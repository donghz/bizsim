package executor

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"github.com/bizsim/go-translator/pkg/catalog"
	"github.com/bizsim/go-translator/pkg/reducers"
)

type TenantScope struct {
	tenantID string
}

func NewTenantScope(id string) TenantScope {
	return TenantScope{tenantID: id}
}

type Result struct {
	Data any
}

type Executor struct {
	db       *sql.DB
	catalog  *catalog.Catalog
	reducers map[string]reducers.ReducerFunc
}

func NewExecutor(db *sql.DB, cat *catalog.Catalog, red map[string]reducers.ReducerFunc) (*Executor, error) {
	if !cat.IsValidated() {
		return nil, errors.New("P9: catalog must be validated before use")
	}
	return &Executor{
		db:       db,
		catalog:  cat,
		reducers: red,
	}, nil
}

func (e *Executor) Execute(ctx context.Context, scope TenantScope, opName string, params map[string]any) (Result, error) {
	def, ok := e.catalog.GetOp(opName)
	if !ok {
		return Result{}, fmt.Errorf("unknown operation: %s", opName)
	}

	switch def.Mode {
	case catalog.OpRead, catalog.OpQuery:
		query, args, err := def.Expand(scope.tenantID, params)
		if err != nil {
			return Result{}, err
		}
		rows, err := e.db.QueryContext(ctx, query, args...)
		if err != nil {
			return Result{}, err
		}
		defer rows.Close()

		if def.Mode == catalog.OpQuery {
			reducer := e.reducers[def.ReducerKey]
			data, err := reducer(rows)
			return Result{Data: data}, err
		}

		var items []map[string]any
		for rows.Next() {
			row, err := scanRowToMap(rows)
			if err != nil {
				return Result{}, err
			}
			items = append(items, row)
		}
		return Result{Data: items}, nil

	case catalog.OpWrite:
		if len(def.SQLSequence) > 0 {
			queries, allArgs, err := def.ExpandSequence(scope.tenantID, params)
			if err != nil {
				return Result{}, err
			}
			tx, err := e.db.BeginTx(ctx, nil)
			if err != nil {
				return Result{}, err
			}
			for i, q := range queries {
				if _, err := tx.ExecContext(ctx, q, allArgs[i]...); err != nil {
					tx.Rollback()
					return Result{}, err
				}
			}
			return Result{}, tx.Commit()
		} else {
			query, args, err := def.Expand(scope.tenantID, params)
			if err != nil {
				return Result{}, err
			}
			_, err = e.db.ExecContext(ctx, query, args...)
			return Result{}, err
		}

	default:
		return Result{}, fmt.Errorf("unsupported mode: %s", def.Mode)
	}
}

func scanRowToMap(rows *sql.Rows) (map[string]any, error) {
	cols, err := rows.Columns()
	if err != nil {
		return nil, err
	}
	values := make([]any, len(cols))
	valuePtrs := make([]any, len(cols))
	for i := range values {
		valuePtrs[i] = &values[i]
	}

	if err := rows.Scan(valuePtrs...); err != nil {
		return nil, err
	}

	row := make(map[string]any)
	for i, col := range cols {
		val := values[i]
		if b, ok := val.([]byte); ok {
			val = string(b)
		}
		row[col] = val
	}
	return row, nil
}
