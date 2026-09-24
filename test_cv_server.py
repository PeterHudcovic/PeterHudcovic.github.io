import hashlib
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from cv_server import create_server


class PrivateDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        folder = Path(self.temp.name)
        records = []
        for i in range(3):
            path = folder / f"private-{i}.pdf"
            path.write_bytes(b"%PDF-1.4 test document " + str(i).encode())
            salt = bytes([i + 1]) * 16
            records.append(dict(path=str(path), salt=salt.hex(), hash=hashlib.scrypt(
                f"test-code-{i}".encode(), salt=salt, n=16384, r=8, p=1).hex()))
        config = folder / "config.json"
        config.write_text(json.dumps(dict(documents=records, allowed_origins=["http://preview.test"])))
        self.server = create_server(config, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, code=None, path="/api/cv", origin="http://preview.test"):
        data = json.dumps(dict(code=code)).encode() if code is not None else None
        req = urllib.request.Request(self.base + path, data=data, headers={
            "Origin": origin, "Content-Type": "application/json"})
        try:
            return urllib.request.urlopen(req)
        except urllib.error.HTTPError as error:
            return error

    def test_each_code_returns_only_its_document(self):
        for i in range(3):
            with self.request(f"test-code-{i}") as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b"%PDF-1.4 test document " + str(i).encode())
                self.assertEqual(response.headers["Content-Type"], "application/pdf")
                self.assertIn("attachment", response.headers["Content-Disposition"])
                self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_invalid_code_and_foreign_origin_rejected(self):
        for code, origin in [("wrong", "http://preview.test"), ("test-code-0", "https://elsewhere.test")]:
            with self.request(code, origin=origin) as response:
                self.assertEqual(response.status, 403)
                self.assertNotIn(b"%PDF", response.read())

    def test_private_files_and_source_cannot_be_fetched(self):
        for path in ["/api/cv", "/private-0.pdf", "/config.json", "/cv_server.py", "/.git/config", "/../private-0.pdf"]:
            with self.request(path=path) as response:
                self.assertEqual(response.status, 404)

    def test_rate_limit(self):
        for _ in range(10):
            self.request("wrong").close()
        with self.request("test-code-0") as response:
            self.assertEqual(response.status, 429)


if __name__ == "__main__":
    unittest.main()
