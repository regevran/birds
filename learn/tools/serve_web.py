#!/usr/bin/env python3
"""Serve the staged browser client for development, without caching.

``python -m http.server`` sends no cache headers, so browsers may reuse a
stale ES module or stylesheet after the client is restaged. This server is the
same simple file server with ``Cache-Control: no-store`` on every response,
so a reload always reflects ``build/web``. It is a development convenience
only; the client is deployed as static files elsewhere.
"""

from __future__ import annotations

import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True)
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    handler = functools.partial(Handler, directory=args.directory)
    server = ThreadingHTTPServer(("", args.port), handler)
    print(f"Serving {args.directory} on http://localhost:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
