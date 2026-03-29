from datetime import datetime
from typing import List, Dict, Any, Optional

class Session:
    def __init__(self, session_id: str):
        self.id = session_id
        self.messages: List[Dict[str, Any]] = []
        self.context: Dict[str, Any] = {}
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at

    def add_message(self, role: str, content: str, **kwargs):
        msg = {"role": role, "content": content}
        # 特殊处理 tool_calls - 确保格式正确
        if "tool_calls" in kwargs and kwargs["tool_calls"]:
            # 只保留必要字段
            cleaned_tool_calls = []
            for tc in kwargs["tool_calls"]:
                cleaned_tc = {
                    "id": tc["id"],
                    "type": tc.get("type", "function"),
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"]
                    }
                }
                cleaned_tool_calls.append(cleaned_tc)
            msg["tool_calls"] = cleaned_tool_calls
        else:
            # 其他 kwargs 直接添加
            for k, v in kwargs.items():
                if k != "tool_calls":
                    msg[k] = v

        self.messages.append(msg)
        self.updated_at = datetime.now().isoformat()

    def get_messages(self) -> List[Dict[str, Any]]:
        return self.messages

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "context": self.context,
            "messages": self.messages
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Session':
        session = cls(data["id"])
        session.created_at = data["created_at"]
        session.updated_at = data["updated_at"]
        session.context = data.get("context", {})
        session.messages = data.get("messages", [])
        return session
