package main

// The agent loop.
//
// Send the messages to the model, run the tool calls it asks for,
// add the results, and repeat until the model stops or a limit is hit.

import (
	"encoding/json"
	"fmt"
	"math"
	"time"

	"barebones/harness/tools"
)

const (
	maxMalformed = 3
	// The smallest HTTP timeout for one model call, in seconds.
	minCallSeconds = 1.0
)

// Transcript records. The fields are in the order of the spec, section 10.
type textRecord struct {
	Type    string `json:"type"`
	Content string `json:"content"`
}

type assistantRecord struct {
	Type      string           `json:"type"`
	Content   json.RawMessage  `json:"content"`
	Thinking  json.RawMessage  `json:"thinking,omitempty"`
	ToolCalls []toolCallRecord `json:"tool_calls,omitempty"`
}

type toolCallRecord struct {
	ID        string          `json:"id"`
	Name      string          `json:"name"`
	Arguments json.RawMessage `json:"arguments"`
}

type toolResultRecord struct {
	Type       string `json:"type"`
	ToolCallID string `json:"tool_call_id"`
	Name       string `json:"name"`
	Content    string `json:"content"`
}

type endRecord struct {
	Type       string  `json:"type"`
	StopReason string  `json:"stop_reason"`
	Turns      int     `json:"turns"`
	Seconds    pyFloat `json:"seconds"`
	Error      *string `json:"error,omitempty"`
}

// toolMessage is the tool result message that goes back to the model.
type toolMessage struct {
	Role       string `json:"role"`
	ToolCallID string `json:"tool_call_id"`
	ToolName   string `json:"tool_name"`
	Content    string `json:"content"`
}

// textMessage is a system or user message.
type textMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// recorder gets one transcript record per assistant message, tool result, and end.
type recorder func(entry any)

// runFacts are the facts of one run.
type runFacts struct {
	stopReason       string
	turns            int
	seconds          float64
	promptTokens     int64
	completionTokens int64
	toolCalls        int
	malformed        int
	err              string
}

// runLoop runs the loop from the spec on messages, in place, and returns the facts of the run.
// An error means a harness failure inside a tool. The caller reports it as a crash.
func runLoop(m *model, toolSet *tools.Tools, messages *[]json.RawMessage, maxTurns, maxSeconds float64, record recorder) (runFacts, error) {
	var facts runFacts
	started := time.Now()
	for {
		// Each call gets the time that remains, so the run ends near max_seconds.
		remaining := math.Max(maxSeconds-time.Since(started).Seconds(), minCallSeconds)
		response, err := m.chat(*messages, toolSet.Definitions(), remaining)
		if err != nil {
			if isTimeout(err) {
				facts.stopReason = "max_seconds"
			} else {
				facts.stopReason = "infra_error"
				facts.err = err.Error()
			}
			break
		}
		facts.turns++
		facts.promptTokens += response.PromptEvalCount
		facts.completionTokens += response.EvalCount
		*messages = append(*messages, response.Message)
		calls, entry, err := readAssistant(response.Message, facts.turns)
		if err != nil {
			return facts, err
		}
		record(entry)
		if len(calls) == 0 {
			facts.stopReason = "end_turn"
			break
		}
		for _, call := range calls {
			content, bad, err := toolSet.Call(call.Name, call.Arguments)
			if err != nil {
				return facts, err
			}
			facts.toolCalls++
			if bad {
				facts.malformed++
			}
			message, err := encodeJSON(toolMessage{Role: "tool", ToolCallID: call.ID, ToolName: call.Name, Content: content})
			if err != nil {
				return facts, err
			}
			*messages = append(*messages, message)
			record(toolResultRecord{Type: "tool_result", ToolCallID: call.ID, Name: call.Name, Content: content})
		}
		if facts.malformed >= maxMalformed {
			facts.stopReason = "malformed_tool_call"
			break
		}
		if float64(facts.turns) >= maxTurns {
			facts.stopReason = "max_turns"
			break
		}
		if time.Since(started).Seconds() >= maxSeconds {
			facts.stopReason = "max_seconds"
			break
		}
	}
	facts.seconds = roundSeconds(time.Since(started).Seconds())
	end := endRecord{Type: "end", StopReason: facts.stopReason, Turns: facts.turns, Seconds: pyFloat(facts.seconds)}
	if facts.stopReason == "infra_error" {
		end.Error = &facts.err
	}
	record(end)
	return facts, nil
}

// readAssistant returns the tool calls of an assistant message and its transcript record.
// It fills in an id when Ollama gives none.
func readAssistant(message json.RawMessage, turn int) ([]toolCallRecord, assistantRecord, error) {
	entry := assistantRecord{Type: "assistant", Content: json.RawMessage(`""`)}
	var fields struct {
		Content   json.RawMessage   `json:"content"`
		Thinking  json.RawMessage   `json:"thinking"`
		ToolCalls []json.RawMessage `json:"tool_calls"`
	}
	if err := json.Unmarshal(message, &fields); err != nil {
		return nil, entry, fmt.Errorf("a bad assistant message from Ollama: %w", err)
	}
	if fields.Content != nil {
		content, err := normalizeJSON(fields.Content)
		if err != nil {
			return nil, entry, err
		}
		entry.Content = content
	}
	var thinking string
	if json.Unmarshal(fields.Thinking, &thinking) == nil && thinking != "" {
		normalized, err := encodeJSON(thinking)
		if err != nil {
			return nil, entry, err
		}
		entry.Thinking = normalized
	}
	calls := make([]toolCallRecord, 0, len(fields.ToolCalls))
	for index, raw := range fields.ToolCalls {
		call, err := readToolCall(raw, turn, index)
		if err != nil {
			return nil, entry, err
		}
		calls = append(calls, call)
	}
	if len(calls) > 0 {
		entry.ToolCalls = calls
	}
	return calls, entry, nil
}

// readToolCall returns the id, the name, and the arguments of one tool call.
func readToolCall(raw json.RawMessage, turn, index int) (toolCallRecord, error) {
	var shape struct {
		ID       any `json:"id"`
		Function struct {
			Name      any             `json:"name"`
			Arguments json.RawMessage `json:"arguments"`
		} `json:"function"`
	}
	if err := json.Unmarshal(raw, &shape); err != nil {
		return toolCallRecord{}, fmt.Errorf("a bad tool call from Ollama: %w", err)
	}
	call := toolCallRecord{ID: fmt.Sprintf("call_%d_%d", turn, index)}
	if id, ok := shape.ID.(string); ok && id != "" {
		call.ID = id
	}
	if name, ok := shape.Function.Name.(string); ok {
		call.Name = name
	}
	arguments := shape.Function.Arguments
	if arguments == nil {
		arguments = json.RawMessage(`{}`)
	}
	// Arguments that arrive as a JSON string are parsed. A string that is not JSON stays a string.
	var text string
	if json.Unmarshal(arguments, &text) == nil && json.Valid([]byte(text)) {
		arguments = json.RawMessage(text)
	}
	normalized, err := normalizeJSON(arguments)
	if err != nil {
		return toolCallRecord{}, err
	}
	call.Arguments = normalized
	return call, nil
}
