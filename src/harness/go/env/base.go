// Package env holds the Env interface: what every environment offers the tools.
//
// An env is the place where the tools act: the laptop, a Docker container,
// or a cloud sandbox. The tools call the methods below and nothing else.
//
// Every env receives the host working folder path. The env is responsible
// for making that folder visible to itself, for example by mounting it.
//
// Paths are the strings that the model sent. The env resolves each path and
// keeps it inside the working folder. When a path or a command has a problem,
// the env returns an *Error. Its Key names the string in config/messages.json
// that the tool returns to the model. Any other error is a harness failure.
package env

import (
	"strings"
	"unicode/utf8"
)

// The keys in config/messages.json that an *Error can name.
const (
	KeyOutsideFolder = "errors.outside_folder"
	KeyNotFound      = "errors.not_found"
	KeyIsDirectory   = "errors.is_directory"
	KeyNotDirectory  = "errors.not_a_directory"
	KeyTimeout       = "errors.timeout"
)

// Env is the interface. Each env fills in every method.
type Env interface {
	// Start sets up the env. It does nothing for envs that need no setup.
	Start() error
	// Stop tears down the env. A second call does nothing.
	Stop() error
	// Read returns the text of a file.
	Read(path string) (string, error)
	// Write writes text to a file. It creates the file and its parent folders if needed.
	Write(path, text string) error
	// List returns the sorted names in a folder. Folder names end with /.
	List(path string) ([]string, error)
	// Run runs a shell command in the working folder and returns stdout, stderr, and the exit code.
	Run(command string, timeoutSeconds float64) (string, string, int, error)
}

// Error is a problem that the tool reports to the model as text.
//
// Path is the path to name in the message when it differs from the path that
// the model sent. For example, edit_file on a.py/x names the file a.py.
// When Path is nil, the tool names the path that the model sent.
type Error struct {
	Key    string
	Detail string
	Path   *string
}

func (e *Error) Error() string {
	return e.Key + ": " + e.Detail
}

func newError(key, detail string) *Error {
	return &Error{Key: key, Detail: detail}
}

// DecodeText turns bytes into text the way Python decodes UTF-8 with errors="replace".
// Each maximal invalid part becomes one U+FFFD, so the character count matches Python.
func DecodeText(data []byte) string {
	if utf8.Valid(data) {
		return string(data)
	}
	var out strings.Builder
	for len(data) > 0 {
		r, size := utf8.DecodeRune(data)
		if r != utf8.RuneError || size > 1 {
			out.Write(data[:size])
			data = data[size:]
			continue
		}
		out.WriteRune(utf8.RuneError)
		data = data[invalidLength(data):]
	}
	return out.String()
}

// invalidLength returns how many bytes Python replaces with one U+FFFD at the start of data.
// That is the lead byte plus the continuation bytes that were valid so far.
func invalidLength(data []byte) int {
	lead := data[0]
	var need int
	low, high := byte(0x80), byte(0xBF)
	switch {
	case lead >= 0xC2 && lead <= 0xDF:
		need = 1
	case lead == 0xE0:
		need, low = 2, 0xA0
	case lead >= 0xE1 && lead <= 0xEC, lead == 0xEE, lead == 0xEF:
		need = 2
	case lead == 0xED:
		need, high = 2, 0x9F
	case lead == 0xF0:
		need, low = 3, 0x90
	case lead >= 0xF1 && lead <= 0xF3:
		need = 3
	case lead == 0xF4:
		need, high = 3, 0x8F
	default:
		return 1
	}
	size := 1
	for size <= need && size < len(data) {
		next := data[size]
		if size > 1 {
			low, high = 0x80, 0xBF
		}
		if next < low || next > high {
			break
		}
		size++
	}
	return size
}

// TranslateNewlines changes \r\n and \r to \n, as Python text mode does when it reads.
func TranslateNewlines(text string) string {
	if !strings.Contains(text, "\r") {
		return text
	}
	text = strings.ReplaceAll(text, "\r\n", "\n")
	return strings.ReplaceAll(text, "\r", "\n")
}
