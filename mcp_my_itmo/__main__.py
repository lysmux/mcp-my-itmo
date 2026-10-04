from mcp_my_itmo.config import Settings
from mcp_my_itmo.logging_setup import setup_logging
from mcp_my_itmo.server import create_app


def main() -> None:
    setup_logging()
    settings = Settings.load()
    create_app(settings).run(transport=settings.transport)


if __name__ == "__main__":
    main()
