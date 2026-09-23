"""Talk to the model through Ollama.

This is the model seam (a value seam). The model is a tag string
and a think flag, not a separate class per model.
"""

import json
import urllib.error
import urllib.request

DEFAULT_URL = "http://localhost:11434"


class ModelError(Exception):
    """Ollama is unreachable or gave a bad answer. The loop reports infra_error."""


class Model:
    """One Ollama chat model: the tag, the think flag, and the options to send."""

    def __init__(
        self,
        name: str,
        think: bool,
        num_ctx: int | None = None,
        temperature: float | None = None,
        url: str = DEFAULT_URL,
        timeout: float = 600,
    ) -> None:
        self.name = name
        self.think = think
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.url = url.rstrip("/")
        self.timeout = timeout

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        """POST /api/chat once and return the response body."""
        body: dict = {
            "model": self.name,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "think": self.think,
        }
        options = {}
        if self.num_ctx is not None:
            options["num_ctx"] = self.num_ctx
        if self.temperature is not None:
            options["temperature"] = self.temperature
        if options:
            body["options"] = options
        response = post(self.url + "/api/chat", body, self.timeout)
        if "message" not in response:
            raise ModelError(f"no message in the Ollama response: {json.dumps(response)[:500]}")
        return response

    def digest(self) -> str | None:
        """Return the model digest from /api/tags, or None if the tag is not listed."""
        for entry in get(self.url + "/api/tags", self.timeout).get("models", []):
            if entry.get("name") == self.name or entry.get("model") == self.name:
                return entry.get("digest")
        return None

    def default_parameters(self) -> dict[str, str]:
        """Return the model's own parameters from /api/show, for example temperature."""
        response = post(self.url + "/api/show", {"model": self.name}, self.timeout)
        parameters = {}
        for line in response.get("parameters", "").splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                parameters[parts[0]] = parts[1].strip()
        return parameters

    def loaded_context_length(self) -> int | None:
        """Return the context length of the loaded model from /api/ps, or None if not loaded."""
        for entry in get(self.url + "/api/ps", self.timeout).get("models", []):
            if entry.get("name") == self.name or entry.get("model") == self.name:
                return entry.get("context_length")
        return None


def post(url: str, body: dict, timeout: float) -> dict:
    """Send a JSON POST and return the parsed JSON reply."""
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    return send(request, timeout)


def get(url: str, timeout: float) -> dict:
    """Send a GET and return the parsed JSON reply."""
    return send(urllib.request.Request(url), timeout)


def send(request: urllib.request.Request, timeout: float) -> dict:
    """Send one request. Turn every transport or format problem into a ModelError."""
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise ModelError(f"HTTP {error.code} from {request.full_url}: {detail}") from None
    except (urllib.error.URLError, OSError) as error:
        raise ModelError(f"cannot reach {request.full_url}: {error}") from None
    try:
        parsed = json.loads(raw)
    except ValueError:
        raise ModelError(f"no JSON in the reply from {request.full_url}") from None
    if isinstance(parsed, dict) and "error" in parsed:
        raise ModelError(f"Ollama error: {parsed['error']}")
    return parsed
