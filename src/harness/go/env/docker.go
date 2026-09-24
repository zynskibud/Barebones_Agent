package env

// The docker env: bash runs inside a Docker container.
//
// The container mounts the host working folder at /work. The container and
// the host see the same files, so the eval harness grades the host folder.
//
//   - Read, Write, List: act on the host folder with the safePath check of the
//     local env. bash sees the working folder as /work, so safePath first maps
//     a path that starts with /work to the working folder.
//   - Run: docker exec bash -c <command> in /work. GNU timeout in the container
//     kills the command and every process it started.
//   - Start, Stop: the container lives while its docker run client holds stdin
//     open. If the harness dies, even by SIGKILL, the pipe closes, the container
//     stops, and --rm removes it.
//
// Build the image once, from the repo root: docker build -t barebones-task docker/

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"time"
)

const (
	image = "barebones-task"
	mount = "/work"
	// Resource limits for every container, so that runs are comparable.
	cpus   = "2"
	memory = "2g"
	// The longest wait for one docker command and for the container to start, in seconds.
	dockerSeconds = 30
	pollInterval  = 100 * time.Millisecond
	// How long the host waits for docker exec after the command timeout, in seconds.
	execGraceSeconds = 10
	// timeout --signal KILL kills its whole process group, itself included,
	// so docker exec exits with 128 + 9 when the command runs past the timeout.
	killed = 137
)

// Docker holds files on the host folder and runs commands in a container that mounts it.
type Docker struct {
	*Local
	name string
	// keeper is the docker run client. The container lives while its stdin is open.
	keeper      *exec.Cmd
	keeperStdin io.WriteCloser
	keeperDone  chan struct{}
	keeperErr   *bytes.Buffer
}

// NewDocker checks the working folder and returns the env.
// The docker env needs no run time limit, so it ignores maxSeconds.
func NewDocker(workdir string, maxSeconds float64) (*Docker, error) {
	local, err := NewLocal(workdir, maxSeconds)
	if err != nil {
		return nil, err
	}
	local.mount = mount
	suffix := make([]byte, 6)
	if _, err := rand.Read(suffix); err != nil {
		return nil, err
	}
	return &Docker{Local: local, name: "barebones-" + hex.EncodeToString(suffix)}, nil
}

func (d *Docker) Start() error {
	found := docker("image", "inspect", "--format", "{{.Id}}", image)
	if found.code != 0 {
		if strings.Contains(found.stderr, "No such image") {
			return fmt.Errorf("the docker image %s does not exist. "+
				"Build it from the repo root: docker build -t %s docker/", image, image)
		}
		return fmt.Errorf("docker failed: %s", lastLine(found.stderr))
	}
	keeper := exec.Command("docker", "run", "--rm", "--interactive", "--init", "--pull", "never",
		"--name", d.name,
		"--cpus", cpus, "--memory", memory,
		"--volume", d.root+":"+mount, "--workdir", mount,
		image, "cat")
	stdin, err := keeper.StdinPipe()
	if err != nil {
		return err
	}
	// The keeper stays in the process group of the harness, so a kill of that
	// group kills it too. Its stdout is /dev/null and its stderr goes to a buffer.
	d.keeperErr = &bytes.Buffer{}
	keeper.Stderr = d.keeperErr
	if err := keeper.Start(); err != nil {
		return err
	}
	d.keeper = keeper
	d.keeperStdin = stdin
	d.keeperDone = make(chan struct{})
	go func() {
		_ = keeper.Wait()
		close(d.keeperDone)
	}()
	return d.waitUntilRunning()
}

// waitUntilRunning returns when the container runs. It removes the container
// and returns an error if the container does not start.
func (d *Docker) waitUntilRunning() error {
	deadline := time.Now().Add(dockerSeconds * time.Second)
	for time.Now().Before(deadline) {
		if d.keeperExited() {
			<-d.keeperDone
			detail := lastLine(d.keeperErr.String())
			_ = d.Stop()
			return fmt.Errorf("the container did not start: %s", detail)
		}
		state := docker("inspect", "--format", "{{.State.Running}}", d.name)
		if strings.TrimSpace(state.stdout) == "true" {
			return nil
		}
		time.Sleep(pollInterval)
	}
	_ = d.Stop()
	return fmt.Errorf("the container did not start within %d seconds", dockerSeconds)
}

// keeperExited reports whether the docker run client has ended.
func (d *Docker) keeperExited() bool {
	select {
	case <-d.keeperDone:
		return true
	default:
		return false
	}
}

// Stop removes the container. A second call does nothing.
func (d *Docker) Stop() error {
	keeper := d.keeper
	if keeper == nil {
		return nil
	}
	d.keeper = nil
	removed := docker("rm", "--force", d.name)
	if removed.code != 0 && !strings.Contains(removed.stderr, "No such container") {
		fmt.Fprintf(os.Stderr, "could not remove the container %s: %s\n", d.name, lastLine(removed.stderr))
	}
	_ = d.keeperStdin.Close()
	select {
	case <-d.keeperDone:
	case <-time.After(dockerSeconds * time.Second):
		_ = keeper.Process.Kill()
		<-d.keeperDone
	}
	return nil
}

func (d *Docker) Run(command string, timeoutSeconds float64) (string, string, int, error) {
	if d.keeper == nil || d.keeperExited() {
		return "", "", 0, fmt.Errorf("the container %s is not running", d.name)
	}
	limit := strconv.FormatFloat(timeoutSeconds, 'g', -1, 64)
	// GNU timeout kills the command group inside the container. The docker exec
	// client stays in the process group of the harness, with stdin from /dev/null.
	cmd := exec.Command("docker", "exec", d.name, "timeout", "--signal", "KILL", limit, "bash", "-c", command)
	done, err := runProcess(cmd, seconds(timeoutSeconds+execGraceSeconds), false)
	if err != nil {
		return "", "", 0, err
	}
	if done.timedOut {
		return "", "", 0, newError(KeyTimeout, command)
	}
	if done.code == killed && done.elapsed >= seconds(timeoutSeconds) {
		return "", "", 0, newError(KeyTimeout, command)
	}
	return commandText(done.stdout), commandText(done.stderr), done.code, nil
}

// dockerResult is the outcome of one docker command.
type dockerResult struct {
	code   int
	stdout string
	stderr string
}

// docker runs one docker command and returns the result. It never fails.
func docker(args ...string) dockerResult {
	ctx, cancel := context.WithTimeout(context.Background(), dockerSeconds*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "docker", args...)
	cmd.WaitDelay = time.Second
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	err := cmd.Run()
	if errors.Is(err, exec.ErrNotFound) {
		return dockerResult{code: 127, stderr: "the docker command is not on PATH"}
	}
	if ctx.Err() != nil {
		return dockerResult{code: 1, stderr: fmt.Sprintf("docker %s did not answer in %d seconds", args[0], dockerSeconds)}
	}
	code := 0
	if err != nil {
		var exitErr *exec.ExitError
		if !errors.As(err, &exitErr) {
			return dockerResult{code: 1, stderr: err.Error()}
		}
		code = exitCode(exitErr.ProcessState)
	}
	return dockerResult{code: code, stdout: stdout.String(), stderr: stderr.String()}
}

// lastLine returns the last line of a docker error, or a note when there is none.
func lastLine(text string) string {
	lines := strings.Split(strings.TrimSpace(text), "\n")
	if last := strings.TrimSpace(lines[len(lines)-1]); last != "" {
		return last
	}
	return "no error text"
}
