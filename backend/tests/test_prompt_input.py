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

    completions = collect_completion_texts(completer, "/h")

    assert "/help" in completions
    assert "/load" not in completions


def test_load_command_no_longer_completes_novel_ids(tmp_path):
    novels_dir = tmp_path / "novels"
    novel_dir = novels_dir / "novel_alpha"
    novel_dir.mkdir(parents=True)
    (novel_dir / "meta.json").write_text(
        json.dumps({"id": "novel_alpha", "title": "测试小说"}, ensure_ascii=False),
        encoding="utf-8",
    )

    completer = NovelCommandCompleter(novels_dir=novels_dir)

    completions = collect_completion_texts(completer, "/load novel_")

    assert completions == []


def test_load_command_without_prefix_does_not_list_novel_ids(tmp_path):
    novels_dir = tmp_path / "novels"
    novel_dir = novels_dir / "novel_beta"
    novel_dir.mkdir(parents=True)
    (novel_dir / "meta.json").write_text(
        json.dumps({"id": "novel_beta", "title": "第二本"}, ensure_ascii=False),
        encoding="utf-8",
    )

    completer = NovelCommandCompleter(novels_dir=novels_dir)

    completions = collect_completion_texts(completer, "/load ")

    assert completions == []
