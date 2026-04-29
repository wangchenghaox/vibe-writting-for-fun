from contextlib import contextmanager


class FakeConsole:
    def __init__(self):
        self.prints = []

    def print(self, *args, **kwargs):
        self.prints.append((args, kwargs))

    @contextmanager
    def status(self, *args, **kwargs):
        yield


class FakeDisplay:
    def __init__(self):
        self.console = FakeConsole()
        self.inputs = iter(["hello", EOFError])

    def print_welcome(self):
        pass

    def get_input(self):
        value = next(self.inputs)
        if value is EOFError:
            raise EOFError
        return value


def test_cli_streams_assistant_response(monkeypatch):
    import app.ui.cli as cli_module

    created_agents = []

    class FakeAgent:
        def __init__(self, provider, session):
            self.event_bus = type(
                "FakeEventBus",
                (),
                {"_subscribers": {}, "subscribe": lambda *args, **kwargs: None},
            )()
            self.chat_calls = []
            self.chat_stream_calls = []
            created_agents.append(self)

        def chat(self, message):
            self.chat_calls.append(message)
            return "完整回复"

        def chat_stream(self, message):
            self.chat_stream_calls.append(message)
            yield "你"
            yield "好"

    fake_display = FakeDisplay()
    saved_sessions = []

    monkeypatch.setattr(cli_module, "setup_logging", lambda: None)
    monkeypatch.setattr(cli_module, "create_provider", lambda: object())
    monkeypatch.setattr(cli_module, "RichDisplay", lambda: fake_display)
    monkeypatch.setattr(cli_module, "AgentCore", FakeAgent)
    monkeypatch.setattr(
        cli_module,
        "SessionStore",
        lambda: type("FakeSessionStore", (), {"save_session": lambda self, session: saved_sessions.append(session)})(),
    )

    cli_module.CLI().run()

    agent = created_agents[0]
    assert agent.chat_calls == []
    assert agent.chat_stream_calls == ["hello"]
    assert [args[0] for args, kwargs in fake_display.console.prints if kwargs.get("end") == ""] == [
        "\n[bold blue]Assistant:[/bold blue] ",
        "你",
        "好",
    ]
