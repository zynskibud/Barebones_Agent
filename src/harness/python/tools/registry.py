"""The tool registry: definitions, argument checks, dispatch, and truncation.

The tool definitions come from config/tools.json and go to the model
exactly as stored. Every string that the model reads comes from
config/messages.json. This module holds no tool text of its own.
"""

from collections.abc import Callable

from env.base import Env, EnvError

MAX_RESULT_CHARS = 10_000

Handler = Callable[[Env, dict, dict], str]


def text(messages: dict, key: str, **values: object) -> str:
    """Return the string at a dotted key of messages.json with its placeholders filled."""
    node = messages
    for part in key.split("."):
        node = node[part]
    return node.format(**values)


def env_error(messages: dict, error: EnvError, path: str = "") -> str:
    """Turn an EnvError into the message string that its key names.

    The message names the path that the model sent, unless the env set error.path.
    """
    named = error.path if error.path is not None else path
    return text(messages, error.key, path=named)


def check_arguments(definition: dict, arguments: object) -> str | None:
    """Return what is wrong with the arguments, or None when they fit the schema."""
    schema = definition["function"]["parameters"]
    if not isinstance(arguments, dict):
        return "arguments are not a JSON object"
    properties = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in arguments:
            return f"missing required argument {key}"
    for key, value in arguments.items():
        if key not in properties:
            if schema.get("additionalProperties") is False:
                return f"unexpected argument {key}"
            continue
        expected = properties[key].get("type")
        if expected and not fits_type(value, expected):
            return f"{key} must be a {expected}"
    return None


def fits_type(value: object, expected: str) -> bool:
    """Check one JSON schema type. A bool never counts as an integer or a number."""
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    return True


def truncate(messages: dict, result: str) -> str:
    """Keep the first MAX_RESULT_CHARS characters and add the truncation line."""
    if len(result) <= MAX_RESULT_CHARS:
        return result
    cut = len(result) - MAX_RESULT_CHARS
    return result[:MAX_RESULT_CHARS] + "\n" + text(messages, "truncated", n=cut)


class Tools:
    """The tool set for one run: the ordered definitions and the dispatch."""

    def __init__(self, definitions: list[dict], handlers: dict[str, Handler], env: Env, messages: dict) -> None:
        self.definitions = definitions
        self.env = env
        self.messages = messages
        self.by_name = {definition["function"]["name"]: definition for definition in definitions}
        self.handlers = {name: handlers[name] for name in self.by_name}

    def call(self, name: str, arguments: object) -> tuple[str, bool]:
        """Run one tool call. Return the result text and whether the call was malformed."""
        definition = self.by_name.get(name)
        if definition is None:
            return text(self.messages, "errors.unknown_tool", name=name), True
        problem = check_arguments(definition, arguments)
        if problem is not None:
            return text(self.messages, "errors.invalid_arguments", name=name, detail=problem), True
        result = self.handlers[name](self.env, self.messages, arguments)
        return truncate(self.messages, result), False
