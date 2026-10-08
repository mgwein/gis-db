import argparse

import uvicorn

from gisdb.config import get_settings
from gisdb.logging_config import configure_logging


def main(argv: list[str] | None = None) -> int:
    configure_logging(get_settings().log_level)

    parser = argparse.ArgumentParser(prog="gisdb")
    subparsers = parser.add_subparsers(required=True, dest="command")

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)

    if args.command == "serve":
        uvicorn.run(
            "gisdb.api.app:app",
            host=args.host,
            port=args.port,
            log_config=None,
            access_log=False,
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
