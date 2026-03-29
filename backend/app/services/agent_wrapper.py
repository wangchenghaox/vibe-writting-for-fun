import subprocess
import json

class SimpleAgent:
    def __init__(self, novel_id: str):
        self.novel_id = novel_id

    def chat(self, message: str, websocket):
        """使用subprocess调用ai-agent-core"""
        try:
            # 简单回复，暂不集成复杂的Agent
            return f"AI回复: {message}"
        except Exception as e:
            return f"错误: {str(e)}"
