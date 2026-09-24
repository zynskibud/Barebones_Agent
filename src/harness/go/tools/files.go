package tools

// The file tools: read_file, list_files, edit_file.
//
// This is part of the tools seam (a behavior seam).
// Each tool calls env, never the machine directly.

import (
	"errors"
	"strings"

	"barebones/harness/env"
)

// ReadFile returns the text of one file.
func ReadFile(e env.Env, messages *Messages, arguments map[string]any) (string, error) {
	path := stringArgument(arguments, "path", "")
	text, err := e.Read(path)
	if err != nil {
		return envProblem(messages, err, path)
	}
	return text, nil
}

// ListFiles returns the names in one folder, one per line. Not recursive. Dotfiles are hidden.
func ListFiles(e env.Env, messages *Messages, arguments map[string]any) (string, error) {
	path := stringArgument(arguments, "path", ".")
	names, err := e.List(path)
	if err != nil {
		return envProblem(messages, err, path)
	}
	shown := make([]string, 0, len(names))
	for _, name := range names {
		if !strings.HasPrefix(name, ".") {
			shown = append(shown, name)
		}
	}
	return strings.Join(shown, "\n"), nil
}

// EditFile replaces old_str once in a file, or creates the file when old_str is empty.
func EditFile(e env.Env, messages *Messages, arguments map[string]any) (string, error) {
	path := stringArgument(arguments, "path", "")
	old := stringArgument(arguments, "old_str", "")
	replacement := stringArgument(arguments, "new_str", "")
	if old == "" {
		return createFile(e, messages, path, replacement)
	}
	current, err := e.Read(path)
	if err != nil {
		return envProblem(messages, err, path)
	}
	switch strings.Count(current, old) {
	case 0:
		return messages.Text("errors.old_str_not_found", "path", path), nil
	case 1:
	default:
		return messages.Text("errors.old_str_multiple", "path", path), nil
	}
	if err := e.Write(path, strings.Replace(current, old, replacement, 1)); err != nil {
		return envProblem(messages, err, path)
	}
	return messages.Text("ok.edited", "path", path), nil
}

// createFile creates a file that does not exist yet.
func createFile(e env.Env, messages *Messages, path, content string) (string, error) {
	_, err := e.Read(path)
	if err == nil {
		return messages.Text("errors.already_exists", "path", path), nil
	}
	var problem *env.Error
	if !errors.As(err, &problem) || problem.Key != env.KeyNotFound {
		return envProblem(messages, err, path)
	}
	if err := e.Write(path, content); err != nil {
		return envProblem(messages, err, path)
	}
	return messages.Text("ok.created", "path", path), nil
}

// envProblem turns an env error into the result text for the model.
// Any other error is a harness failure and goes back to the loop.
func envProblem(messages *Messages, err error, path string) (string, error) {
	var problem *env.Error
	if errors.As(err, &problem) {
		return EnvError(messages, problem, path), nil
	}
	return "", err
}
