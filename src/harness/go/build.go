package main

// The composition root.
//
// buildAgent(config) is the only place that reads the choices
// and builds the parts: model, tools, env, and loop.

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"barebones/harness/env"
	"barebones/harness/tools"
)

// envMaker builds one env from the host working folder and max_seconds.
type envMaker func(workdir string, maxSeconds float64, root string) (env.Env, error)

var envs = map[string]envMaker{
	"local": func(workdir string, maxSeconds float64, root string) (env.Env, error) {
		return env.NewLocal(workdir, maxSeconds)
	},
	"docker": func(workdir string, maxSeconds float64, root string) (env.Env, error) {
		return env.NewDocker(workdir, maxSeconds)
	},
	"cloud": func(workdir string, maxSeconds float64, root string) (env.Env, error) {
		return env.NewCloud(workdir, maxSeconds, filepath.Join(root, ".env"))
	},
}

var handlers = map[string]tools.Handler{
	"read_file":  tools.ReadFile,
	"list_files": tools.ListFiles,
	"edit_file":  tools.EditFile,
	"bash":       tools.Bash,
}

// agent holds the built parts that the loop and main need.
type agent struct {
	model        *model
	tools        *tools.Tools
	env          env.Env
	systemPrompt string
	maxTurns     float64
	maxSeconds   float64
}

// buildAgent reads the choices in config and builds every part.
func buildAgent(cfg *config, workdir string) (*agent, error) {
	root, err := repoRoot()
	if err != nil {
		return nil, err
	}
	maxSeconds, err := cfg.number("max_seconds")
	if err != nil {
		return nil, err
	}
	maxTurns, err := cfg.number("max_turns")
	if err != nil {
		return nil, err
	}
	envName, err := cfg.text("env")
	if err != nil {
		return nil, err
	}
	makeEnv, ok := envs[envName]
	if !ok {
		return nil, fmt.Errorf("unknown env %s", envName)
	}
	// Every env gets max_seconds. An env that needs no time limit ignores it.
	chosenEnv, err := makeEnv(workdir, maxSeconds, root)
	if err != nil {
		return nil, err
	}
	configDir := filepath.Join(root, "config")
	messagesData, err := os.ReadFile(filepath.Join(configDir, "messages.json"))
	if err != nil {
		return nil, err
	}
	messages, err := tools.LoadMessages(messagesData)
	if err != nil {
		return nil, err
	}
	setName, err := cfg.text("tools")
	if err != nil {
		return nil, err
	}
	definitions, err := loadDefinitions(filepath.Join(configDir, "tools.json"), setName)
	if err != nil {
		return nil, err
	}
	toolSet, err := tools.New(definitions, handlers, chosenEnv, messages)
	if err != nil {
		return nil, err
	}
	chosenModel, err := newModel(cfg, maxSeconds)
	if err != nil {
		return nil, err
	}
	systemPrompt, err := readText(filepath.Join(configDir, "system_prompt.txt"))
	if err != nil {
		return nil, err
	}
	return &agent{
		model:        chosenModel,
		tools:        toolSet,
		env:          chosenEnv,
		systemPrompt: trimRight(systemPrompt),
		maxTurns:     maxTurns,
		maxSeconds:   maxSeconds,
	}, nil
}

// loadDefinitions returns the definitions of one tool set, in set order, as stored in tools.json.
func loadDefinitions(path, setName string) ([]json.RawMessage, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var file struct {
		Tools map[string]json.RawMessage `json:"tools"`
		Sets  map[string][]string        `json:"sets"`
	}
	if err := json.Unmarshal(data, &file); err != nil {
		return nil, fmt.Errorf("tools.json: %w", err)
	}
	names, ok := file.Sets[setName]
	if !ok {
		return nil, fmt.Errorf("tools.json has no tool set %s", setName)
	}
	definitions := make([]json.RawMessage, 0, len(names))
	for _, name := range names {
		definition, ok := file.Tools[name]
		if !ok {
			return nil, fmt.Errorf("tools.json has no tool %s", name)
		}
		definitions = append(definitions, definition)
	}
	return definitions, nil
}

// repoRoot finds the folder that holds config/tools.json.
// It looks in the current folder and its parents first, because go run builds
// the program in a temporary folder. Then it looks above the program file.
func repoRoot() (string, error) {
	var starts []string
	if wd, err := os.Getwd(); err == nil {
		starts = append(starts, wd)
	}
	if program, err := os.Executable(); err == nil {
		if real, err := filepath.EvalSymlinks(program); err == nil {
			program = real
		}
		starts = append(starts, filepath.Dir(program))
	}
	for _, start := range starts {
		for folder := start; ; folder = filepath.Dir(folder) {
			if info, err := os.Stat(filepath.Join(folder, "config", "tools.json")); err == nil && !info.IsDir() {
				return folder, nil
			}
			if filepath.Dir(folder) == folder {
				break
			}
		}
	}
	return "", errors.New("cannot find the repo root: no config/tools.json in the current folder, " +
		"the program folder, or their parents")
}

// configID returns <harness>.<tools>.<env>.<codebase>.<model-id>.<think-id>.
func configID(cfg *config) (string, error) {
	parts := make([]string, 0, 6)
	for _, key := range []string{"harness", "tools", "env", "codebase", "model"} {
		text, err := cfg.text(key)
		if err != nil {
			return "", err
		}
		parts = append(parts, text)
	}
	parts[4] = strings.ReplaceAll(parts[4], ":", "-")
	think, ok := cfg.get("think")
	if !ok {
		return "", errors.New("the config has no think key")
	}
	if think.truthy() {
		parts = append(parts, "think")
	} else {
		parts = append(parts, "no-think")
	}
	return strings.Join(parts, "."), nil
}

// config is a flat YAML config: keys in file order, each with one scalar value.
type config struct {
	keys   []string
	values map[string]value
}

func (c *config) get(key string) (value, bool) {
	found, ok := c.values[key]
	return found, ok
}

// text returns a string value, or an error when the key is missing or not a string.
func (c *config) text(key string) (string, error) {
	found, ok := c.values[key]
	if !ok {
		return "", fmt.Errorf("the config has no %s key", key)
	}
	if found.kind != stringValue {
		return "", fmt.Errorf("the config value of %s is not text", key)
	}
	return found.s, nil
}

// number returns a number value, or an error when the key is missing or not a number.
func (c *config) number(key string) (float64, error) {
	found, ok := c.values[key]
	if !ok {
		return 0, fmt.Errorf("the config has no %s key", key)
	}
	switch found.kind {
	case intValue:
		return float64(found.i), nil
	case floatValue:
		return found.f, nil
	}
	return 0, fmt.Errorf("the config value of %s is not a number", key)
}

// MarshalJSON writes the config as one object with the keys in file order.
func (c *config) MarshalJSON() ([]byte, error) {
	out := []byte{'{'}
	for index, key := range c.keys {
		if index > 0 {
			out = append(out, ',')
		}
		name, err := encodeJSON(key)
		if err != nil {
			return nil, err
		}
		item, err := c.values[key].MarshalJSON()
		if err != nil {
			return nil, err
		}
		out = append(append(append(out, name...), ':'), item...)
	}
	return append(out, '}'), nil
}

// loadConfig reads a flat YAML config file: one key: value per line, with # comments.
func loadConfig(path string) (*config, error) {
	text, err := readText(path)
	if err != nil {
		return nil, err
	}
	cfg := &config{values: map[string]value{}}
	for _, line := range strings.Split(text, "\n") {
		line = trimSpace(stripComment(line))
		key, raw, found := strings.Cut(line, ":")
		if line == "" || !found {
			continue
		}
		key = trimSpace(key)
		if _, seen := cfg.values[key]; !seen {
			cfg.keys = append(cfg.keys, key)
		}
		cfg.values[key] = parseScalar(trimSpace(raw))
	}
	return cfg, nil
}

// stripComment removes a # comment. A # inside quotes stays.
func stripComment(line string) string {
	var quote byte
	for index := 0; index < len(line); index++ {
		char := line[index]
		switch {
		case quote != 0:
			if char == quote {
				quote = 0
			}
		case char == '\'' || char == '"':
			quote = char
		case char == '#' && (index == 0 || line[index-1] == ' ' || line[index-1] == '\t'):
			return line[:index]
		}
	}
	return line
}

// valueKind names the type of one config value.
type valueKind int

const (
	nullValue valueKind = iota
	boolValue
	intValue
	floatValue
	stringValue
)

// value is one YAML scalar: null, a bool, an integer, a float, or text.
type value struct {
	kind valueKind
	b    bool
	i    int64
	f    float64
	s    string
}

// parseScalar turns one YAML scalar into a value, with the rules of the Python harness.
func parseScalar(raw string) value {
	switch raw {
	case "", "null", "~":
		return value{kind: nullValue}
	case "true", "True":
		return value{kind: boolValue, b: true}
	case "false", "False":
		return value{kind: boolValue, b: false}
	}
	if len(raw) >= 2 && raw[0] == raw[len(raw)-1] && (raw[0] == '\'' || raw[0] == '"') {
		return value{kind: stringValue, s: raw[1 : len(raw)-1]}
	}
	if number, err := strconv.ParseInt(raw, 10, 64); err == nil {
		return value{kind: intValue, i: number}
	}
	// Only decimal numbers count. Text such as inf or 0x10 stays text.
	if strings.ContainsAny(raw, "0123456789") && !strings.ContainsAny(raw, "xXpP_") {
		if number, err := strconv.ParseFloat(raw, 64); err == nil {
			return value{kind: floatValue, f: number}
		}
	}
	return value{kind: stringValue, s: raw}
}

// truthy follows the Python truth rules.
func (v value) truthy() bool {
	switch v.kind {
	case boolValue:
		return v.b
	case intValue:
		return v.i != 0
	case floatValue:
		return v.f != 0
	case stringValue:
		return v.s != ""
	}
	return false
}

func (v value) isNull() bool {
	return v.kind == nullValue
}

// MarshalJSON writes the value as Python's json module writes it.
func (v value) MarshalJSON() ([]byte, error) {
	switch v.kind {
	case boolValue:
		return []byte(strconv.FormatBool(v.b)), nil
	case intValue:
		return []byte(strconv.FormatInt(v.i, 10)), nil
	case floatValue:
		return []byte(pythonFloat(v.f)), nil
	case stringValue:
		return encodeJSON(v.s)
	}
	return []byte("null"), nil
}
