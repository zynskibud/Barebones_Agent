package env

// The local env: runs on the laptop.
//
// Every path goes through a safePath check that keeps the agent inside one
// working folder. Tools call this file and never touch the disk directly.

import (
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
	"syscall"
	"time"
)

// Local holds files and commands on this machine, inside one working folder.
type Local struct {
	root string
	// mount is a folder name that stands for the working folder, for example
	// /work in the docker env. The local env has none.
	mount string
}

// NewLocal checks the working folder and returns the env.
// The local env needs no time limit, so it ignores maxSeconds.
func NewLocal(workdir string, maxSeconds float64) (*Local, error) {
	root, err := resolveFolder(workdir)
	if err != nil {
		return nil, err
	}
	return &Local{root: root}, nil
}

// resolveFolder returns the real absolute path of a working folder that exists.
func resolveFolder(workdir string) (string, error) {
	absolute, err := filepath.Abs(workdir)
	if err != nil {
		return "", err
	}
	root := realPath(absolute)
	info, err := os.Stat(root)
	if err != nil || !info.IsDir() {
		return "", fmt.Errorf("the working folder %s does not exist", workdir)
	}
	return root, nil
}

func (l *Local) Start() error { return nil }

func (l *Local) Stop() error { return nil }

// safePath resolves a path inside the working folder. It follows .. and symlinks.
func (l *Local) safePath(path string) (string, error) {
	if l.mount != "" && (path == l.mount || strings.HasPrefix(path, l.mount+"/")) {
		path = "." + path[len(l.mount):]
	}
	joined := path
	if !strings.HasPrefix(path, "/") {
		joined = l.root + "/" + path
	}
	target := realPath(joined)
	if target != l.root && !strings.HasPrefix(target, l.root+"/") {
		return "", newError(KeyOutsideFolder, path)
	}
	return target, nil
}

// filePrefix returns the first prefix of path that is a file, spelled as the model sent it.
// For a.py/x that is a.py. It returns the whole path if no prefix is a file.
func (l *Local) filePrefix(path string) string {
	parts := strings.Split(path, "/")
	for count := 1; count < len(parts); count++ {
		prefix := strings.Join(parts[:count], "/")
		if prefix == "" {
			continue
		}
		candidate, err := l.safePath(prefix)
		if err != nil {
			continue
		}
		info, err := os.Stat(candidate)
		if err == nil && !info.IsDir() {
			return prefix
		}
	}
	return path
}

func (l *Local) Read(path string) (string, error) {
	target, err := l.safePath(path)
	if err != nil {
		return "", err
	}
	info, statErr := os.Stat(target)
	if statErr == nil && info.IsDir() {
		return "", newError(KeyIsDirectory, path)
	}
	if statErr != nil || !info.Mode().IsRegular() {
		return "", newError(KeyNotFound, path)
	}
	data, err := os.ReadFile(target)
	if err != nil {
		return "", err
	}
	return TranslateNewlines(DecodeText(data)), nil
}

func (l *Local) Write(path, text string) error {
	target, err := l.safePath(path)
	if err != nil {
		return err
	}
	err = os.MkdirAll(filepath.Dir(target), 0o777)
	if err == nil {
		err = os.WriteFile(target, []byte(text), 0o666)
	}
	if errors.Is(err, syscall.EEXIST) || errors.Is(err, syscall.ENOTDIR) {
		// A parent of the path is a file, for example a.py in a.py/x.
		prefix := l.filePrefix(path)
		return &Error{Key: KeyNotDirectory, Detail: path, Path: &prefix}
	}
	return err
}

func (l *Local) List(path string) ([]string, error) {
	target, err := l.safePath(path)
	if err != nil {
		return nil, err
	}
	info, err := os.Stat(target)
	if err != nil {
		return nil, newError(KeyNotFound, path)
	}
	if !info.IsDir() {
		return nil, newError(KeyNotDirectory, path)
	}
	entries, err := os.ReadDir(target)
	if err != nil {
		return nil, err
	}
	names := make([]string, 0, len(entries))
	for _, entry := range entries {
		name := entry.Name()
		// Stat follows symlinks, so a link to a folder counts as a folder.
		if info, err := os.Stat(filepath.Join(target, name)); err == nil && info.IsDir() {
			name += "/"
		}
		names = append(names, name)
	}
	sort.Strings(names)
	return names, nil
}

func (l *Local) Run(command string, timeoutSeconds float64) (string, string, int, error) {
	cmd := exec.Command("bash", "-c", command)
	cmd.Dir = l.root
	// The command gets its own session, so a timeout can kill every process it started.
	// Its stdin is /dev/null (cmd.Stdin is nil) and its output goes to pipes of this
	// harness, so it never holds the stdin, stdout, or stderr of the harness.
	done, err := runProcess(cmd, seconds(timeoutSeconds), true)
	if err != nil {
		return "", "", 0, err
	}
	if done.timedOut {
		return "", "", 0, newError(KeyTimeout, command)
	}
	return commandText(done.stdout), commandText(done.stderr), done.code, nil
}

// commandText decodes command output as Python text mode does.
func commandText(data []byte) string {
	return TranslateNewlines(DecodeText(data))
}

// finished is the outcome of one process.
type finished struct {
	stdout   []byte
	stderr   []byte
	code     int
	elapsed  time.Duration
	timedOut bool
}

// runProcess starts cmd and captures stdout and stderr separately. stdin is /dev/null.
//
// It waits until the process exits and both pipes reach end of file. On a timeout,
// it kills the process, waits for it, and closes the pipes, so a child that keeps
// the pipes open cannot block it. With ownSession, the process starts in a new
// session, and the timeout kills its whole process group.
func runProcess(cmd *exec.Cmd, timeout time.Duration, ownSession bool) (finished, error) {
	var result finished
	outRead, outWrite, err := os.Pipe()
	if err != nil {
		return result, err
	}
	errRead, errWrite, err := os.Pipe()
	if err != nil {
		outRead.Close()
		outWrite.Close()
		return result, err
	}
	cmd.Stdout = outWrite
	cmd.Stderr = errWrite
	if ownSession {
		cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	}
	started := time.Now()
	err = cmd.Start()
	outWrite.Close()
	errWrite.Close()
	if err != nil {
		outRead.Close()
		errRead.Close()
		return result, err
	}
	stdout := readAll(outRead)
	stderr := readAll(errRead)
	exited := make(chan error, 1)
	go func() { exited <- cmd.Wait() }()
	timer := time.NewTimer(timeout)
	defer timer.Stop()
	pending := 3
	processDone := false
	for pending > 0 {
		select {
		case result.stdout = <-stdout:
			pending--
		case result.stderr = <-stderr:
			pending--
		case <-exited:
			processDone = true
			pending--
		case <-timer.C:
			if ownSession {
				killGroup(cmd)
			} else {
				_ = cmd.Process.Kill()
			}
			if !processDone {
				<-exited
			}
			outRead.Close()
			errRead.Close()
			result.timedOut = true
			result.elapsed = time.Since(started)
			return result, nil
		}
	}
	outRead.Close()
	errRead.Close()
	result.elapsed = time.Since(started)
	result.code = exitCode(cmd.ProcessState)
	return result, nil
}

// readAll reads a pipe to the end in the background and sends the bytes once.
func readAll(pipe io.Reader) <-chan []byte {
	out := make(chan []byte, 1)
	go func() {
		data, _ := io.ReadAll(pipe)
		out <- data
	}()
	return out
}

// killGroup kills the command and every process in its group.
// The caller waits for the command.
func killGroup(cmd *exec.Cmd) {
	if cmd.Process == nil {
		return
	}
	// The process runs in its own session, so its group id is its pid.
	_ = syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
}

// exitCode returns the exit code the way Python reports it: minus the signal for a killed process.
func exitCode(state *os.ProcessState) int {
	if status, ok := state.Sys().(syscall.WaitStatus); ok && status.Signaled() {
		return -int(status.Signal())
	}
	return state.ExitCode()
}

// seconds turns a number of seconds into a duration.
func seconds(value float64) time.Duration {
	return time.Duration(value * float64(time.Second))
}

// realPath resolves a path the way Python's os.path.realpath does with strict=False.
// It works left to right, follows each symlink, and applies .. to the resolved path.
// A part that does not exist is kept as it is.
func realPath(path string) string {
	resolved, _ := joinReal("", path, map[string]*string{})
	if !strings.HasPrefix(resolved, "/") {
		if wd, err := os.Getwd(); err == nil {
			resolved = wd + "/" + resolved
		}
	}
	return filepath.Clean(resolved)
}

// joinReal joins rest to the resolved path. seen holds the links in progress (nil)
// and the links already resolved. It reports false when it finds a symlink loop.
func joinReal(path, rest string, seen map[string]*string) (string, bool) {
	if strings.HasPrefix(rest, "/") {
		rest = rest[1:]
		path = "/"
	}
	for rest != "" {
		var name string
		name, rest, _ = strings.Cut(rest, "/")
		if name == "" || name == "." {
			continue
		}
		if name == ".." {
			if path == "" {
				path = ".."
				continue
			}
			head, tail := splitPath(path)
			path = head
			if tail == ".." {
				path = joinPath(joinPath(path, ".."), "..")
			}
			continue
		}
		next := joinPath(path, name)
		info, err := os.Lstat(next)
		if err != nil || info.Mode()&os.ModeSymlink == 0 {
			path = next
			continue
		}
		if known, ok := seen[next]; ok {
			if known != nil {
				path = *known
				continue
			}
			// A symlink loop: stop resolving here.
			return joinPath(next, rest), false
		}
		seen[next] = nil
		link, err := os.Readlink(next)
		if err != nil {
			path = next
			continue
		}
		var ok bool
		path, ok = joinReal(path, link, seen)
		if !ok {
			return joinPath(path, rest), false
		}
		resolved := path
		seen[next] = &resolved
	}
	return path, true
}

// splitPath splits a path into the folder and the last name, as Python's posixpath.split does.
func splitPath(path string) (string, string) {
	index := strings.LastIndex(path, "/") + 1
	head, tail := path[:index], path[index:]
	if head != "" && strings.Trim(head, "/") != "" {
		head = strings.TrimRight(head, "/")
	}
	return head, tail
}

// joinPath joins two path parts, as Python's posixpath.join does.
func joinPath(path, name string) string {
	switch {
	case strings.HasPrefix(name, "/"):
		return name
	case path == "" || strings.HasSuffix(path, "/"):
		return path + name
	default:
		return path + "/" + name
	}
}
