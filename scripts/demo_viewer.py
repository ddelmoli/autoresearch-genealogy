#!/usr/bin/env python3
"""demo_viewer.py -- serve the live session viewer on localhost.

    python3 scripts/demo_viewer.py [--port 8765]

then open http://127.0.0.1:8765/ (for a second screen or a TV, put that window
there). The page replays the current event stream and then follows it live over
Server-Sent Events. Standard library only.

Binds to 127.0.0.1 and nothing else: the stream carries vault text, including
living people, so it must never be reachable from the network. Page options go in
the URL, e.g. `?viewer_gen=2&viewer_label=Dad` to also show each person's
relationship to a Gen 2 watcher.
"""
import argparse
import http.server
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import demo_events as de  # noqa: E402

PAGE = pathlib.Path(__file__).resolve().parent / "demo_viewer" / "index.html"
POLL = 0.4


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            body = PAGE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif path == "/events":
            self.stream()
        else:
            self.send_error(404)

    def stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        offset, inode, last_ping = 0, None, 0.0
        try:
            while True:
                try:
                    st = de.EVENTS.stat()
                except FileNotFoundError:
                    st = None
                if st is not None:
                    # `narrate.py start` moves the old file aside: a new inode or a
                    # shorter file means a new demo, so tell the page to clear.
                    if inode is not None and (st.st_ino != inode or st.st_size < offset):
                        self.send("reset", {})
                        offset = 0
                    inode = st.st_ino
                    if st.st_size > offset:
                        with open(de.EVENTS, "rb") as fh:
                            fh.seek(offset)
                            chunk = fh.read()
                        complete = chunk.rfind(b"\n") + 1   # only whole lines
                        for line in chunk[:complete].splitlines():
                            if line.strip():
                                self.wfile.write(b"data: " + line + b"\n\n")
                        offset += complete
                        self.wfile.flush()
                if time.time() - last_ping > 5:      # keepalive + on/off state
                    self.send("status", {"active": de.is_active()})
                    last_ping = time.time()
                time.sleep(POLL)
        except (BrokenPipeError, ConnectionResetError):
            return

    def send(self, event, data):
        self.wfile.write(f"event: {event}\ndata: {json.dumps(data)}\n\n".encode())
        self.wfile.flush()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    srv.daemon_threads = True
    print(f"session viewer: http://127.0.0.1:{a.port}/  (stream: {de.EVENTS})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
