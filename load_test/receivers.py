"""Local webhook receivers with configurable reliability for load testing.

Ports: 9201 = 100% reliable, 9202 = 90%, 9203 = 50%.
Failures return HTTP 500. Run: python load_test/receivers.py
"""

import http.server
import random
import threading

RELIABILITY = {9201: 1.0, 9202: 0.9, 9203: 0.5}


class Receiver(http.server.BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - http.server API
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        ok = random.random() < RELIABILITY[self.server.server_address[1]]
        self.send_response(200 if ok else 500)
        self.end_headers()
        self.wfile.write(b"ok" if ok else b"error")

    def log_message(self, *args):
        pass


def main() -> None:
    servers = [
        http.server.ThreadingHTTPServer(("127.0.0.1", port), Receiver) for port in RELIABILITY
    ]
    for server in servers[1:]:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"receivers up on {sorted(RELIABILITY)}", flush=True)
    servers[0].serve_forever()


if __name__ == "__main__":
    main()
