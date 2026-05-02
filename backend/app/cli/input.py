from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style


COMMANDS = {
    "/help": "显示可用命令",
    "/current": "显示当前 sandbox",
    "exit": "保存会话并退出",
    "quit": "保存会话并退出",
}


class NovelCommandCompleter(Completer):
    def __init__(self, novels_dir: Path | str = "data/novels"):
        self.novels_dir = Path(novels_dir)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        stripped = text.lstrip()
        leading_spaces = len(text) - len(stripped)

        if " " in stripped:
            return

        for command, description in COMMANDS.items():
            if command.startswith(stripped):
                yield Completion(
                    command,
                    start_position=-(len(stripped) + leading_spaces),
                    display_meta=description,
                )

    def get_matches(self, text: str) -> list[str]:
        class _Document:
            text_before_cursor = text

        return [
            completion.text
            for completion in self.get_completions(_Document(), None)
        ]


class PromptInput:
    def __init__(
        self,
        history_path: Path | str = "data/cli_history.txt",
        novels_dir: Path | str = "data/novels",
    ):
        history_file = Path(history_path)
        history_file.parent.mkdir(parents=True, exist_ok=True)
        self.session = PromptSession(
            completer=NovelCommandCompleter(novels_dir=novels_dir),
            complete_while_typing=True,
            history=FileHistory(str(history_file)),
            style=Style.from_dict({
                "prompt": "bold #7dd3fc",
            }),
        )

    def get_input(self, prompt: str = "> ") -> str:
        return self.session.prompt([("class:prompt", prompt)])
