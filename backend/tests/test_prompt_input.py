import json

from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from app.cli.input import NovelCommandCompleter


def collect_completion_texts(completer, text):
    document = Document(text=text, cursor_position=len(text))
    return [
        completion.text
        for completion in completer.get_completions(document, CompleteEvent())
    ]


def test_completes_slash_commands():
    completer = NovelCommandCompleter()

    completions = collect_completion_texts(completer, "/l")

    assert "/load" in completions
    assert "/list" in completions


def test_completes_novel_ids_for_load_command(tmp_path):
    novels_dir = tmp_path / "novels"
    novel_dir = novels_dir / "novel_alpha"
    novel_dir.mkdir(parents=True)
    (novel_dir / "meta.json").write_text(
        json.dumps({"id": "novel_alpha", "title": "测试小说"}, ensure_ascii=False),
        encoding="utf-8",
    )

    completer = NovelCommandCompleter(novels_dir=novels_dir)

    completions = collect_completion_texts(completer, "/load novel_")

    assert "novel_alpha" in completions


def test_load_command_without_prefix_lists_novel_ids(tmp_path):
    novels_dir = tmp_path / "novels"
    novel_dir = novels_dir / "novel_beta"
    novel_dir.mkdir(parents=True)
    (novel_dir / "meta.json").write_text(
        json.dumps({"id": "novel_beta", "title": "第二本"}, ensure_ascii=False),
        encoding="utf-8",
    )

    completer = NovelCommandCompleter(novels_dir=novels_dir)

    completions = collect_completion_texts(completer, "/load ")

    assert "novel_beta" in completions
