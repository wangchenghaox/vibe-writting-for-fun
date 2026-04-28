from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from ..events.event_bus import EventBus
from ..events.event_types import Event, EventType
from .prompt_input import PromptInput

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
        self.console.print(f"[cyan]💭 思考: {event.data['content']}[/cyan]\n")

    def _on_tool_called(self, event: Event):
        tool_name = event.data['name']
        tool_args = event.data['args']
        self.console.print(f"\n[yellow]🔧 调用工具: {tool_name}[/yellow]")
        self.console.print(f"[dim]   参数: {tool_args}[/dim]")

    def _on_tool_result(self, event: Event):
        result = str(event.data['result'])
        if len(result) > 200:
            result = result[:200] + "..."
        self.console.print(f"[green]✓ 工具结果: {result}[/green]\n")

    def print_welcome(self):
        self.console.print(Panel(
            "[bold cyan]AI 小说创作 CLI[/bold cyan]\n\n"
            "输入内容开始对话，输入 /help 查看命令。\n"
            "Tab 自动补全，↑/↓ 浏览历史，Ctrl+D 退出。",
            border_style="cyan",
        ))

    def get_input(self, prompt: str = "> ") -> str:
        return self.input_reader.get_input(prompt)
