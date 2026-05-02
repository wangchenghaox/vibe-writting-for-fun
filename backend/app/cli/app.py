import uuid
import os
import errno
from ..agent.core import AgentCore
from ..agent.session import Session
from ..db.init import init_db
from ..llm.config import create_provider
from ..memory.event_recorder import MemoryEventRecorder
from ..storage.session_store import SessionStore
from .display import RichDisplay
from .. import tools as _tools  # noqa: F401 - import registers tool decorators
from ..utils.logging_config import setup_logging
from .commands import CommandHandler

class CLI:
    def __init__(self):
        # 初始化日志
        os.makedirs('logs', exist_ok=True)
        setup_logging()
        init_db()

        self.display = RichDisplay()
        self.session_store = SessionStore()
        self.provider = create_provider()

    def run(self):
        self.display.print_welcome()

        session_id = str(uuid.uuid4())
        session = Session(session_id)
        session.context["user_id"] = 0
        session.context["novel_id"] = os.getenv("CURRENT_NOVEL_ID", "default")
        session.context["agent_name"] = "main"
        session.context["agent_instance_id"] = session_id
        agent = AgentCore(
            self.provider,
            session,
            tool_context=dict(session.context),
            memory_recorder=MemoryEventRecorder(
                user_id=0,
                novel_id=session.context["novel_id"],
                agent_name="main",
                agent_instance_id=session_id,
                session_id=session_id,
            ),
        )

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

        subscriptions = (
            (EventType.TOOL_CALLED, on_tool_called),
            (EventType.TOOL_RESULT, on_tool_result),
            (EventType.CONTEXT_COMPRESSED, on_context_compressed),
        )
        for event_type, callback in subscriptions:
            agent.event_bus.subscribe(event_type, callback)

        def cleanup_subscriptions():
            unsubscribe = getattr(agent.event_bus, "unsubscribe", None)
            if unsubscribe is None:
                return
            for event_type, callback in subscriptions:
                try:
                    unsubscribe(event_type, callback)
                except ValueError:
                    pass

        while True:
            try:
                user_input = self.display.get_input().strip()

                if not user_input:
                    continue

                if user_input.lower() in ['exit', 'quit']:
                    self.session_store.save_session(session)
                    self.display.console.print("[yellow]Session saved. Goodbye![/yellow]")
                    cleanup_subscriptions()
                    break

                # 处理命令
                if command_handler.handle(user_input):
                    continue

                started_response = False
                for chunk in agent.chat_stream(user_input):
                    if not started_response:
                        self.display.console.print("\n[bold blue]Assistant:[/bold blue] ", end="")
                        started_response = True
                    self.display.console.print(chunk, end="")
                if started_response:
                    self.display.console.print("\n")

            except EOFError:
                self.session_store.save_session(session)
                self.display.console.print("\n[yellow]Session saved. Goodbye![/yellow]")
                cleanup_subscriptions()
                break
            except KeyboardInterrupt:
                self.display.console.print("\n[yellow]已取消输入，按 Ctrl+D 或输入 exit 退出。[/yellow]")
            except OSError as e:
                if e.errno == errno.EINVAL:
                    self.session_store.save_session(session)
                    self.display.console.print("\n[yellow]检测到非交互式输入，Session saved. Goodbye![/yellow]")
                    cleanup_subscriptions()
                    break
                self.display.console.print(f"[red]Error: {e}[/red]")
            except Exception as e:
                self.display.console.print(f"[red]Error: {e}[/red]")
