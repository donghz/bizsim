package reducers

import (
	"database/sql"
)

type ReducerFunc func(rows *sql.Rows) (any, error)

func GetStandardReducers() map[string]ReducerFunc {
	return map[string]ReducerFunc{
		"single_row":          SingleRow,
		"list_with_count":     ListWithCount,
		"aggregation_summary": AggregationSummary,
		"passthrough":         Passthrough,
	}
}

func SingleRow(rows *sql.Rows) (any, error) {
	if !rows.Next() {
		return nil, nil
	}
	return scanRowToMap(rows)
}

func ListWithCount(rows *sql.Rows) (any, error) {
	var items []map[string]any
	for rows.Next() {
		row, err := scanRowToMap(rows)
		if err != nil {
			return nil, err
		}
		items = append(items, row)
	}
	return map[string]any{
		"items": items,
		"count": len(items),
	}, nil
}

func AggregationSummary(rows *sql.Rows) (any, error) {
	var items []map[string]any
	for rows.Next() {
		row, err := scanRowToMap(rows)
		if err != nil {
			return nil, err
		}
		items = append(items, row)
	}
	return map[string]any{
		"results": items,
	}, nil
}

func Passthrough(rows *sql.Rows) (any, error) {
	var items []map[string]any
	for rows.Next() {
		row, err := scanRowToMap(rows)
		if err != nil {
			return nil, err
		}
		items = append(items, row)
	}
	return items, nil
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
