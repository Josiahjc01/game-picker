"""Tiny static server for the Game Picker web UI."""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str | None = None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        # Keep console readable during demos.
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the Game Picker web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    if not (WEB / "index.html").exists():
        raise SystemExit(f"Missing UI at {WEB / 'index.html'}")
    if not (WEB / "games.json").exists():
        raise SystemExit(
            f"Missing {WEB / 'games.json'}. Run scripts/build_library.py then "
            "copy/slim into web/games.json (see README)."
        )

    handler = functools.partial(QuietHandler, directory=str(WEB))
    with socketserver.ThreadingTCPServer((args.host, args.port), handler) as httpd:
        httpd.allow_reuse_address = True
        print(f"Game Picker UI → http://{args.host}:{args.port}/")
        print("Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
