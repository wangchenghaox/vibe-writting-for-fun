import inspect
from typing import Callable, Dict, Any, List

_tool_registry: Dict[str, Dict[str, Any]] = {}

def tool(name: str, description: str):
    def decorator(func: Callable):
        sig = inspect.signature(func)
        params = {}

        for param_name, param in sig.parameters.items():
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

        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": params,
                    "required": list(params.keys())
                }
            }
        }

        _tool_registry[name] = {
            "schema": schema,
            "func": func
        }

        return func
    return decorator

def get_tool_schemas() -> List[Dict[str, Any]]:
    return [t["schema"] for t in _tool_registry.values()]

def execute_tool(name: str, arguments: Dict[str, Any]) -> Any:
    if name not in _tool_registry:
        raise ValueError(f"Tool {name} not found")
    return _tool_registry[name]["func"](**arguments)
