from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock


class TargetState:
    def __init__(self) -> None:
        self._healthy = True
        self._lock = Lock()

    def set_healthy(self, healthy: bool) -> None:
        with self._lock:
            self._healthy = healthy

    def status(self) -> int:
        with self._lock:
            return 200 if self._healthy else 503


STATE = TargetState()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_response(STATE.status())
            self.end_headers()
            self.wfile.write(b"healthy" if STATE.status() == 200 else b"failing")
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if self.path == "/__control/healthy":
            STATE.set_healthy(True)
        elif self.path == "/__control/fail":
            STATE.set_healthy(False)
        else:
            self.send_error(404)
            return
        self.send_response(204)
        self.end_headers()

    def log_message(self, _format: str, *_args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
