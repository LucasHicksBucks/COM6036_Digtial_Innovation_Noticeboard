#!/usr/bin/env python3
"""Community Noticeboard prototype: presentation/API layer entry point."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import secrets
from urllib.parse import parse_qs, urlparse

from noticeboard_service import NoticeboardService, ValidationError

ROOT = Path(__file__).parent
service = NoticeboardService(ROOT / "noticeboard.db")
ADMIN_PASSWORD = os.environ.get("NOTICEBOARD_ADMIN_PASSWORD", "noticeboard")
SESSION_SECRET = os.environ.get("NOTICEBOARD_SESSION_SECRET", secrets.token_hex(32))
SESSION_TTL = timedelta(hours=8)


def _session_token():
    expires = int((datetime.now(timezone.utc) + SESSION_TTL).timestamp())
    message = f"moderator:{expires}".encode("utf-8")
    signature = hmac.new(SESSION_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"{expires}.{signature}"


def _valid_session(cookie_header):
    cookies = {}
    for item in (cookie_header or "").split(";"):
        if "=" in item:
            key, value = item.strip().split("=", 1)
            cookies[key] = value
    token = cookies.get("noticeboard_session", "")
    try:
        expires_text, signature = token.split(".", 1)
        expires = int(expires_text)
    except (ValueError, AttributeError):
        return False
    if expires < int(datetime.now(timezone.utc).timestamp()):
        return False
    message = f"moderator:{expires}".encode("utf-8")
    expected = hmac.new(SESSION_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


class NoticeboardHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200, headers=None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _require_moderator(self):
        if not _valid_session(self.headers.get("Cookie")):
            self._send_json({"error": "Moderator login required"}, 401)
            return False
        return True

    def _send_file(self, path, content_type):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _request_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        route = urlparse(self.path)
        if route.path == "/api/notices":
            filters = {key: values[0] for key, values in parse_qs(route.query).items()}
            self._send_json({"notices": service.list_notices(filters)})
        elif route.path == "/api/archive":
            self._send_json({"notices": service.public_archive()})
        elif route.path == "/api/session":
            self._send_json({"authenticated": _valid_session(self.headers.get("Cookie"))})
        elif route.path == "/api/moderation" and self._require_moderator():
            self._send_json({"notices": service.pending_notices()})
        elif route.path == "/api/moderation/archive" and self._require_moderator():
            self._send_json({"notices": service.moderator_archive()})
        elif route.path == "/api/categories":
            self._send_json({"categories": service.categories()})
        elif route.path == "/":
            self._send_file(ROOT / "static" / "index.html", "text/html; charset=utf-8")
        elif route.path == "/app.js":
            self._send_file(ROOT / "static" / "app.js", "text/javascript; charset=utf-8")
        elif route.path == "/styles.css":
            self._send_file(ROOT / "static" / "styles.css", "text/css; charset=utf-8")
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        route = urlparse(self.path).path
        try:
            if route == "/api/login":
                data = self._request_json()
                if not hmac.compare_digest(str(data.get("password", "")), ADMIN_PASSWORD):
                    self._send_json({"error": "Incorrect moderator password"}, 401)
                    return
                self._send_json({"authenticated": True}, headers={"Set-Cookie": f"noticeboard_session={_session_token()}; HttpOnly; SameSite=Strict; Path=/; Max-Age={int(SESSION_TTL.total_seconds())}"})
            elif route == "/api/logout":
                self._send_json({"authenticated": False}, headers={"Set-Cookie": "noticeboard_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"})
            elif route == "/api/notices":
                self._send_json({"notice": service.submit_notice(self._request_json())}, 201)
            elif route == "/api/notices/approve" and self._require_moderator():
                data = self._request_json()
                self._send_json({"notice": service.moderate_notice(data["id"], "approved")})
            elif route == "/api/notices/reject" and self._require_moderator():
                data = self._request_json()
                self._send_json({"notice": service.moderate_notice(data["id"], "rejected")})
            elif route == "/api/notices/delete" and self._require_moderator():
                data = self._request_json()
                service.delete_notice(data["id"])
                self._send_json({"deleted": True})
            elif route == "/api/notices/final-delete" and self._require_moderator():
                data = self._request_json()
                service.final_delete_notice(data["id"])
                self._send_json({"deleted": True})
            elif route == "/api/notices/restore" and self._require_moderator():
                data = self._request_json()
                self._send_json({"notice": service.restore_notice(data["id"])})
            else:
                self._send_json({"error": "Not found"}, 404)
        except (ValidationError, KeyError, json.JSONDecodeError) as error:
            self._send_json({"error": str(error)}, 400)
        except LookupError as error:
            self._send_json({"error": str(error)}, 404)

    def log_message(self, format_string, *args):
        print(f"{self.address_string()} - {format_string % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), NoticeboardHandler)
    print("Community Noticeboard running at http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping noticeboard")
    finally:
        server.server_close()
