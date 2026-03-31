package handler

import (
	"context"
	"fmt"
	"github.com/bizsim/go-translator/pkg/executor"
)

type ActionEvent struct {
	EventID   string      `json:"event_id"`
	EventType string      `json:"event_type"`
	AgentID   int         `json:"agent_id"`
	TenantID  string      `json:"tenant_id"`
	Tick      int         `json:"tick"`
	Reads     []OpPattern `json:"reads"`
	Writes    []OpPattern `json:"writes"`
}

type OpPattern struct {
	Pattern string         `json:"pattern"`
	Params  map[string]any `json:"params"`
}

type QueryRequest struct {
	QueryID       string         `json:"query_id"`
	AgentID       int            `json:"agent_id"`
	QueryTemplate string         `json:"query_template"`
	Params        map[string]any `json:"params"`
	TickIssued    int            `json:"tick_issued"`
}

type QueryResult struct {
	QueryID       string `json:"query_id"`
	AgentID       int    `json:"agent_id"`
	QueryTemplate string `json:"query_template"`
	TickIssued    int    `json:"tick_issued"`
	TickAvailable int    `json:"tick_available"`
	Data          any    `json:"data"`
}

type Handler struct {
	executor *executor.Executor
}

func New(ex *executor.Executor) *Handler {
	return &Handler{executor: ex}
}

func (h *Handler) HandleActionEvent(ctx context.Context, ev ActionEvent) error {
	scope := executor.NewTenantScope(ev.TenantID)

	for _, p := range ev.Reads {
		if _, err := h.executor.Execute(ctx, scope, p.Pattern, p.Params); err != nil {
			return fmt.Errorf("read %s failed: %w", p.Pattern, err)
		}
	}

	for _, p := range ev.Writes {
		if _, err := h.executor.Execute(ctx, scope, p.Pattern, p.Params); err != nil {
			return fmt.Errorf("write %s failed: %w", p.Pattern, err)
		}
	}

	return nil
}

func (h *Handler) HandleQueryRequest(ctx context.Context, tenantID string, req QueryRequest) (QueryResult, error) {
	scope := executor.NewTenantScope(tenantID)

	if _, ok := req.Params["current_tick"]; !ok {
		req.Params["current_tick"] = req.TickIssued
	}

	res, err := h.executor.Execute(ctx, scope, req.QueryTemplate, req.Params)
	if err != nil {
		return QueryResult{}, err
	}

	return QueryResult{
		QueryID:       req.QueryID,
		AgentID:       req.AgentID,
		QueryTemplate: req.QueryTemplate,
		TickIssued:    req.TickIssued,
		TickAvailable: req.TickIssued + 1,
		Data:          res.Data,
	}, nil
}
