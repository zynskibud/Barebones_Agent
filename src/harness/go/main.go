// Command harness starts the agent.
//
// Chat mode: an interactive session in the terminal.
// Task mode: one task, then exit. The eval harness starts it as a separate program.
package main

import (
	"bufio"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/signal"
	"path/filepath"
	"runtime/debug"
	"strconv"
	"strings"
	"sync"

	"barebones/harness/env"
)

var exitCodes = map[string]int{
	"end_turn":            0,
	"max_turns":           2,
	"max_seconds":         2,
	"malformed_tool_call": 2,
	"infra_error":         3,
}

const resultPreviewChars = 300

// options are the command line flags.
type options struct {
	config     string
	workdir    string
	mode       string
	promptFile string
	transcript string
	result     string
}

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(arguments []string) int {
	opts, code, ok := parseArgs(arguments)
	if !ok {
		return code
	}
	if opts.mode == "task" {
		return runTask(opts)
	}
	return runChat(opts)
}

// parseArgs reads the flags. A usage error exits with the infra_error code.
func parseArgs(arguments []string) (options, int, bool) {
	var opts options
	flags := flag.NewFlagSet("harness", flag.ContinueOnError)
	flags.SetOutput(os.Stderr)
	flags.StringVar(&opts.config, "config", "", "the config file")
	flags.StringVar(&opts.workdir, "workdir", "", "the working folder; the agent works only here")
	flags.StringVar(&opts.mode, "mode", "chat", "chat or task")
	flags.StringVar(&opts.promptFile, "prompt-file", "", "task mode: the file that holds the task prompt")
	flags.StringVar(&opts.transcript, "transcript", "", "task mode: where to write transcript.jsonl")
	flags.StringVar(&opts.result, "result", "", "task mode: where to write result.json")
	flags.Usage = func() {
		fmt.Fprintln(os.Stderr, "usage: harness --config CONFIG --workdir WORKDIR [--mode {chat,task}] "+
			"[--prompt-file PROMPT_FILE] [--transcript TRANSCRIPT] [--result RESULT]")
	}
	err := flags.Parse(arguments)
	if errors.Is(err, flag.ErrHelp) {
		flags.PrintDefaults()
		return opts, 0, false
	}
	usageError := func(message string) (options, int, bool) {
		flags.Usage()
		fmt.Fprintf(os.Stderr, "harness: error: %s\n", message)
		return opts, exitCodes["infra_error"], false
	}
	if err != nil {
		// The flag package has already printed the problem and the usage.
		return opts, exitCodes["infra_error"], false
	}
	if flags.NArg() > 0 {
		return usageError("unrecognized arguments: " + strings.Join(flags.Args(), " "))
	}
	given := map[string]bool{}
	flags.Visit(func(f *flag.Flag) { given[f.Name] = true })
	var missing []string
	for _, name := range []string{"config", "workdir"} {
		if !given[name] {
			missing = append(missing, "--"+name)
		}
	}
	if len(missing) > 0 {
		return usageError("the following arguments are required: " + strings.Join(missing, ", "))
	}
	if opts.mode != "chat" && opts.mode != "task" {
		return usageError(fmt.Sprintf("argument --mode: invalid choice: '%s' (choose from 'chat', 'task')", opts.mode))
	}
	if opts.mode == "task" {
		for _, name := range []string{"prompt-file", "transcript", "result"} {
			if !given[name] {
				return usageError("--" + name + " is required in task mode")
			}
		}
	}
	return opts, 0, true
}

// usedSettings are the model values that the run used.
type usedSettings struct {
	modelDigest json.RawMessage
	numCtx      json.RawMessage
	temperature json.RawMessage
}

// runTask runs one task, writes the transcript and the result, and prints the status line.
func runTask(opts options) int {
	cfg, err := loadConfig(opts.config)
	var transcript *transcriptFile
	if err == nil {
		transcript, err = openTranscript(opts.transcript, cfg)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "cannot start: %v\n", err)
		fmt.Println("stop_reason=infra_error turns=0 seconds=0.0")
		return exitCodes["infra_error"]
	}
	facts, used, err := runTaskParts(opts, cfg, transcript.record)
	if err != nil {
		detail := err.Error()
		fmt.Fprintln(os.Stderr, detail)
		facts = runFacts{stopReason: "infra_error", err: detail}
		transcript.record(endRecord{Type: "end", StopReason: "infra_error", Seconds: 0, Error: &detail})
		used = usedSettings{numCtx: configJSON(cfg, "num_ctx"), temperature: configJSON(cfg, "temperature")}
	}
	transcript.close()
	exitCode := exitCodes[facts.stopReason]
	if err := writeResult(opts.result, cfg, facts, used, exitCode); err != nil {
		fmt.Fprintf(os.Stderr, "cannot write the result: %v\n", err)
		exitCode = exitCodes["infra_error"]
	}
	if facts.err != "" {
		lines := strings.Split(trimRight(facts.err), "\n")
		fmt.Fprintln(os.Stderr, lines[len(lines)-1])
	}
	fmt.Printf("stop_reason=%s turns=%d seconds=%s\n", facts.stopReason, facts.turns, pythonFloat(facts.seconds))
	return exitCode
}

// runTaskParts builds the agent, runs the loop, and stops the env.
// Any error, and any panic, is a harness crash.
func runTaskParts(opts options, cfg *config, record recorder) (facts runFacts, used usedSettings, err error) {
	defer func() {
		if caught := recover(); caught != nil {
			err = fmt.Errorf("panic: %v\n%s", caught, debug.Stack())
		}
	}()
	built, err := buildAgent(cfg, opts.workdir)
	if err != nil {
		return facts, used, err
	}
	prompt, err := readText(opts.promptFile)
	if err != nil {
		return facts, used, err
	}
	prompt = trimRight(prompt)
	record(textRecord{Type: "system", Content: built.systemPrompt})
	record(textRecord{Type: "user", Content: prompt})
	messages, err := startMessages(built.systemPrompt, prompt)
	if err != nil {
		return facts, used, err
	}
	stop := stopOnce(built.env)
	defer stop()
	// A failed start still reaches stop.
	facts, err = startAndLoop(built, &messages, record)
	if stopErr := stop(); stopErr != nil {
		err = errors.Join(err, stopErr)
	}
	if err != nil {
		return facts, used, err
	}
	return facts, usedModelSettings(built, cfg), nil
}

// startAndLoop starts the env and runs the loop.
func startAndLoop(built *agent, messages *[]json.RawMessage, record recorder) (runFacts, error) {
	if err := built.env.Start(); err != nil {
		return runFacts{}, err
	}
	return runLoop(built.model, built.tools, messages, built.maxTurns, built.maxSeconds, record)
}

// startMessages returns the system message and the user message.
func startMessages(systemPrompt, prompt string) ([]json.RawMessage, error) {
	system, err := encodeJSON(textMessage{Role: "system", Content: systemPrompt})
	if err != nil {
		return nil, err
	}
	user, err := encodeJSON(textMessage{Role: "user", Content: prompt})
	if err != nil {
		return nil, err
	}
	return []json.RawMessage{system, user}, nil
}

// stopOnce returns a function that stops the env the first time only.
// An interrupt (Ctrl-C) also stops the env, so a cloud run still downloads its work.
func stopOnce(chosen env.Env) func() error {
	var once sync.Once
	var stopErr error
	stop := func() error {
		once.Do(func() { stopErr = chosen.Stop() })
		return stopErr
	}
	interrupts := make(chan os.Signal, 1)
	signal.Notify(interrupts, os.Interrupt)
	go func() {
		<-interrupts
		if err := stop(); err != nil {
			fmt.Fprintln(os.Stderr, err)
		}
		os.Exit(130)
	}()
	return stop
}

// usedModelSettings finds the digest, context size, and temperature that the run used.
func usedModelSettings(built *agent, cfg *config) usedSettings {
	used := usedSettings{numCtx: configJSON(cfg, "num_ctx"), temperature: configJSON(cfg, "temperature")}
	var err error
	defer func() {
		if err != nil {
			fmt.Fprintf(os.Stderr, "could not read the model settings: %v\n", err)
		}
	}()
	if used.modelDigest, err = built.model.digest(); err != nil {
		return used
	}
	if isNullJSON(used.numCtx) {
		if used.numCtx, err = built.model.loadedContextLength(); err != nil {
			return used
		}
	}
	if isNullJSON(used.temperature) {
		var parameters map[string]string
		if parameters, err = built.model.defaultParameters(); err != nil {
			return used
		}
		used.temperature = nil
		if raw, ok := parameters["temperature"]; ok {
			number, parseErr := strconv.ParseFloat(raw, 64)
			if parseErr != nil {
				err = fmt.Errorf("could not convert string to float: '%s'", raw)
				return used
			}
			used.temperature = json.RawMessage(pythonFloat(number))
		}
	}
	return used
}

// configJSON returns the JSON of one config value, or null when the key is missing.
func configJSON(cfg *config, key string) json.RawMessage {
	found, ok := cfg.get(key)
	if !ok {
		return nil
	}
	raw, _ := found.MarshalJSON()
	return raw
}

func isNullJSON(raw json.RawMessage) bool {
	return len(raw) == 0 || string(raw) == "null"
}

// transcriptFile writes transcript.jsonl one line at a time.
type transcriptFile struct {
	file *os.File
}

// openTranscript opens transcript.jsonl and writes the config line.
func openTranscript(path string, cfg *config) (*transcriptFile, error) {
	id, err := configID(cfg)
	if err != nil {
		return nil, err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o777); err != nil {
		return nil, err
	}
	file, err := os.Create(path)
	if err != nil {
		return nil, err
	}
	transcript := &transcriptFile{file: file}
	transcript.record(struct {
		Type     string  `json:"type"`
		ConfigID string  `json:"config_id"`
		Config   *config `json:"config"`
	}{"config", id, cfg})
	return transcript, nil
}

// record appends one JSON line. The file is not buffered, so each line is on disk at once.
func (t *transcriptFile) record(entry any) {
	line, err := encodeJSON(entry)
	if err == nil {
		_, err = t.file.Write(append(line, '\n'))
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "cannot write the transcript: %v\n", err)
	}
}

func (t *transcriptFile) close() {
	if err := t.file.Close(); err != nil {
		fmt.Fprintf(os.Stderr, "cannot close the transcript: %v\n", err)
	}
}

// result is result.json, with the keys in the order of the spec, section 11.
type result struct {
	ConfigID           string          `json:"config_id"`
	Task               string          `json:"task"`
	Trial              *int64          `json:"trial"`
	StopReason         string          `json:"stop_reason"`
	Turns              int             `json:"turns"`
	Seconds            pyFloat         `json:"seconds"`
	PromptTokens       int64           `json:"prompt_tokens"`
	CompletionTokens   int64           `json:"completion_tokens"`
	Model              json.RawMessage `json:"model"`
	ModelDigest        json.RawMessage `json:"model_digest"`
	NumCtx             json.RawMessage `json:"num_ctx"`
	Temperature        json.RawMessage `json:"temperature"`
	Think              json.RawMessage `json:"think"`
	ExitCode           int             `json:"exit_code"`
	ToolCalls          int             `json:"tool_calls"`
	MalformedToolCalls int             `json:"malformed_tool_calls"`
	Passed             json.RawMessage `json:"passed"`
	GraderOutput       json.RawMessage `json:"grader_output"`
}

// writeResult writes result.json with exactly the keys in the spec.
func writeResult(path string, cfg *config, facts runFacts, used usedSettings, exitCode int) error {
	id, err := configID(cfg)
	if err != nil {
		return err
	}
	trialFolder := filepath.Dir(path)
	written := result{
		ConfigID:           id,
		Task:               folderName(filepath.Dir(trialFolder)),
		Trial:              trialNumber(folderName(trialFolder)),
		StopReason:         facts.stopReason,
		Turns:              facts.turns,
		Seconds:            pyFloat(facts.seconds),
		PromptTokens:       facts.promptTokens,
		CompletionTokens:   facts.completionTokens,
		Model:              nullable(configJSON(cfg, "model")),
		ModelDigest:        nullable(used.modelDigest),
		NumCtx:             nullable(used.numCtx),
		Temperature:        nullable(used.temperature),
		Think:              nullable(configJSON(cfg, "think")),
		ExitCode:           exitCode,
		ToolCalls:          facts.toolCalls,
		MalformedToolCalls: facts.malformed,
		Passed:             json.RawMessage("null"),
		GraderOutput:       json.RawMessage("null"),
	}
	if err := os.MkdirAll(trialFolder, 0o777); err != nil {
		return err
	}
	var out strings.Builder
	encoder := json.NewEncoder(&out)
	encoder.SetEscapeHTML(false)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(written); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(out.String()), 0o666)
}

// nullable turns a missing JSON value into null.
func nullable(raw json.RawMessage) json.RawMessage {
	if len(raw) == 0 {
		return json.RawMessage("null")
	}
	return raw
}

// folderName returns the last name of a folder path, or "" for . and /, as Python's Path.name does.
func folderName(folder string) string {
	name := filepath.Base(folder)
	if name == "." || name == "/" {
		return ""
	}
	return name
}

// trialNumber reads the trial number from the trial folder name, or nil if it is not a number.
func trialNumber(name string) *int64 {
	if name == "" || strings.Trim(name, "0123456789") != "" {
		return nil
	}
	number, err := strconv.ParseInt(name, 10, 64)
	if err != nil {
		return nil
	}
	return &number
}

// runChat reads user lines from stdin. Each line runs the loop on the shared history.
func runChat(opts options) int {
	cfg, err := loadConfig(opts.config)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return exitCodes["infra_error"]
	}
	id, err := configID(cfg)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return exitCodes["infra_error"]
	}
	built, err := buildAgent(cfg, opts.workdir)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return exitCodes["infra_error"]
	}
	system, err := encodeJSON(textMessage{Role: "system", Content: built.systemPrompt})
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return exitCodes["infra_error"]
	}
	messages := []json.RawMessage{system}
	fmt.Printf("%s in %s. Type exit to stop.\n", id, opts.workdir)
	stop := stopOnce(built.env)
	code := chatLines(built, &messages)
	if err := stop(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		code = exitCodes["infra_error"]
	}
	return code
}

// chatLines starts the env and runs the loop once for each line of stdin.
func chatLines(built *agent, messages *[]json.RawMessage) int {
	if err := built.env.Start(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return exitCodes["infra_error"]
	}
	input := bufio.NewReader(os.Stdin)
	for {
		fmt.Print("> ")
		line, err := input.ReadString('\n')
		if err != nil && !errors.Is(err, io.EOF) {
			fmt.Fprintln(os.Stderr, err)
			return exitCodes["infra_error"]
		}
		if line == "" && errors.Is(err, io.EOF) {
			return 0
		}
		line = strings.TrimSuffix(line, "\n")
		if trimSpace(line) == "exit" {
			return 0
		}
		if trimSpace(line) == "" {
			continue
		}
		user, encodeErr := encodeJSON(textMessage{Role: "user", Content: line})
		if encodeErr != nil {
			fmt.Fprintln(os.Stderr, encodeErr)
			return exitCodes["infra_error"]
		}
		*messages = append(*messages, user)
		facts, loopErr := runLoop(built.model, built.tools, messages, built.maxTurns, built.maxSeconds, printRecord)
		if loopErr != nil {
			fmt.Fprintln(os.Stderr, loopErr)
			return exitCodes["infra_error"]
		}
		if facts.stopReason == "infra_error" {
			fmt.Fprintln(os.Stderr, facts.err)
			return exitCodes["infra_error"]
		}
	}
}

// printRecord shows one transcript record to the person at the terminal.
func printRecord(entry any) {
	switch record := entry.(type) {
	case assistantRecord:
		var thinking string
		if json.Unmarshal(record.Thinking, &thinking) == nil && thinking != "" {
			fmt.Printf("[thinking: %d characters]\n", characters(thinking))
		}
		var content string
		if json.Unmarshal(record.Content, &content) == nil && content != "" {
			fmt.Println(content)
		}
		for _, call := range record.ToolCalls {
			fmt.Printf("-> %s %s\n", call.Name, spacedJSON(call.Arguments))
		}
	case toolResultRecord:
		preview := record.Content
		if characters(preview) > resultPreviewChars {
			preview = firstCharacters(preview, resultPreviewChars) + "..."
		}
		fmt.Printf("<- %s: %s\n", record.Name, preview)
	case endRecord:
		fmt.Printf("[%s, %d turns, %s s]\n", record.StopReason, record.Turns, pythonFloat(float64(record.Seconds)))
	}
}
