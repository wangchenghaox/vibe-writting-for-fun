import inspect
from typing import Callable, Dict, Any, List, Optional, Sequence

_tool_registry: Dict[str, Dict[str, Any]] = {}

def tool(name: str, description: str, context_params: Optional[Sequence[str]] = None):
    def decorator(func: Callable):
        sig = inspect.signature(func)
        params = {}
        required = []
        hidden_context_params = set(context_params or [])

        for param_name, param in sig.parameters.items():
            if param_name in hidden_context_params:
                continue

            param_type = "string"
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_type = "integer"
                elif param.annotation == bool:
                    param_type = "boolean"

            params[param_name] = {
                "type": param_type,
                "description": f"Parameter {param_name}"
            }
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": params,
                    "required": required
                }
            }
        }

        _tool_registry[name] = {
            "schema": schema,
            "func": func,
            "signature": sig,
            "context_params": hidden_context_params
        }

        return func
    return decorator

def get_tool_schemas(allowed_names: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    if allowed_names is None:
        return [t["schema"] for t in _tool_registry.values()]

    allowed = set(allowed_names)
    return [
        entry["schema"]
        for name, entry in _tool_registry.items()
        if name in allowed
    ]

def execute_tool(name: str, arguments: Dict[str, Any], context: Dict[str, Any] = None) -> Any:
    if name not in _tool_registry:
        raise ValueError(f"Tool {name} not found")
    entry = _tool_registry[name]
    call_args = dict(arguments)

    if context:
        for key in entry.get("context_params", set()):
            if key in context and key in entry["signature"].parameters:
                call_args[key] = context[key]

        for key, value in context.items():
            if (
                key not in entry.get("context_params", set())
                and key in entry["signature"].parameters
                and (key not in call_args or call_args[key] in (None, ""))
            ):
                call_args[key] = value

    return entry["func"](**call_args)
