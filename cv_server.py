"""Private CV endpoint and local preview. Put behind HTTPS/Apache for production."""
import argparse
import hashlib
import hmac
import ipaddress
import json
import mimetypes
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
PUBLIC = {"index.html", "redef.svg", "aix-lab.jpg", "azure-lab-evidence.png", "project_takeover.jpg",
          "it-takeover-playbook.pdf", "simple-project-roadmap.png", "simple-project-roadmap.pdf"}


def create_server(config_path, port=8766):
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    records = config["documents"]
    for record in records:
        path = Path(record["path"]).resolve(strict=True)
        if path.is_relative_to(ROOT):
            raise ValueError("Private CVs must be outside the website directory")
        record["path"] = path
    attempts = {}
    lock = threading.Lock()
    hashing_slots = threading.BoundedSemaphore(2)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *_):
            pass  # Never log codes, request bodies, or CV filenames.

        def respond(self, status, body=b"", content_type="text/plain; charset=utf-8", attachment=False):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if status == 429:
                self.send_header("Retry-After", "900")
            if attachment:
                self.send_header("Content-Disposition", 'attachment; filename="Peter_Hudcovic_CV.pdf"')
                self.send_header("X-Robots-Tag", "noindex, noarchive")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            name = urlsplit(self.path).path.removeprefix("/") or "index.html"
            if name not in PUBLIC:
                self.respond(404, b"Not found")
                return
            try:
                self.respond(200, (ROOT / name).read_bytes(), mimetypes.guess_type(name)[0] or "application/octet-stream")
            except OSError:
                self.respond(404, b"Not found")

        def do_POST(self):
            if self.path not in {"/api/cv", "/cv-download.php"}:
                self.respond(404)
                return
            if self.headers.get("Origin") not in config["allowed_origins"]:
                self.respond(403)
                return
            now = time.monotonic()
            peer = self.client_address[0]
            # Enable only behind Apache, which OVERWRITES this header with the
            # connection's REMOTE_ADDR. The service is bound to loopback only.
            if config.get("apache_proxy", False):
                try:
                    peer = str(ipaddress.ip_address(self.headers.get("X-CV-Client-IP", "")))
                except ValueError:
                    self.respond(403)
                    return
            with lock:
                for key in list(attempts):
                    if attempts[key][0] < now - 900:
                        del attempts[key]
                start, count = attempts.get(peer, (now, 0))
                if count >= 10 or len(attempts) >= 10000:
                    self.respond(429)
                    return
                attempts[peer] = (start, count + 1)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1024:
                    self.respond(400)
                    return
                if self.headers.get("Content-Type") != "application/json":
                    self.respond(400)
                    return
                payload = json.loads(self.rfile.read(length))
                code = payload.get("code") if isinstance(payload, dict) else None
                if not isinstance(code, str) or not 0 < len(code) <= 128:
                    self.respond(400)
                    return
                match = None
                if not hashing_slots.acquire(blocking=False):
                    self.respond(503)
                    return
                try:
                    for record in records:
                        digest = hashlib.scrypt(code.encode(), salt=bytes.fromhex(record["salt"]), n=16384, r=8, p=1).hex()
                        if hmac.compare_digest(digest, record["hash"]):
                            match = record
                finally:
                    hashing_slots.release()
                if match is None:
                    self.respond(403)
                    return
                self.respond(200, match["path"].read_bytes(), "application/pdf", attachment=True)
            except (ValueError, OSError):
                self.respond(400)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Private JSON config outside the website and repository")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    create_server(args.config, args.port).serve_forever()
