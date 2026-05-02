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


class NonInteractiveDisplay(FakeDisplay):
    def get_input(self):
        raise OSError(22, "Invalid argument")


def test_cli_streams_assistant_response(monkeypatch):
    import app.cli.app as cli_module

    created_agents = []

    class FakeAgent:
        def __init__(self, provider, session, tool_context=None, memory_recorder=None):
            self.event_bus = type(
                "FakeEventBus",
                (),
                {"_subscribers": {}, "subscribe": lambda *args, **kwargs: None},
            )()
            self.session = session
            self.tool_context = tool_context or {}
            self.memory_recorder = memory_recorder
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
    assert agent.tool_context["user_id"] == 0
    assert agent.tool_context["agent_name"] == "main"
    assert agent.tool_context["agent_instance_id"] == saved_sessions[0].id
    assert [args[0] for args, kwargs in fake_display.console.prints if kwargs.get("end") == ""] == [
        "\n[bold blue]Assistant:[/bold blue] ",
        "你",
        "好",
    ]


def test_cli_initializes_database_schema(monkeypatch):
    import app.cli.app as cli_module

    init_calls = []

    monkeypatch.setattr(cli_module, "init_db", lambda: init_calls.append(True))
    monkeypatch.setattr(cli_module, "setup_logging", lambda: None)
    monkeypatch.setattr(cli_module, "create_provider", lambda: object())
    monkeypatch.setattr(cli_module, "RichDisplay", lambda: FakeDisplay())
    monkeypatch.setattr(
        cli_module,
        "SessionStore",
        lambda: type("FakeSessionStore", (), {"save_session": lambda self, session: None})(),
    )

    cli_module.CLI()

    assert init_calls == [True]


def test_cli_exits_when_prompt_reports_non_interactive_input(monkeypatch):
    import app.cli.app as cli_module

    saved_sessions = []

    monkeypatch.setattr(cli_module, "setup_logging", lambda: None)
    monkeypatch.setattr(cli_module, "create_provider", lambda: object())
    monkeypatch.setattr(cli_module, "RichDisplay", lambda: NonInteractiveDisplay())
    monkeypatch.setattr(
        cli_module,
        "SessionStore",
        lambda: type("FakeSessionStore", (), {"save_session": lambda self, session: saved_sessions.append(session)})(),
    )

    cli_module.CLI().run()

    assert len(saved_sessions) == 1


def test_cli_main_help_does_not_start_interactive_loop(monkeypatch, capsys):
    import app.cli_main as cli_main

    monkeypatch.setattr(
        cli_main,
        "CLI",
        lambda: (_ for _ in ()).throw(AssertionError("CLI should not start")),
    )

    try:
        cli_main.main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0

    assert "AI 小说创作 CLI" in capsys.readouterr().out
