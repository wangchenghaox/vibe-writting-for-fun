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
        command_handler = CommandHandler(self.display.console)

        session_id = str(uuid.uuid4())
        session = Session(session_id)
        agent = AgentCore(self.provider, session)

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

                agent.chat(user_input)

            except KeyboardInterrupt:
                self.session_store.save_session(session)
                self.display.console.print("\n[yellow]Session saved. Goodbye![/yellow]")
                break
            except Exception as e:
                self.display.console.print(f"[red]Error: {e}[/red]")
