package main

// Text and JSON helpers that keep the output the same as the Python harness.
// Python's json module and str methods do these things by default. Go needs them written out.

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"os"
	"strconv"
	"strings"
	"unicode"
	"unicode/utf8"

	"barebones/harness/env"
)

// encodeJSON writes one value as compact JSON. It keeps <, >, and & as they are,
// as Python does, and adds no newline at the end.
func encodeJSON(item any) ([]byte, error) {
	var out bytes.Buffer
	encoder := json.NewEncoder(&out)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(item); err != nil {
		return nil, err
	}
	return bytes.TrimSuffix(out.Bytes(), []byte("\n")), nil
}

// normalizeJSON writes raw JSON again in compact form. Keys keep their order,
// numbers keep their text, and strings are written the way encodeJSON writes them.
func normalizeJSON(raw json.RawMessage) (json.RawMessage, error) {
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	var out bytes.Buffer
	// Each open object or array holds a count of its items, and whether it is an object.
	type level struct {
		object bool
		items  int
	}
	var stack []level
	for {
		token, err := decoder.Token()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return nil, err
		}
		if delim, ok := token.(json.Delim); ok && (delim == '}' || delim == ']') {
			stack = stack[:len(stack)-1]
			out.WriteByte(byte(delim))
			continue
		}
		if len(stack) > 0 {
			top := &stack[len(stack)-1]
			switch {
			case top.object && top.items%2 == 1:
				out.WriteByte(':')
			case top.items > 0:
				out.WriteByte(',')
			}
			top.items++
		}
		switch item := token.(type) {
		case json.Delim:
			out.WriteByte(byte(item))
			stack = append(stack, level{object: item == '{'})
		case json.Number:
			out.WriteString(item.String())
		case string:
			text, err := encodeJSON(item)
			if err != nil {
				return nil, err
			}
			out.Write(text)
		case bool:
			out.WriteString(strconv.FormatBool(item))
		case nil:
			out.WriteString("null")
		}
	}
	return out.Bytes(), nil
}

// spacedJSON adds a space after each : and , outside strings, as Python's json.dumps writes.
func spacedJSON(compact []byte) string {
	var out strings.Builder
	inString, escaped := false, false
	for _, char := range compact {
		out.WriteByte(char)
		switch {
		case inString && escaped:
			escaped = false
		case inString && char == '\\':
			escaped = true
		case char == '"':
			inString = !inString
		case !inString && (char == ':' || char == ','):
			out.WriteByte(' ')
		}
	}
	return out.String()
}

// pythonFloat writes a float as Python's repr does, for example 0.6, 5.0, or 1e-05.
func pythonFloat(number float64) string {
	if math.IsInf(number, 0) || math.IsNaN(number) {
		// Python writes these too, although they are not valid JSON.
		switch {
		case math.IsNaN(number):
			return "NaN"
		case number > 0:
			return "Infinity"
		}
		return "-Infinity"
	}
	scientific := strconv.FormatFloat(number, 'e', -1, 64)
	mark := strings.LastIndexByte(scientific, 'e')
	exponent, _ := strconv.Atoi(scientific[mark+1:])
	if exponent < -4 || exponent >= 16 {
		return scientific
	}
	plain := strconv.FormatFloat(number, 'f', -1, 64)
	if !strings.ContainsRune(plain, '.') {
		plain += ".0"
	}
	return plain
}

// roundSeconds rounds to one decimal, as Python's round(x, 1) does.
func roundSeconds(seconds float64) float64 {
	rounded, _ := strconv.ParseFloat(strconv.FormatFloat(seconds, 'f', 1, 64), 64)
	return rounded
}

// pyFloat is a float that JSON writes as Python does, for example 42.0 and not 42.
type pyFloat float64

func (f pyFloat) MarshalJSON() ([]byte, error) {
	return []byte(pythonFloat(float64(f))), nil
}

// isPythonSpace reports whether Python's str.strip removes the character.
func isPythonSpace(char rune) bool {
	return unicode.IsSpace(char) || (char >= 0x1c && char <= 0x1f)
}

// trimRight removes trailing whitespace, as Python's str.rstrip does.
func trimRight(text string) string {
	return strings.TrimRightFunc(text, isPythonSpace)
}

// trimSpace removes whitespace at both ends, as Python's str.strip does.
func trimSpace(text string) string {
	return strings.TrimFunc(text, isPythonSpace)
}

// readText reads a UTF-8 text file the way Python's read_text does:
// invalid UTF-8 is an error, and \r\n and \r become \n.
func readText(path string) (string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	if !utf8.Valid(data) {
		return "", fmt.Errorf("%s is not valid UTF-8", path)
	}
	return env.TranslateNewlines(string(data)), nil
}

// characters counts the characters (code points) in text, as Python's len does.
func characters(text string) int {
	return utf8.RuneCountInString(text)
}

// firstCharacters returns the first count characters of text.
func firstCharacters(text string, count int) string {
	end := 0
	for index := 0; index < count && end < len(text); index++ {
		_, size := utf8.DecodeRuneInString(text[end:])
		end += size
	}
	return text[:end]
}
