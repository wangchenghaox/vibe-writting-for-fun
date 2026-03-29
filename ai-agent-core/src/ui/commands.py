import os
from pathlib import Path
import json

class CommandHandler:
    def __init__(self, console):
        self.console = console
        self.novels_dir = Path("data/novels")

    def handle(self, command: str) -> bool:
        """处理命令，返回 True 表示已处理"""
        if not command.startswith('/'):
            return False

        parts = command.split()
        cmd = parts[0][1:]  # 去掉 /

        if cmd == "list":
            self._list_novels()
        elif cmd == "load" and len(parts) > 1:
            self._load_novel(parts[1])
        elif cmd == "current":
            self._show_current()
        elif cmd == "chapters":
            self._list_chapters()
        elif cmd == "help":
            self._show_help()
        else:
            self.console.print(f"[red]未知命令: {cmd}[/red]")
            self._show_help()

        return True

    def _list_novels(self):
        """列出所有小说"""
        if not self.novels_dir.exists():
            self.console.print("[yellow]暂无小说[/yellow]")
            return

        self.console.print("\n[bold cyan]📚 小说列表:[/bold cyan]")
        for novel_dir in self.novels_dir.iterdir():
            if novel_dir.is_dir():
                meta_file = novel_dir / "meta.json"
                if meta_file.exists():
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    self.console.print(f"  • {meta['id']}: {meta['title']}")
        self.console.print()

    def _load_novel(self, novel_id: str):
        """加载小说到当前上下文"""
        novel_dir = self.novels_dir / novel_id
        if not novel_dir.exists():
            self.console.print(f"[red]小说不存在: {novel_id}[/red]")
            return

        os.environ['CURRENT_NOVEL_ID'] = novel_id
        meta_file = novel_dir / "meta.json"
        with open(meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        self.console.print(f"\n[green]✓ 已加载小说: {meta['title']}[/green]")
        self.console.print(f"  ID: {novel_id}")
        self.console.print(f"  描述: {meta['description']}\n")

    def _show_current(self):
        """显示当前小说"""
        novel_id = os.getenv('CURRENT_NOVEL_ID')
        if not novel_id:
            self.console.print("[yellow]未加载任何小说[/yellow]")
            return

        novel_dir = self.novels_dir / novel_id
        meta_file = novel_dir / "meta.json"
        with open(meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        self.console.print(f"\n[bold cyan]当前小说:[/bold cyan]")
        self.console.print(f"  标题: {meta['title']}")
        self.console.print(f"  ID: {novel_id}")
        self.console.print(f"  描述: {meta['description']}\n")

    def _list_chapters(self):
        """列出当前小说的章节"""
        novel_id = os.getenv('CURRENT_NOVEL_ID')
        if not novel_id:
            self.console.print("[yellow]未加载任何小说，使用 /load <novel_id>[/yellow]")
            return

        chapters_dir = self.novels_dir / novel_id / "chapters"
        if not chapters_dir.exists():
            self.console.print("[yellow]暂无章节[/yellow]")
            return

        self.console.print("\n[bold cyan]📖 章节列表:[/bold cyan]")
        for chapter_file in sorted(chapters_dir.glob("*.json")):
            with open(chapter_file, 'r', encoding='utf-8') as f:
                chapter = json.load(f)
            word_count = len(chapter['content'])
            self.console.print(f"  • {chapter['id']}: {chapter['title']} ({word_count} 字)")
        self.console.print()

    def _show_help(self):
        """显示帮助信息"""
        self.console.print("\n[bold cyan]可用命令:[/bold cyan]")
        self.console.print("  /list       - 列出所有小说")
        self.console.print("  /load <id>  - 加载指定小说")
        self.console.print("  /current    - 显示当前小说")
        self.console.print("  /chapters   - 列出当前小说的章节")
        self.console.print("  /help       - 显示此帮助信息\n")

