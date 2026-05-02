from pathlib import Path
from rich.table import Table
from .input import COMMANDS

class CommandHandler:
    def __init__(self, console, agent=None, workdir=None):
        self.console = console
        self.agent = agent
        self.workdir = Path(workdir).resolve(strict=False) if workdir else None

    def handle(self, command: str) -> bool:
        """处理命令，返回 True 表示已处理"""
        if not command.startswith('/'):
            return False

        parts = command.split()
        cmd = parts[0][1:]  # 去掉 /

        if cmd == "current":
            self._show_current()
        elif cmd == "help":
            self._show_help()
        else:
            self.console.print(f"[red]未知命令: {cmd}[/red]")
            self._show_help()

        return True

    def _show_current(self):
        """显示当前 sandbox"""
        workdir = self.workdir
        if workdir is None and self.agent:
            context_workdir = self.agent.tool_context.get("workdir")
            workdir = Path(context_workdir).resolve(strict=False) if context_workdir else None
        if workdir is None:
            self.console.print("[yellow]未设置工作 sandbox[/yellow]")
            return

        self.console.print("\n[bold cyan]当前 sandbox:[/bold cyan]")
        self.console.print(f"  Workdir: {workdir}\n")
        self.console.print()

    def _show_help(self):
        """显示帮助信息"""
        table = Table(title="可用命令", show_header=True, header_style="bold cyan")
        table.add_column("命令", style="cyan", no_wrap=True)
        table.add_column("说明")
        for command, description in COMMANDS.items():
            table.add_row(command, description)
        self.console.print()
        self.console.print(table)
        self.console.print()
