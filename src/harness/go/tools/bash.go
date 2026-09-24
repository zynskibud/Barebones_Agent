package tools

// The bash tool: run one shell command.
//
// This is part of the tools seam (a behavior seam).
// The tool calls env, never the machine directly.

import (
	"strconv"
	"strings"

	"barebones/harness/env"
)

// TimeoutSeconds is the time limit for one command.
const TimeoutSeconds = 30

// Bash runs the command. It returns stdout, then stderr, then the exit code line.
func Bash(e env.Env, messages *Messages, arguments map[string]any) (string, error) {
	stdout, stderr, code, err := e.Run(stringArgument(arguments, "command", ""), TimeoutSeconds)
	if err != nil {
		return envProblem(messages, err, "")
	}
	return withNewline(stdout) + withNewline(stderr) + messages.Text("exit_code", "n", strconv.Itoa(code)), nil
}

// withNewline returns the part with one newline at the end. An empty part stays empty.
func withNewline(part string) string {
	if part == "" || strings.HasSuffix(part, "\n") {
		return part
	}
	return part + "\n"
}
