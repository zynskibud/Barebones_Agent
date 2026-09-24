// Package tools holds the tool registry: definitions, argument checks, dispatch, and truncation.
//
// The tool definitions come from config/tools.json and go to the model
// exactly as stored. Every string that the model reads comes from
// config/messages.json. This package holds no tool text of its own.
package tools

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strconv"
	"strings"
	"unicode/utf8"

	"barebones/harness/env"
)

// MaxResultChars is the longest tool result, in characters, before truncation.
const MaxResultChars = 10_000

// Handler runs one tool. It returns the result text, or an error for a harness failure.
type Handler func(e env.Env, messages *Messages, arguments map[string]any) (string, error)

// Messages holds the strings of config/messages.json.
type Messages struct {
	tree map[string]any
}

// The keys that the harness uses. LoadMessages checks that each one is a string.
var messageKeys = []string{
	env.KeyOutsideFolder, env.KeyNotFound, env.KeyIsDirectory, env.KeyNotDirectory, env.KeyTimeout,
	"errors.already_exists", "errors.old_str_not_found", "errors.old_str_multiple",
	"errors.unknown_tool", "errors.invalid_arguments",
	"ok.edited", "ok.created", "truncated", "exit_code",
}

// LoadMessages parses messages.json and checks that every key the harness uses is there.
func LoadMessages(data []byte) (*Messages, error) {
	var tree map[string]any
	if err := json.Unmarshal(data, &tree); err != nil {
		return nil, fmt.Errorf("messages.json: %w", err)
	}
	messages := &Messages{tree: tree}
	for _, key := range messageKeys {
		if _, ok := messages.lookup(key); !ok {
			return nil, fmt.Errorf("messages.json has no string at %s", key)
		}
	}
	return messages, nil
}

// lookup returns the string at a dotted key.
func (m *Messages) lookup(key string) (string, bool) {
	var node any = m.tree
	for _, part := range strings.Split(key, ".") {
		branch, ok := node.(map[string]any)
		if !ok {
			return "", false
		}
		node = branch[part]
	}
	text, ok := node.(string)
	return text, ok
}

// Text returns the string at a dotted key with its placeholders filled.
// pairs holds placeholder names and values: "path", "a.py", ...
func (m *Messages) Text(key string, pairs ...string) string {
	text, _ := m.lookup(key)
	replacements := make([]string, 0, len(pairs))
	for index := 0; index+1 < len(pairs); index += 2 {
		replacements = append(replacements, "{"+pairs[index]+"}", pairs[index+1])
	}
	// One pass, so a value that holds a placeholder stays as it is.
	return strings.NewReplacer(replacements...).Replace(text)
}

// EnvError turns an env error into the message string that its key names.
// The message names the path that the model sent, unless the env set a path.
func EnvError(messages *Messages, err *env.Error, path string) string {
	if err.Path != nil {
		path = *err.Path
	}
	return messages.Text(err.Key, "path", path)
}

// Truncate keeps the first MaxResultChars characters and adds the truncation line.
func Truncate(messages *Messages, result string) string {
	length := utf8.RuneCountInString(result)
	if length <= MaxResultChars {
		return result
	}
	cut := length - MaxResultChars
	end := 0
	for count := 0; count < MaxResultChars; count++ {
		_, size := utf8.DecodeRuneInString(result[end:])
		end += size
	}
	return result[:end] + "\n" + messages.Text("truncated", "n", strconv.Itoa(cut))
}

// schema is the part of a tool definition that the argument check reads.
type schema struct {
	properties map[string]json.RawMessage
	required   []string
	closed     bool
}

// Tools is the tool set for one run: the ordered definitions and the dispatch.
type Tools struct {
	definitions []json.RawMessage
	byName      map[string]schema
	handlers    map[string]Handler
	env         env.Env
	messages    *Messages
}

// New builds the tool set. Each definition must have a handler.
func New(definitions []json.RawMessage, handlers map[string]Handler, e env.Env, messages *Messages) (*Tools, error) {
	tools := &Tools{
		definitions: definitions,
		byName:      map[string]schema{},
		handlers:    map[string]Handler{},
		env:         e,
		messages:    messages,
	}
	for _, definition := range definitions {
		parsed, name, err := parseDefinition(definition)
		if err != nil {
			return nil, err
		}
		handler, ok := handlers[name]
		if !ok {
			return nil, fmt.Errorf("no handler for the tool %s", name)
		}
		tools.byName[name] = parsed
		tools.handlers[name] = handler
	}
	return tools, nil
}

// parseDefinition reads the name and the parameter schema of one definition.
func parseDefinition(definition json.RawMessage) (schema, string, error) {
	var shape struct {
		Function struct {
			Name       string `json:"name"`
			Parameters struct {
				Properties           map[string]json.RawMessage `json:"properties"`
				Required             []string                   `json:"required"`
				AdditionalProperties json.RawMessage            `json:"additionalProperties"`
			} `json:"parameters"`
		} `json:"function"`
	}
	if err := json.Unmarshal(definition, &shape); err != nil {
		return schema{}, "", fmt.Errorf("tools.json: %w", err)
	}
	parameters := shape.Function.Parameters
	parsed := schema{
		properties: parameters.Properties,
		required:   parameters.Required,
		// Only a literal false closes the object, as in the Python check.
		closed: bytes.Equal(bytes.TrimSpace(parameters.AdditionalProperties), []byte("false")),
	}
	return parsed, shape.Function.Name, nil
}

// Definitions returns the tool definitions in set order, as stored.
func (t *Tools) Definitions() []json.RawMessage {
	return t.definitions
}

// Call runs one tool call. It returns the result text and whether the call was malformed.
// An error means a harness failure, not a tool problem.
func (t *Tools) Call(name string, arguments json.RawMessage) (string, bool, error) {
	parsed, ok := t.byName[name]
	if !ok {
		return t.messages.Text("errors.unknown_tool", "name", name), true, nil
	}
	values, problem := checkArguments(parsed, arguments)
	if problem != "" {
		return t.messages.Text("errors.invalid_arguments", "name", name, "detail", problem), true, nil
	}
	result, err := t.handlers[name](t.env, t.messages, values)
	if err != nil {
		return "", false, err
	}
	return Truncate(t.messages, result), false, nil
}

// checkArguments returns the decoded arguments, or what is wrong with them.
func checkArguments(parsed schema, arguments json.RawMessage) (map[string]any, string) {
	keys, raw, ok := objectMembers(arguments)
	if !ok {
		return nil, "arguments are not a JSON object"
	}
	for _, key := range parsed.required {
		if _, found := raw[key]; !found {
			return nil, "missing required argument " + key
		}
	}
	for _, key := range keys {
		property, known := parsed.properties[key]
		if !known {
			if parsed.closed {
				return nil, "unexpected argument " + key
			}
			continue
		}
		var shape struct {
			Type json.RawMessage `json:"type"`
		}
		_ = json.Unmarshal(property, &shape)
		var expected string
		if json.Unmarshal(shape.Type, &expected) != nil || expected == "" {
			continue
		}
		if !fitsType(raw[key], expected) {
			return nil, key + " must be a " + expected
		}
	}
	values := map[string]any{}
	for key, value := range raw {
		var decoded any
		_ = json.Unmarshal(value, &decoded)
		values[key] = decoded
	}
	return values, ""
}

// objectMembers returns the keys of a JSON object in order, and the raw value of each key.
// A key that appears twice keeps its first place and its last value, as in a Python dict.
func objectMembers(data json.RawMessage) ([]string, map[string]json.RawMessage, bool) {
	decoder := json.NewDecoder(bytes.NewReader(data))
	token, err := decoder.Token()
	if err != nil || token != json.Delim('{') {
		return nil, nil, false
	}
	var keys []string
	values := map[string]json.RawMessage{}
	for decoder.More() {
		token, err := decoder.Token()
		if err != nil {
			return nil, nil, false
		}
		key, _ := token.(string)
		var value json.RawMessage
		if err := decoder.Decode(&value); err != nil {
			return nil, nil, false
		}
		if _, seen := values[key]; !seen {
			keys = append(keys, key)
		}
		values[key] = value
	}
	if _, err := decoder.Token(); err != nil {
		return nil, nil, false
	}
	if _, err := decoder.Token(); !errors.Is(err, io.EOF) {
		return nil, nil, false
	}
	return keys, values, true
}

// fitsType checks one JSON schema type. A bool never counts as an integer or a number.
func fitsType(value json.RawMessage, expected string) bool {
	text := bytes.TrimSpace(value)
	if len(text) == 0 {
		return false
	}
	first := text[0]
	isNumber := first == '-' || (first >= '0' && first <= '9')
	switch expected {
	case "string":
		return first == '"'
	case "integer":
		return isNumber && !bytes.ContainsAny(text, ".eE")
	case "number":
		return isNumber
	case "boolean":
		return first == 't' || first == 'f'
	case "object":
		return first == '{'
	case "array":
		return first == '['
	}
	return true
}

// stringArgument returns a string argument, or fallback when the key is missing.
// The argument check has already checked the type against the schema.
func stringArgument(arguments map[string]any, key, fallback string) string {
	if value, ok := arguments[key].(string); ok {
		return value
	}
	return fallback
}
