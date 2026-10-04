from mcp_my_itmo.config import Settings


def test_mcp_defaults(monkeypatch):
    for name in ("HOST", "PORT", "PATH"):
        monkeypatch.delenv(f"MY_ITMO_MCP_{name}", raising=False)
    settings = Settings.load()
    assert (settings.mcp_host, settings.mcp_port, settings.mcp_path) == (
        "127.0.0.1",
        8000,
        "/mcp",
    )


def test_mcp_env_overrides(monkeypatch):
    monkeypatch.setenv("MY_ITMO_MCP_HOST", "0.0.0.0")
    monkeypatch.setenv("MY_ITMO_MCP_PORT", "9001")
    monkeypatch.setenv("MY_ITMO_MCP_PATH", "/x")
    settings = Settings.load()
    assert (settings.mcp_host, settings.mcp_port, settings.mcp_path) == ("0.0.0.0", 9001, "/x")


def test_app_configured_from_settings():
    from mcp_my_itmo.server import create_app

    settings = Settings.load()
    app = create_app(settings)

    assert app.settings.host == settings.mcp_host
    assert app.settings.port == settings.mcp_port
    assert app.settings.streamable_http_path == settings.mcp_path


def test_transport_defaults_to_stdio(monkeypatch):
    monkeypatch.delenv("MY_ITMO_TRANSPORT", raising=False)
    assert Settings.load().transport == "stdio"


def test_transport_env_allows_streamable_http(monkeypatch):
    monkeypatch.setenv("MY_ITMO_TRANSPORT", "streamable-http")
    assert Settings.load().transport == "streamable-http"
