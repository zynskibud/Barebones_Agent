package env

// The cloud env: runs in an E2B cloud sandbox (a Firecracker microVM).
//
// The harness and the model stay on this machine. Only the tools act in the sandbox.
// There is no shared folder, so the sandbox copy is the single source of truth
// while the agent works:
//
//   - Start creates the sandbox and uploads the host working folder to workRoot.
//   - Read, Write, List, and Run act on the sandbox copy only.
//   - Stop downloads workRoot back into the host working folder, so that the
//     eval harness can grade it on the host, and then kills the sandbox.
//
// safePath is pure path logic: it normalizes the path against workRoot and
// rejects any path that leaves it. It does not follow symlinks, because there is
// no host folder to resolve against. The sandbox is the boundary. The host is
// protected at Stop: the download skips every member that would land outside
// the host working folder.
//
// E2B has no Go SDK. This file talks to E2B with the standard library, the same
// way the Python SDK does: the E2B REST API creates, extends, and kills the
// sandbox, and the envd service in the sandbox reads and writes files (plain
// HTTP on /files) and runs commands (Connect RPC with JSON).
//
// The API key comes from E2B_API_KEY in the environment, or else from the
// E2B_API_KEY line in .env at the repo root. This file never prints it.

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"context"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"mime/multipart"
	"net/http"
	"net/url"
	"os"
	pathpkg "path"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"time"
)

const (
	// The E2B template with the three task toolchains. cloud/README.md says how to build it.
	template        = "barebones-agent"
	workRoot        = "/home/user/work"
	uploadArchive   = "/tmp/barebones-upload.tar.gz"
	downloadArchive = "/tmp/barebones-download.tar.gz"
	// The sandbox timeout is max_seconds plus this grace. The eval harness kills a
	// stuck harness at max_seconds + 60, so the sandbox outlives the harness. If the
	// harness dies before Stop, E2B kills the sandbox at this timeout.
	sandboxGraceSeconds = 120
	// The commands that the env runs for itself (upload, download, checks) get this timeout.
	setupSeconds = 120
	// The time limit for one REST call or one file transfer.
	requestSeconds = 60
	defaultDomain  = "e2b.app"
	envdPort       = "49983"
	// The sandbox user for the agent's files and commands, and the user for the download.
	sandboxUser = "user"
	rootUser    = "root"
)

// Build output that stays in the sandbox. The download at Stop leaves it out.
var downloadExcludes = []string{"target", "__pycache__", ".pytest_cache", "node_modules"}

var metadata = map[string]string{"app": "barebones-agent"}

// Cloud holds files and commands in one E2B sandbox, inside one working folder.
type Cloud struct {
	hostRoot       string
	sandboxSeconds int
	keyFile        string
	domain         string
	apiKey         string
	client         *http.Client
	sandbox        *sandbox
	refreshed      time.Time
}

// sandbox is one running E2B sandbox.
type sandbox struct {
	id          string
	envdURL     string
	accessToken string
}

// NewCloud checks the working folder and returns the env.
// keyFile is the .env file that can hold E2B_API_KEY.
func NewCloud(workdir string, maxSeconds float64, keyFile string) (*Cloud, error) {
	root, err := resolveFolder(workdir)
	if err != nil {
		return nil, err
	}
	domain := os.Getenv("E2B_DOMAIN")
	if domain == "" {
		domain = defaultDomain
	}
	return &Cloud{
		hostRoot:       root,
		sandboxSeconds: int(maxSeconds + sandboxGraceSeconds),
		keyFile:        keyFile,
		domain:         domain,
		client:         &http.Client{},
	}, nil
}

// Start creates the sandbox from the template and uploads the working folder.
func (c *Cloud) Start() error {
	if c.sandbox != nil {
		return nil
	}
	key, err := apiKey(c.keyFile)
	if err != nil {
		return err
	}
	c.apiKey = key
	created, err := c.create()
	if err != nil {
		return err
	}
	c.sandbox = created
	c.refreshed = time.Now()
	if err := c.upload(); err != nil {
		// A failed start must not leak the sandbox.
		c.kill()
		return err
	}
	return nil
}

// Stop downloads the working folder to the host, then kills the sandbox. A second call does nothing.
func (c *Cloud) Stop() error {
	if c.sandbox == nil {
		return nil
	}
	err := c.download()
	c.kill()
	return err
}

// safePath returns the sandbox path under workRoot, or an error if it leaves.
func (c *Cloud) safePath(path string) (string, error) {
	target := pathpkg.Clean(path)
	if !strings.HasPrefix(path, "/") {
		target = pathpkg.Clean(workRoot + "/" + path)
	}
	if target != workRoot && !strings.HasPrefix(target, workRoot+"/") {
		return "", newError(KeyOutsideFolder, path)
	}
	return target, nil
}

func (c *Cloud) Read(path string) (string, error) {
	target, err := c.safePath(path)
	if err != nil {
		return "", err
	}
	if err := c.keepAlive(); err != nil {
		return "", err
	}
	data, status, err := c.readFile(target, sandboxUser)
	if err != nil {
		return "", err
	}
	if status == http.StatusNotFound {
		return "", newError(KeyNotFound, path)
	}
	if status != http.StatusOK {
		kind, err := c.kind(target)
		switch {
		case err != nil:
			return "", err
		case kind == "dir":
			return "", newError(KeyIsDirectory, path)
		case kind == "":
			return "", newError(KeyNotFound, path)
		}
		return "", fmt.Errorf("cloud env: cannot read %s: HTTP %d: %s", target, status, firstLine(data))
	}
	return DecodeText(data), nil
}

func (c *Cloud) Write(path, text string) error {
	target, err := c.safePath(path)
	if err != nil {
		return err
	}
	if err := c.keepAlive(); err != nil {
		return err
	}
	// The sandbox creates the parent folders.
	status, detail, err := c.writeFile(target, []byte(text), sandboxUser)
	if err != nil {
		return err
	}
	if status == http.StatusOK {
		return nil
	}
	// A parent of the path is a file, for example a.py in a.py/x.
	prefix, found, err := c.filePrefix(path)
	if err != nil {
		return err
	}
	if !found {
		return fmt.Errorf("cloud env: cannot write %s: HTTP %d: %s", target, status, detail)
	}
	return &Error{Key: KeyNotDirectory, Detail: path, Path: &prefix}
}

// filePrefix returns the first prefix of path that is a file, spelled as the model sent it.
// For a.py/x that is a.py. found is false if no prefix is a file.
func (c *Cloud) filePrefix(path string) (string, bool, error) {
	parts := strings.Split(path, "/")
	for count := 1; count < len(parts); count++ {
		prefix := strings.Join(parts[:count], "/")
		if prefix == "" {
			continue
		}
		target, err := c.safePath(prefix)
		if err != nil {
			continue
		}
		kind, err := c.kind(target)
		if err != nil {
			return "", false, err
		}
		if kind == "file" {
			return prefix, true, nil
		}
	}
	return "", false, nil
}

func (c *Cloud) List(path string) ([]string, error) {
	target, err := c.safePath(path)
	if err != nil {
		return nil, err
	}
	if err := c.keepAlive(); err != nil {
		return nil, err
	}
	var reply struct {
		Entries []struct {
			Name string `json:"name"`
			Type string `json:"type"`
		} `json:"entries"`
	}
	failure, err := c.unary("/filesystem.Filesystem/ListDir", sandboxUser,
		map[string]any{"path": target, "depth": 1}, &reply)
	if err != nil {
		return nil, err
	}
	if failure != nil {
		if failure.Code == "not_found" {
			return nil, newError(KeyNotFound, path)
		}
		kind, err := c.kind(target)
		switch {
		case err != nil:
			return nil, err
		case kind == "":
			return nil, newError(KeyNotFound, path)
		case kind != "dir":
			return nil, newError(KeyNotDirectory, path)
		}
		return nil, fmt.Errorf("cloud env: cannot list %s: %s", target, failure)
	}
	sort.Slice(reply.Entries, func(i, j int) bool { return reply.Entries[i].Name < reply.Entries[j].Name })
	names := make([]string, 0, len(reply.Entries))
	for _, entry := range reply.Entries {
		name := entry.Name
		if entry.Type == "FILE_TYPE_DIRECTORY" {
			name += "/"
		}
		names = append(names, name)
	}
	return names, nil
}

func (c *Cloud) Run(command string, timeoutSeconds float64) (string, string, int, error) {
	if err := c.keepAlive(); err != nil {
		return "", "", 0, err
	}
	// E2B runs every command as /bin/bash -l -c <cmd> in the process group
	// of its daemon. exec setsid gives bash -c its own process group, with
	// the group id equal to the handle pid, so that a timeout can kill the group.
	wrapped := "exec setsid bash -c " + shellQuote(command)
	done, err := c.command(wrapped, workRoot, sandboxUser, timeoutSeconds)
	if err != nil {
		return "", "", 0, err
	}
	if done.timedOut {
		// The E2B timeout ends the stream only. The command keeps running.
		if err := c.killGroup(done.pid); err != nil {
			return "", "", 0, err
		}
		return "", "", 0, newError(KeyTimeout, command)
	}
	return DecodeText(done.stdout), DecodeText(done.stderr), done.code, nil
}

// upload copies every file under the host working folder to workRoot.
func (c *Cloud) upload() error {
	archive, err := packFolder(c.hostRoot)
	if err != nil {
		return err
	}
	status, detail, err := c.writeFile(uploadArchive, archive, sandboxUser)
	if err != nil {
		return err
	}
	if status != http.StatusOK {
		return fmt.Errorf("cloud env: cannot upload the working folder: HTTP %d: %s", status, detail)
	}
	return c.setupCommand(fmt.Sprintf("mkdir -p %s && tar -xzf %s -C %s && rm %s",
		workRoot, uploadArchive, workRoot, uploadArchive), sandboxUser)
}

// download replaces the host working folder contents with workRoot.
//
// Host files that the agent deleted in the sandbox are deleted on the host.
// The host folder changes only after the whole archive is extracted.
// Build output (downloadExcludes) stays in the sandbox.
func (c *Cloud) download() error {
	excludes := make([]string, 0, len(downloadExcludes))
	for _, name := range downloadExcludes {
		excludes = append(excludes, "--exclude="+shellQuote(name))
	}
	err := c.setupCommand(fmt.Sprintf("tar -czf %s -C %s %s .",
		downloadArchive, workRoot, strings.Join(excludes, " ")), rootUser)
	if err != nil {
		return err
	}
	data, status, err := c.readFile(downloadArchive, rootUser)
	if err != nil {
		return err
	}
	if status != http.StatusOK {
		return fmt.Errorf("cloud env: cannot download the working folder: HTTP %d: %s", status, firstLine(data))
	}
	staging, err := os.MkdirTemp("", "barebones-download-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(staging)
	staging = realPath(staging)
	if err := unpackArchive(data, staging); err != nil {
		return err
	}
	return replaceContents(c.hostRoot, staging)
}

// kind returns "dir", "file", or "" when the sandbox path does not exist.
//
// Only the error paths call this. A shell test follows symlinks like the
// local env, and it answers for every path (for example a path under a
// file, where the E2B file API gives an internal error).
func (c *Cloud) kind(target string) (string, error) {
	quoted := shellQuote(target)
	done, err := c.command(fmt.Sprintf("if [ -d %s ]; then echo dir; elif [ -e %s ]; then echo file; fi",
		quoted, quoted), "", sandboxUser, setupSeconds)
	if err != nil {
		return "", err
	}
	if done.timedOut || done.code != 0 {
		return "", fmt.Errorf("cloud env: the path check for %s failed", target)
	}
	return strings.TrimSpace(string(done.stdout)), nil
}

// killGroup kills the command and every process in its group.
// A nonzero exit means the group ended on its own.
func (c *Cloud) killGroup(pid int64) error {
	done, err := c.command(fmt.Sprintf("kill -9 -- -%d", pid), "", sandboxUser, setupSeconds)
	if err != nil {
		return err
	}
	if done.timedOut {
		return fmt.Errorf("cloud env: the kill of process group %d did not finish", pid)
	}
	return nil
}

// setupCommand runs one command that the env needs. A nonzero exit is an error.
func (c *Cloud) setupCommand(command, user string) error {
	done, err := c.command(command, "", user, setupSeconds)
	if err != nil {
		return err
	}
	if done.timedOut {
		return fmt.Errorf("cloud env: %q ran longer than %d seconds", command, setupSeconds)
	}
	if done.code != 0 {
		return fmt.Errorf("cloud env: %q exited with code %d: %s", command, done.code, firstLine(done.stderr))
	}
	return nil
}

// keepAlive pushes the sandbox timeout forward when half of it has passed (for long chats).
func (c *Cloud) keepAlive() error {
	if c.sandbox == nil {
		return errors.New("cloud env: the sandbox is not running")
	}
	if time.Since(c.refreshed).Seconds() <= float64(c.sandboxSeconds)/2 {
		return nil
	}
	body := map[string]int{"timeout": c.sandboxSeconds}
	if _, err := c.api(http.MethodPost, "/sandboxes/"+c.sandbox.id+"/timeout", body); err != nil {
		return err
	}
	c.refreshed = time.Now()
	return nil
}

// kill kills the sandbox and forgets it.
//
// A failed kill does not fail the run: the work is already on the host,
// and E2B kills the sandbox at its timeout.
func (c *Cloud) kill() {
	running := c.sandbox
	c.sandbox = nil
	if running == nil {
		return
	}
	if _, err := c.api(http.MethodDelete, "/sandboxes/"+running.id, nil); err != nil {
		fmt.Fprintf(os.Stderr, "cloud env: could not kill sandbox %s: %v\n", running.id, err)
	}
}

// create asks the E2B API for a new sandbox from the template.
func (c *Cloud) create() (*sandbox, error) {
	body := map[string]any{
		"templateID": template,
		"timeout":    c.sandboxSeconds,
		"metadata":   metadata,
		"envVars":    map[string]string{},
	}
	raw, err := c.api(http.MethodPost, "/v2/sandboxes", body)
	if err != nil {
		return nil, err
	}
	var reply struct {
		SandboxID       string  `json:"sandboxID"`
		EnvdAccessToken *string `json:"envdAccessToken"`
		Domain          *string `json:"domain"`
	}
	if err := json.Unmarshal(raw, &reply); err != nil || reply.SandboxID == "" {
		return nil, fmt.Errorf("cloud env: a bad reply from the E2B API: %s", firstLine(raw))
	}
	domain := c.domain
	if reply.Domain != nil && *reply.Domain != "" {
		domain = *reply.Domain
	}
	created := &sandbox{id: reply.SandboxID, envdURL: "https://" + envdPort + "-" + reply.SandboxID + "." + domain}
	if reply.EnvdAccessToken != nil {
		created.accessToken = *reply.EnvdAccessToken
	}
	return created, nil
}

// api sends one call to the E2B REST API and returns the body of a successful reply.
func (c *Cloud) api(method, path string, body any) ([]byte, error) {
	var payload io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		payload = bytes.NewReader(data)
	}
	ctx, cancel := context.WithTimeout(context.Background(), requestSeconds*time.Second)
	defer cancel()
	request, err := http.NewRequestWithContext(ctx, method, "https://api."+c.domain+path, payload)
	if err != nil {
		return nil, err
	}
	request.Header.Set("X-API-KEY", c.apiKey)
	if body != nil {
		request.Header.Set("Content-Type", "application/json")
	}
	response, err := c.client.Do(request)
	if err != nil {
		return nil, fmt.Errorf("cloud env: cannot reach the E2B API: %w", err)
	}
	defer response.Body.Close()
	raw, err := io.ReadAll(response.Body)
	if err != nil {
		return nil, err
	}
	if response.StatusCode >= 300 {
		return nil, fmt.Errorf("cloud env: E2B API %s %s: HTTP %d: %s", method, path, response.StatusCode, firstLine(raw))
	}
	return raw, nil
}

// envdRequest builds one request to the envd service in the sandbox.
func (c *Cloud) envdRequest(ctx context.Context, method, path string, query url.Values, body io.Reader) (*http.Request, error) {
	address := c.sandbox.envdURL + path
	if len(query) > 0 {
		address += "?" + query.Encode()
	}
	request, err := http.NewRequestWithContext(ctx, method, address, body)
	if err != nil {
		return nil, err
	}
	request.Header.Set("E2b-Sandbox-Id", c.sandbox.id)
	request.Header.Set("E2b-Sandbox-Port", envdPort)
	if c.sandbox.accessToken != "" {
		request.Header.Set("X-Access-Token", c.sandbox.accessToken)
	}
	return request, nil
}

// readFile reads one sandbox file. It returns the body and the HTTP status.
func (c *Cloud) readFile(target, user string) ([]byte, int, error) {
	ctx, cancel := context.WithTimeout(context.Background(), requestSeconds*time.Second)
	defer cancel()
	query := url.Values{"path": {target}, "username": {user}}
	request, err := c.envdRequest(ctx, http.MethodGet, "/files", query, nil)
	if err != nil {
		return nil, 0, err
	}
	response, err := c.client.Do(request)
	if err != nil {
		return nil, 0, fmt.Errorf("cloud env: cannot reach the sandbox: %w", err)
	}
	defer response.Body.Close()
	data, err := io.ReadAll(response.Body)
	if err != nil {
		return nil, 0, err
	}
	return data, response.StatusCode, nil
}

// writeFile writes one sandbox file as a multipart upload. It returns the HTTP status
// and, on a failure, the error text.
func (c *Cloud) writeFile(target string, data []byte, user string) (int, string, error) {
	var body bytes.Buffer
	form := multipart.NewWriter(&body)
	part, err := form.CreateFormFile("file", target)
	if err != nil {
		return 0, "", err
	}
	if _, err := part.Write(data); err != nil {
		return 0, "", err
	}
	if err := form.Close(); err != nil {
		return 0, "", err
	}
	ctx, cancel := context.WithTimeout(context.Background(), requestSeconds*time.Second)
	defer cancel()
	query := url.Values{"path": {target}, "username": {user}}
	request, err := c.envdRequest(ctx, http.MethodPost, "/files", query, &body)
	if err != nil {
		return 0, "", err
	}
	request.Header.Set("Content-Type", form.FormDataContentType())
	response, err := c.client.Do(request)
	if err != nil {
		return 0, "", fmt.Errorf("cloud env: cannot reach the sandbox: %w", err)
	}
	defer response.Body.Close()
	raw, err := io.ReadAll(response.Body)
	if err != nil {
		return 0, "", err
	}
	if response.StatusCode >= 300 {
		return response.StatusCode, firstLine(raw), nil
	}
	return http.StatusOK, "", nil
}

// connectError is the error that a Connect RPC returns.
type connectError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func (e *connectError) String() string {
	return e.Code + ": " + e.Message
}

// basicUser is the Authorization header that envd reads for the user of an RPC.
func basicUser(user string) string {
	return "Basic " + base64.StdEncoding.EncodeToString([]byte(user+":"))
}

// unary sends one unary Connect RPC with JSON. It returns the RPC error, if any.
func (c *Cloud) unary(method, user string, body, reply any) (*connectError, error) {
	data, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	ctx, cancel := context.WithTimeout(context.Background(), requestSeconds*time.Second)
	defer cancel()
	request, err := c.envdRequest(ctx, http.MethodPost, method, nil, bytes.NewReader(data))
	if err != nil {
		return nil, err
	}
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("Connect-Protocol-Version", "1")
	request.Header.Set("Authorization", basicUser(user))
	response, err := c.client.Do(request)
	if err != nil {
		return nil, fmt.Errorf("cloud env: cannot reach the sandbox: %w", err)
	}
	defer response.Body.Close()
	raw, err := io.ReadAll(response.Body)
	if err != nil {
		return nil, err
	}
	if response.StatusCode != http.StatusOK {
		failure := &connectError{Code: "unknown", Message: firstLine(raw)}
		_ = json.Unmarshal(raw, failure)
		return failure, nil
	}
	return nil, json.Unmarshal(raw, reply)
}

// commandResult is the outcome of one sandbox command.
type commandResult struct {
	pid      int64
	stdout   []byte
	stderr   []byte
	code     int
	timedOut bool
}

// command runs /bin/bash -l -c <command> in the sandbox through the Start RPC,
// which streams the process events. An empty cwd means the user's home folder.
func (c *Cloud) command(command, cwd, user string, timeoutSeconds float64) (commandResult, error) {
	var done commandResult
	process := map[string]any{"cmd": "/bin/bash", "args": []string{"-l", "-c", command}, "envs": map[string]string{}}
	if cwd != "" {
		process["cwd"] = cwd
	}
	// stdin false gives the command no input stream, as the Python SDK asks. Without it
	// envd keeps stdin open, and a command that reads stdin waits until the timeout.
	message, err := json.Marshal(map[string]any{"process": process, "stdin": false})
	if err != nil {
		return done, err
	}
	envelope := make([]byte, 5, 5+len(message))
	binary.BigEndian.PutUint32(envelope[1:], uint32(len(message)))
	envelope = append(envelope, message...)
	timeout := time.Duration(timeoutSeconds * float64(time.Second))
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	request, err := c.envdRequest(ctx, http.MethodPost, "/process.Process/Start", nil, bytes.NewReader(envelope))
	if err != nil {
		return done, err
	}
	request.Header.Set("Content-Type", "application/connect+json")
	request.Header.Set("Connect-Protocol-Version", "1")
	request.Header.Set("Connect-Timeout-Ms", strconv.FormatInt(timeout.Milliseconds(), 10))
	request.Header.Set("Keepalive-Ping-Interval", "50")
	request.Header.Set("Authorization", basicUser(user))
	response, err := c.client.Do(request)
	if err != nil {
		if ctx.Err() != nil {
			done.timedOut = true
			return done, nil
		}
		return done, fmt.Errorf("cloud env: cannot reach the sandbox: %w", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		raw, _ := io.ReadAll(response.Body)
		return done, fmt.Errorf("cloud env: the command did not start: HTTP %d: %s", response.StatusCode, firstLine(raw))
	}
	ended, err := readEvents(response.Body, &done)
	if err != nil {
		if ctx.Err() != nil {
			done.timedOut = true
			return done, nil
		}
		return done, err
	}
	if !ended {
		return done, errors.New("cloud env: the command ended without an end event")
	}
	return done, nil
}

// readEvents reads the Connect stream of process events into done.
// It reports whether the stream held the end event.
func readEvents(stream io.Reader, done *commandResult) (bool, error) {
	ended := false
	header := make([]byte, 5)
	for {
		if _, err := io.ReadFull(stream, header); err != nil {
			if errors.Is(err, io.EOF) {
				return ended, nil
			}
			return ended, err
		}
		body := make([]byte, binary.BigEndian.Uint32(header[1:]))
		if _, err := io.ReadFull(stream, body); err != nil {
			return ended, err
		}
		if header[0]&0b10 != 0 {
			// The end of the stream. It can carry an RPC error.
			var last struct {
				Error *connectError `json:"error"`
			}
			_ = json.Unmarshal(body, &last)
			if last.Error != nil {
				return ended, fmt.Errorf("cloud env: the command failed: %s", last.Error)
			}
			return ended, nil
		}
		var message struct {
			Event struct {
				Start *struct {
					Pid int64 `json:"pid"`
				} `json:"start"`
				Data *struct {
					Stdout []byte `json:"stdout"`
					Stderr []byte `json:"stderr"`
				} `json:"data"`
				End *struct {
					ExitCode int `json:"exitCode"`
				} `json:"end"`
			} `json:"event"`
		}
		if err := json.Unmarshal(body, &message); err != nil {
			return ended, fmt.Errorf("cloud env: a bad process event: %w", err)
		}
		event := message.Event
		switch {
		case event.Start != nil:
			done.pid = event.Start.Pid
		case event.Data != nil:
			done.stdout = append(done.stdout, event.Data.Stdout...)
			done.stderr = append(done.stderr, event.Data.Stderr...)
		case event.End != nil:
			done.code = event.End.ExitCode
			ended = true
		}
	}
}

// packFolder returns a gzip tar of the folder, with the names under ".".
func packFolder(root string) ([]byte, error) {
	var out bytes.Buffer
	zipped := gzip.NewWriter(&out)
	archive := tar.NewWriter(zipped)
	err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		info, err := entry.Info()
		if err != nil {
			return err
		}
		if info.Mode()&fs.ModeSocket != 0 {
			return nil
		}
		link := ""
		if info.Mode()&fs.ModeSymlink != 0 {
			if link, err = os.Readlink(path); err != nil {
				return err
			}
		}
		header, err := tar.FileInfoHeader(info, link)
		if err != nil {
			return err
		}
		relative, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		header.Name = "./" + filepath.ToSlash(relative)
		if relative == "." {
			header.Name = "./"
		} else if info.IsDir() {
			header.Name += "/"
		}
		if err := archive.WriteHeader(header); err != nil {
			return err
		}
		if !info.Mode().IsRegular() {
			return nil
		}
		file, err := os.Open(path)
		if err != nil {
			return err
		}
		defer file.Close()
		_, err = io.Copy(archive, file)
		return err
	})
	if err != nil {
		return nil, err
	}
	if err := archive.Close(); err != nil {
		return nil, err
	}
	if err := zipped.Close(); err != nil {
		return nil, err
	}
	return out.Bytes(), nil
}

// unpackArchive extracts a gzip tar into dest with the rules of Python's tarfile data filter.
// It skips a member that would land outside dest, with a note on stderr.
func unpackArchive(data []byte, dest string) error {
	zipped, err := gzip.NewReader(bytes.NewReader(data))
	if err != nil {
		return err
	}
	archive := tar.NewReader(zipped)
	type folderTime struct {
		path string
		time time.Time
	}
	var folders []folderTime
	for {
		header, err := archive.Next()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return err
		}
		target, problem := checkMember(header, dest)
		if problem != "" {
			fmt.Fprintf(os.Stderr, "cloud env: skipped %s in the download: %s\n", header.Name, problem)
			continue
		}
		if err := extractMember(archive, header, target, dest); err != nil {
			return err
		}
		if header.Typeflag == tar.TypeDir {
			folders = append(folders, folderTime{target, header.ModTime})
		}
	}
	// Folder times are set last, because each file inside changes them.
	for index := len(folders) - 1; index >= 0; index-- {
		_ = os.Chtimes(folders[index].path, folders[index].time, folders[index].time)
	}
	return nil
}

// checkMember returns where a member lands, or why the data filter rejects it.
func checkMember(header *tar.Header, dest string) (string, string) {
	name := strings.TrimLeft(header.Name, "/")
	target := realPath(filepath.Join(dest, name))
	if !inside(target, dest) {
		return "", fmt.Sprintf("%s would be extracted to %s, which is outside the destination", header.Name, target)
	}
	switch header.Typeflag {
	case tar.TypeReg, tar.TypeDir:
		return target, ""
	case tar.TypeSymlink, tar.TypeLink:
		if strings.HasPrefix(header.Linkname, "/") {
			return "", fmt.Sprintf("%s is a link to an absolute path", header.Name)
		}
		linkTarget := filepath.Join(dest, header.Linkname)
		if header.Typeflag == tar.TypeSymlink {
			linkTarget = filepath.Join(dest, filepath.Dir(name), header.Linkname)
		}
		if resolved := realPath(linkTarget); !inside(resolved, dest) {
			return "", fmt.Sprintf("%s would link to %s, which is outside the destination", header.Name, resolved)
		}
		return target, ""
	}
	return "", fmt.Sprintf("%s is a special file", header.Name)
}

// inside reports whether target is dest or a path under it.
func inside(target, dest string) bool {
	return target == dest || strings.HasPrefix(target, dest+"/")
}

// extractMember writes one checked member at target.
func extractMember(archive io.Reader, header *tar.Header, target, dest string) error {
	if err := os.MkdirAll(filepath.Dir(target), 0o777); err != nil {
		return err
	}
	switch header.Typeflag {
	case tar.TypeDir:
		if err := os.Mkdir(target, 0o777); err != nil && !errors.Is(err, fs.ErrExist) {
			return err
		}
		return nil
	case tar.TypeSymlink:
		return os.Symlink(header.Linkname, target)
	case tar.TypeLink:
		return os.Link(filepath.Join(dest, header.Linkname), target)
	}
	// A regular file: no high bits and no group or other write. The owner can read and write.
	mode := fs.FileMode(header.Mode) & 0o755
	if mode&0o100 == 0 {
		mode &^= 0o111
	}
	mode |= 0o600
	file, err := os.OpenFile(target, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, mode)
	if err != nil {
		return err
	}
	if _, err := io.Copy(file, archive); err != nil {
		file.Close()
		return err
	}
	if err := file.Close(); err != nil {
		return err
	}
	if err := os.Chmod(target, mode); err != nil {
		return err
	}
	return os.Chtimes(target, header.ModTime, header.ModTime)
}

// replaceContents deletes every entry in root and moves every entry of staging into root.
func replaceContents(root, staging string) error {
	entries, err := os.ReadDir(root)
	if err != nil {
		return err
	}
	for _, entry := range entries {
		if err := os.RemoveAll(filepath.Join(root, entry.Name())); err != nil {
			return err
		}
	}
	entries, err = os.ReadDir(staging)
	if err != nil {
		return err
	}
	for _, entry := range entries {
		from, to := filepath.Join(staging, entry.Name()), filepath.Join(root, entry.Name())
		err := os.Rename(from, to)
		if errors.Is(err, syscall.EXDEV) {
			// Another disk: copy, as Python's shutil.move does.
			err = copyTree(from, to)
		}
		if err != nil {
			return err
		}
	}
	return nil
}

// copyTree copies a file, a symlink, or a folder tree.
func copyTree(from, to string) error {
	return filepath.WalkDir(from, func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		relative, err := filepath.Rel(from, path)
		if err != nil {
			return err
		}
		target := filepath.Join(to, relative)
		info, err := entry.Info()
		if err != nil {
			return err
		}
		switch {
		case info.Mode()&fs.ModeSymlink != 0:
			link, err := os.Readlink(path)
			if err != nil {
				return err
			}
			return os.Symlink(link, target)
		case info.IsDir():
			return os.MkdirAll(target, info.Mode().Perm())
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		if err := os.WriteFile(target, data, info.Mode().Perm()); err != nil {
			return err
		}
		return os.Chtimes(target, info.ModTime(), info.ModTime())
	})
}

// apiKey returns E2B_API_KEY from the environment, or else from the .env file.
func apiKey(keyFile string) (string, error) {
	if key := os.Getenv("E2B_API_KEY"); key != "" {
		return key, nil
	}
	if data, err := os.ReadFile(keyFile); err == nil {
		for _, line := range strings.Split(string(data), "\n") {
			name, value, found := strings.Cut(line, "=")
			if found && strings.TrimSpace(name) == "E2B_API_KEY" {
				return strings.Trim(strings.TrimSpace(value), `'"`), nil
			}
		}
	}
	return "", errors.New("E2B_API_KEY is not set. Set it in the environment or in .env at the repo root")
}

var shellSafe = regexp.MustCompile(`^[A-Za-z0-9_@%+=:,./-]+$`)

// shellQuote quotes a string for a POSIX shell, as Python's shlex.quote does.
func shellQuote(text string) string {
	if text == "" {
		return "''"
	}
	if shellSafe.MatchString(text) {
		return text
	}
	return "'" + strings.ReplaceAll(text, "'", `'"'"'`) + "'"
}

// firstLine returns the first line of a reply, for an error message.
func firstLine(data []byte) string {
	text := strings.TrimSpace(DecodeText(data))
	if line, _, found := strings.Cut(text, "\n"); found {
		return line
	}
	return text
}
