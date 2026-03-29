import uuid
import os
from ..agent.core import AgentCore
from ..agent.session import Session
from ..llm.config import create_provider
from ..storage.session_store import SessionStore
from ..ui.rich_display import RichDisplay
from ..tools import chapter_tools, outline_tools, novel_tools, review_tools
from ..utils.logging_config import setup_logging
from ..ui.commands import CommandHandler

class CLI:
    def __init__(self):
        # 初始化日志
        os.makedirs('logs', exist_ok=True)
        setup_logging()

        self.display = RichDisplay()
        self.session_store = SessionStore()
        self.provider = create_provider()

    def run(self):
        self.display.print_welcome()

        session_id = str(uuid.uuid4())
        session = Session(session_id)
        agent = AgentCore(self.provider, session)

        command_handler = CommandHandler(self.display.console, agent)

        # 订阅事件显示思考过程
        from ..events.event_types import EventType

        def on_tool_called(event):
            self.display.console.print(f"[cyan]🔧 调用工具: {event.data['name']}[/cyan]")
            self.display.console.print(f"[dim]   参数: {event.data['args']}[/dim]")

        def on_tool_result(event):
            result = str(event.data['result'])[:150]
            self.display.console.print(f"[green]   ✓ 结果: {result}...[/green]\n")

        def on_context_compressed(event):
            self.display.console.print(f"[yellow]📦 上下文已压缩至 {event.data['count']} 条消息[/yellow]\n")

        # 清理可能存在的旧订阅
        agent.event_bus._subscribers.clear()

        agent.event_bus.subscribe(EventType.TOOL_CALLED, on_tool_called)
        agent.event_bus.subscribe(EventType.TOOL_RESULT, on_tool_result)
        agent.event_bus.subscribe(EventType.CONTEXT_COMPRESSED, on_context_compressed)

        while True:
            try:
                user_input = self.display.get_input()

                if user_input.lower() in ['exit', 'quit']:
                    self.session_store.save_session(session)
                    self.display.console.print("[yellow]Session saved. Goodbye![/yellow]")
                    break

                # 处理命令
                if command_handler.handle(user_input):
                    continue

                response = agent.chat(user_input)
                self.display.console.print(f"\n[bold blue]Assistant:[/bold blue] {response}\n")

            except KeyboardInterrupt:
                self.session_store.save_session(session)
                self.display.console.print("\n[yellow]Session saved. Goodbye![/yellow]")
                break
            except Exception as e:
                self.display.console.print(f"[red]Error: {e}[/red]")
