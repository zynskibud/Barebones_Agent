package main

// Talk to the model through Ollama.
//
// This is the model seam (a value seam). The model is a tag string
// and a think flag, not a separate type per model.

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
	"unicode"
)

const defaultURL = "http://localhost:11434"

// modelError means Ollama is unreachable or gave a bad answer. The loop reports infra_error.
type modelError struct {
	message string
	timeout bool
}

func (e *modelError) Error() string {
	return e.message
}

// isTimeout reports whether one call ran past its timeout. The loop reports max_seconds.
func isTimeout(err error) bool {
	var failure *modelError
	return errors.As(err, &failure) && failure.timeout
}

// model is one Ollama chat model: the tag, the think flag, and the options to send.
type model struct {
	name        string
	think       value
	numCtx      value
	temperature value
	url         string
	// timeout is the HTTP timeout in seconds for calls that set none.
	timeout float64
	client  *http.Client
}

// newModel reads the model settings from the config.
func newModel(cfg *config, timeout float64) (*model, error) {
	name, err := cfg.text("model")
	if err != nil {
		return nil, err
	}
	think, _ := cfg.get("think")
	numCtx, _ := cfg.get("num_ctx")
	temperature, _ := cfg.get("temperature")
	return &model{
		name:        name,
		think:       think,
		numCtx:      numCtx,
		temperature: temperature,
		url:         defaultURL,
		timeout:     timeout,
		client:      &http.Client{},
	}, nil
}

// chatRequest is the body of POST /api/chat, with the fields in spec order.
type chatRequest struct {
	Model    string            `json:"model"`
	Messages []json.RawMessage `json:"messages"`
	Tools    []json.RawMessage `json:"tools"`
	Stream   bool              `json:"stream"`
	Think    value             `json:"think"`
	Options  *chatOptions      `json:"options,omitempty"`
}

// chatOptions holds only the options that the config sets.
type chatOptions struct {
	NumCtx      *value `json:"num_ctx,omitempty"`
	Temperature *value `json:"temperature,omitempty"`
}

// chatResponse is the part of the Ollama reply that the loop reads.
// message stays raw, so the loop can send it back exactly as Ollama returned it.
type chatResponse struct {
	Message         json.RawMessage `json:"message"`
	PromptEvalCount int64           `json:"prompt_eval_count"`
	EvalCount       int64           `json:"eval_count"`
}

// requestBody builds the JSON body of one chat call.
func (m *model) requestBody(messages, tools []json.RawMessage) ([]byte, error) {
	body := chatRequest{
		Model:    m.name,
		Messages: messages,
		Tools:    tools,
		Stream:   false,
		Think:    m.think,
	}
	if body.Tools == nil {
		body.Tools = []json.RawMessage{}
	}
	options := chatOptions{}
	if !m.numCtx.isNull() {
		options.NumCtx = &m.numCtx
	}
	if !m.temperature.isNull() {
		options.Temperature = &m.temperature
	}
	if options.NumCtx != nil || options.Temperature != nil {
		body.Options = &options
	}
	return encodeJSON(body)
}

// chat sends POST /api/chat once and returns the reply.
// timeout is the HTTP timeout for this call, in seconds.
func (m *model) chat(messages, tools []json.RawMessage, timeout float64) (*chatResponse, error) {
	body, err := m.requestBody(messages, tools)
	if err != nil {
		return nil, err
	}
	raw, err := m.send(http.MethodPost, "/api/chat", body, timeout)
	if err != nil {
		return nil, err
	}
	var fields map[string]json.RawMessage
	_ = json.Unmarshal(raw, &fields)
	if _, ok := fields["message"]; !ok {
		return nil, &modelError{message: "no message in the Ollama response: " + firstCharacters(string(raw), 500)}
	}
	var response chatResponse
	if err := json.Unmarshal(raw, &response); err != nil {
		return nil, &modelError{message: "a bad Ollama response: " + err.Error()}
	}
	return &response, nil
}

// modelEntry is one model in the lists of /api/tags and /api/ps.
type modelEntry struct {
	Name          string          `json:"name"`
	Model         string          `json:"model"`
	Digest        json.RawMessage `json:"digest"`
	ContextLength json.RawMessage `json:"context_length"`
}

// listModels sends GET to a list endpoint and returns the models.
func (m *model) listModels(path string) ([]modelEntry, error) {
	raw, err := m.send(http.MethodGet, path, nil, m.timeout)
	if err != nil {
		return nil, err
	}
	var reply struct {
		Models []modelEntry `json:"models"`
	}
	if err := json.Unmarshal(raw, &reply); err != nil {
		return nil, &modelError{message: "a bad reply from " + path + ": " + err.Error()}
	}
	return reply.Models, nil
}

// digest returns the model digest from /api/tags, or nil if the tag is not listed.
func (m *model) digest() (json.RawMessage, error) {
	entries, err := m.listModels("/api/tags")
	if err != nil {
		return nil, err
	}
	for _, entry := range entries {
		if entry.Name == m.name || entry.Model == m.name {
			return entry.Digest, nil
		}
	}
	return nil, nil
}

// loadedContextLength returns the context length of the loaded model from /api/ps,
// or nil if the model is not loaded.
func (m *model) loadedContextLength() (json.RawMessage, error) {
	entries, err := m.listModels("/api/ps")
	if err != nil {
		return nil, err
	}
	for _, entry := range entries {
		if entry.Name == m.name || entry.Model == m.name {
			return entry.ContextLength, nil
		}
	}
	return nil, nil
}

// defaultParameters returns the model's own parameters from /api/show, for example temperature.
func (m *model) defaultParameters() (map[string]string, error) {
	body, err := encodeJSON(map[string]string{"model": m.name})
	if err != nil {
		return nil, err
	}
	raw, err := m.send(http.MethodPost, "/api/show", body, m.timeout)
	if err != nil {
		return nil, err
	}
	var reply struct {
		Parameters string `json:"parameters"`
	}
	if err := json.Unmarshal(raw, &reply); err != nil {
		return nil, &modelError{message: "a bad reply from /api/show: " + err.Error()}
	}
	parameters := map[string]string{}
	for _, line := range strings.Split(reply.Parameters, "\n") {
		line = strings.TrimLeftFunc(line, unicode.IsSpace)
		split := strings.IndexFunc(line, unicode.IsSpace)
		if split < 0 {
			continue
		}
		rest := trimSpace(line[split:])
		if rest == "" {
			continue
		}
		parameters[line[:split]] = rest
	}
	return parameters, nil
}

// send sends one request and returns the body. Every transport or format problem is a modelError.
func (m *model) send(method, path string, body []byte, timeout float64) ([]byte, error) {
	url := m.url + path
	ctx, cancel := context.WithTimeout(context.Background(), time.Duration(timeout*float64(time.Second)))
	defer cancel()
	request, err := http.NewRequestWithContext(ctx, method, url, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	if body != nil {
		request.Header.Set("Content-Type", "application/json")
	}
	timedOut := &modelError{message: fmt.Sprintf("no reply from %s in %.1f seconds", url, timeout), timeout: true}
	response, err := m.client.Do(request)
	if err != nil {
		if ctx.Err() != nil {
			return nil, timedOut
		}
		return nil, &modelError{message: fmt.Sprintf("cannot reach %s: %v", url, err)}
	}
	defer response.Body.Close()
	raw, err := io.ReadAll(response.Body)
	if err != nil {
		if ctx.Err() != nil {
			return nil, timedOut
		}
		return nil, &modelError{message: fmt.Sprintf("cannot reach %s: %v", url, err)}
	}
	if response.StatusCode >= 400 {
		detail := firstCharacters(strings.ToValidUTF8(string(raw), "�"), 500)
		return nil, &modelError{message: fmt.Sprintf("HTTP %d from %s: %s", response.StatusCode, url, detail)}
	}
	var parsed any
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return nil, &modelError{message: "no JSON in the reply from " + url}
	}
	if object, ok := parsed.(map[string]any); ok {
		if failure, ok := object["error"]; ok {
			return nil, &modelError{message: fmt.Sprintf("Ollama error: %v", failure)}
		}
	}
	return raw, nil
}
