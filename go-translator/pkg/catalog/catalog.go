package catalog

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"gopkg.in/yaml.v3"
)

type OpMode string

const (
	OpRead  OpMode = "read"
	OpWrite OpMode = "write"
	OpQuery OpMode = "query"
)

type OperationDef struct {
	Name        string            `yaml:"name"`
	Mode        OpMode            `yaml:"mode"`
	Params      map[string]string `yaml:"params"`
	SQL         string            `yaml:"sql"`
	SQLSequence []string          `yaml:"sql_sequence"`
	ReducerKey  string            `yaml:"reducer"`
	Returns     map[string]string `yaml:"returns"`
}

type EventDef struct {
	Name     string   `yaml:"name"`
	Requires []string `yaml:"requires"`
}

type DomainFile struct {
	Domain     string         `yaml:"domain"`
	Operations []OperationDef `yaml:"operations"`
	Events     []EventDef     `yaml:"events"`
}

type Catalog struct {
	ops       map[string]OperationDef
	events    map[string][]string
	validated bool
}

func New() *Catalog {
	return &Catalog{
		ops:    make(map[string]OperationDef),
		events: make(map[string][]string),
	}
}

func (c *Catalog) LoadFromYAML(paths ...string) error {
	for _, path := range paths {
		matches, err := filepath.Glob(path)
		if err != nil {
			return fmt.Errorf("glob failed: %w", err)
		}
		if len(matches) == 0 {
			matches = []string{path}
		}
		for _, match := range matches {
			data, err := os.ReadFile(match)
			if err != nil {
				return fmt.Errorf("failed to read file %s: %w", match, err)
			}
			var df DomainFile
			if err := yaml.Unmarshal(data, &df); err != nil {
				return fmt.Errorf("failed to unmarshal %s: %w", match, err)
			}
			for _, op := range df.Operations {
				if _, ok := c.ops[op.Name]; ok {
					return fmt.Errorf("duplicate operation name: %s", op.Name)
				}
				c.ops[op.Name] = op
			}
			for _, ev := range df.Events {
				if _, ok := c.events[ev.Name]; ok {
					return fmt.Errorf("duplicate event name: %s", ev.Name)
				}
				c.events[ev.Name] = ev.Requires
			}
		}
	}
	return nil
}

func (c *Catalog) Validate(reducerKeys []string) error {
	reducerMap := make(map[string]bool)
	for _, k := range reducerKeys {
		reducerMap[k] = true
	}

	for name, ops := range c.events {
		for _, opName := range ops {
			if _, ok := c.ops[opName]; !ok {
				return fmt.Errorf("event %s requires unknown operation %s", name, opName)
			}
		}
	}

	for name, op := range c.ops {
		if op.Mode == OpQuery {
			if op.ReducerKey == "" {
				return fmt.Errorf("query operation %s missing reducer", name)
			}
			if !reducerMap[op.ReducerKey] {
				return fmt.Errorf("query operation %s uses unregistered reducer %s", name, op.ReducerKey)
			}
		}
		if op.SQL == "" && len(op.SQLSequence) == 0 {
			return fmt.Errorf("operation %s has no SQL", name)
		}
	}

	c.validated = true
	return nil
}

func (c *Catalog) IsValidated() bool {
	return c.validated
}

func (c *Catalog) GetOp(name string) (OperationDef, bool) {
	op, ok := c.ops[name]
	return op, ok
}

func (c *Catalog) GetEventRequires(name string) ([]string, bool) {
	reqs, ok := c.events[name]
	return reqs, ok
}

func (op OperationDef) Expand(tenantID string, params map[string]any) (string, []any, error) {
	return ExpandSQL(op.SQL, tenantID, params)
}

func (op OperationDef) ExpandSequence(tenantID string, params map[string]any) ([]string, [][]any, error) {
	var queries []string
	var allArgs [][]any
	for _, sql := range op.SQLSequence {
		query, args, err := ExpandSQL(sql, tenantID, params)
		if err != nil {
			return nil, nil, err
		}
		queries = append(queries, query)
		allArgs = append(allArgs, args)
	}
	return queries, allArgs, nil
}

func ExpandSQL(sqlText, tenantID string, params map[string]any) (string, []any, error) {
	query := strings.ReplaceAll(sqlText, "{tenant}", tenantID)

	var args []any
	var result strings.Builder
	runes := []rune(query)
	for i := 0; i < len(runes); i++ {
		if runes[i] == ':' && i+1 < len(runes) && isAlpha(runes[i+1]) {
			j := i + 1
			for j < len(runes) && isAlphaNum(runes[j]) {
				j++
			}
			paramName := string(runes[i+1 : j])
			val, ok := params[paramName]
			if !ok {
				return "", nil, fmt.Errorf("missing parameter: %s", paramName)
			}
			args = append(args, val)
			result.WriteRune('?')
			i = j - 1
		} else {
			result.WriteRune(runes[i])
		}
	}
	return result.String(), args, nil
}

func isAlpha(r rune) bool {
	return (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || r == '_'
}

func isAlphaNum(r rune) bool {
	return isAlpha(r) || (r >= '0' && r <= '9')
}
