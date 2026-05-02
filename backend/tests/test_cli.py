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
        def __init__(self, provider, session, tool_context=None, memory_recorder=None, memory_enabled=False):
            self.event_bus = type(
                "FakeEventBus",
                (),
                {"_subscribers": {}, "subscribe": lambda *args, **kwargs: None},
            )()
            self.session = session
            self.tool_context = tool_context or {}
            self.memory_recorder = memory_recorder
            self.memory_enabled = memory_enabled
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

    monkeypatch.setattr(cli_module.settings, "WORKDIR", None)
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
    assert "workdir" in agent.tool_context
    assert agent.memory_enabled is False
    assert agent.memory_recorder is None
    assert [args[0] for args, kwargs in fake_display.console.prints if kwargs.get("end") == ""] == [
        "\n[bold blue]Assistant:[/bold blue] ",
        "你",
        "好",
    ]


def test_cli_enables_memory_when_requested(monkeypatch):
    import app.cli.app as cli_module

    created_agents = []

    class FakeAgent:
        def __init__(self, provider, session, tool_context=None, memory_recorder=None, memory_enabled=False):
            self.event_bus = type(
                "FakeEventBus",
                (),
                {"_subscribers": {}, "subscribe": lambda *args, **kwargs: None},
            )()
            self.memory_recorder = memory_recorder
            self.memory_enabled = memory_enabled
            created_agents.append(self)

        def chat_stream(self, message):
            yield "ok"

    monkeypatch.setattr(cli_module.settings, "WORKDIR", None)
    monkeypatch.setattr(cli_module, "setup_logging", lambda: None)
    monkeypatch.setattr(cli_module, "create_provider", lambda: object())
    monkeypatch.setattr(cli_module, "RichDisplay", lambda: FakeDisplay())
    monkeypatch.setattr(cli_module, "AgentCore", FakeAgent)
    monkeypatch.setattr(
        cli_module,
        "SessionStore",
        lambda: type("FakeSessionStore", (), {"save_session": lambda self, session: None})(),
    )

    cli_module.CLI(memory_enabled=True).run()

    assert created_agents[0].memory_enabled is True
    assert created_agents[0].memory_recorder is not None


def test_cli_uses_env_memory_setting_when_no_flag(monkeypatch):
    import app.cli.app as cli_module

    monkeypatch.setattr(cli_module.settings, "MEMORY_ENABLED", True)
    monkeypatch.setattr(cli_module.settings, "WORKDIR", None)
    monkeypatch.setattr(cli_module, "setup_logging", lambda: None)
    monkeypatch.setattr(cli_module, "create_provider", lambda: object())
    monkeypatch.setattr(cli_module, "RichDisplay", lambda: FakeDisplay())
    monkeypatch.setattr(
        cli_module,
        "SessionStore",
        lambda: type("FakeSessionStore", (), {"save_session": lambda self, session: None})(),
    )

    cli = cli_module.CLI()

    assert cli.memory_enabled is True


def test_cli_uses_workdir_as_agent_sandbox(monkeypatch, tmp_path):
    import app.cli.app as cli_module

    created_agents = []

    class FakeAgent:
        def __init__(self, provider, session, tool_context=None, memory_recorder=None, memory_enabled=False):
            self.event_bus = type(
                "FakeEventBus",
                (),
                {"_subscribers": {}, "subscribe": lambda *args, **kwargs: None},
            )()
            self.session = session
            self.tool_context = tool_context or {}
            created_agents.append(self)

        def chat_stream(self, message):
            yield "ok"

    workdir = tmp_path / "sandbox"

    monkeypatch.setattr(cli_module.settings, "WORKDIR", None)
    monkeypatch.setattr(cli_module, "setup_logging", lambda: None)
    monkeypatch.setattr(cli_module, "create_provider", lambda: object())
    monkeypatch.setattr(cli_module, "RichDisplay", lambda: FakeDisplay())
    monkeypatch.setattr(cli_module, "AgentCore", FakeAgent)
    monkeypatch.setattr(
        cli_module,
        "SessionStore",
        lambda: type("FakeSessionStore", (), {"save_session": lambda self, session: None})(),
    )

    cli_module.CLI(workdir=workdir).run()

    resolved = str(workdir.resolve())
    assert cli_module.settings.WORKDIR == workdir.resolve()
    assert created_agents[0].session.context["workdir"] == resolved
    assert created_agents[0].tool_context["workdir"] == resolved
    assert created_agents[0].tool_context["novel_id"] == workdir.name


def test_cli_main_parses_memory_flags(monkeypatch):
    import app.cli_main as cli_main

    requested = []

    class FakeCLI:
        def __init__(self, memory_enabled=None, workdir=None):
            requested.append((memory_enabled, workdir))

        def run(self):
            pass

    monkeypatch.setattr(cli_main, "CLI", FakeCLI)

    cli_main.main(["--memory"])
    cli_main.main(["--no-memory"])

    assert requested == [(True, None), (False, None)]


def test_cli_main_parses_workdir(monkeypatch, tmp_path):
    import app.cli_main as cli_main

    requested = []

    class FakeCLI:
        def __init__(self, memory_enabled=None, workdir=None):
            requested.append((memory_enabled, workdir))

        def run(self):
            pass

    monkeypatch.setattr(cli_main, "CLI", FakeCLI)

    cli_main.main(["--workdir", str(tmp_path)])

    assert requested == [(None, tmp_path)]


def test_command_handler_does_not_switch_workdir_with_load_command(monkeypatch):
    import app.cli.commands as commands_module

    class FakeAgent:
        def __init__(self):
            self.session = type("Session", (), {"context": {"workdir": "/sandbox"}})()
            self.tool_context = {"workdir": "/sandbox"}

    monkeypatch.delenv("CURRENT_NOVEL_ID", raising=False)
    console = FakeConsole()
    agent = FakeAgent()
    handler = commands_module.CommandHandler(console, agent, workdir="/sandbox")

    assert handler.handle("/load novel_a") is True

    assert agent.session.context == {"workdir": "/sandbox"}
    assert agent.tool_context == {"workdir": "/sandbox"}
    printed = "\n".join(str(args[0]) for args, kwargs in console.prints if args)
    assert "未知命令: load" in printed


def test_cli_does_not_initialize_memory_database_by_default(monkeypatch):
    import app.cli.app as cli_module

    init_calls = []

    monkeypatch.setattr(cli_module.settings, "WORKDIR", None)
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

    assert init_calls == []


def test_cli_initializes_database_schema_when_memory_enabled(monkeypatch):
    import app.cli.app as cli_module

    init_calls = []

    monkeypatch.setattr(cli_module.settings, "WORKDIR", None)
    monkeypatch.setattr(cli_module, "init_db", lambda: init_calls.append(True))
    monkeypatch.setattr(cli_module, "setup_logging", lambda: None)
    monkeypatch.setattr(cli_module, "create_provider", lambda: object())
    monkeypatch.setattr(cli_module, "RichDisplay", lambda: FakeDisplay())
    monkeypatch.setattr(
        cli_module,
        "SessionStore",
        lambda: type("FakeSessionStore", (), {"save_session": lambda self, session: None})(),
    )

    cli_module.CLI(memory_enabled=True)

    assert init_calls == [True]


def test_cli_exits_when_prompt_reports_non_interactive_input(monkeypatch):
    import app.cli.app as cli_module

    saved_sessions = []

    monkeypatch.setattr(cli_module.settings, "WORKDIR", None)
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
