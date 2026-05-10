from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from ..events.event_bus import EventBus
from ..events.event_types import Event, EventType
from .input import PromptInput

TOOL_EVENT_PREVIEW_CHARS = 120


def format_tool_preview(value, max_chars: int = TOOL_EVENT_PREVIEW_CHARS) -> str:
    text = str(value).replace("\r\n", "\\n").replace("\n", "\\n")
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}...(已截断，原始长度 {len(text)} 字符)"


class RichDisplay:
    def __init__(self, input_reader=None):
        self.console = Console()
        self.input_reader = input_reader or PromptInput()
        self.event_bus = EventBus()
        self._setup_listeners()

    def _setup_listeners(self):
        self.event_bus.subscribe(EventType.MESSAGE_RECEIVED, self._on_message_received)
        self.event_bus.subscribe(EventType.MESSAGE_SENT, self._on_message_sent)
        self.event_bus.subscribe(EventType.THINKING, self._on_thinking)
        self.event_bus.subscribe(EventType.TOOL_CALLED, self._on_tool_called)
        self.event_bus.subscribe(EventType.TOOL_RESULT, self._on_tool_result)

    def _on_message_received(self, event: Event):
        self.console.print(Panel(event.data["content"], title="[bold blue]User[/bold blue]", border_style="blue"))

    def _on_message_sent(self, event: Event):
        self.console.print(Panel(Markdown(event.data["content"]), title="[bold green]Assistant[/bold green]", border_style="green"))

    def _on_thinking(self, event: Event):
        agent_name = event.data.get("agent_name", "agent")
        content = format_tool_preview(event.data["content"])
        self.console.print(f"[cyan]💭 {agent_name} 思考: {content}[/cyan]\n")

    def _on_tool_called(self, event: Event):
        agent_name = event.data.get("agent_name", "agent")
        tool_name = event.data['name']
        tool_args = format_tool_preview(event.data['args'])
        self.console.print(f"\n[yellow]🔧 {agent_name} 调用工具: {tool_name}[/yellow]")
        self.console.print(f"[dim]   参数: {tool_args}[/dim]")

    def _on_tool_result(self, event: Event):
        agent_name = event.data.get("agent_name", "agent")
        result = format_tool_preview(event.data['result'])
        self.console.print(f"[green]✓ {agent_name} 工具结果: {result}[/green]\n")

    def print_welcome(self):
        self.console.print(Panel(
            "[bold cyan]AI 小说创作 CLI[/bold cyan]\n\n"
            "输入内容开始对话，输入 /help 查看命令。\n"
            "Tab 自动补全，↑/↓ 浏览历史，Ctrl+D 退出。",
            border_style="cyan",
        ))

    def get_input(self, prompt: str = "> ") -> str:
        return self.input_reader.get_input(prompt)
