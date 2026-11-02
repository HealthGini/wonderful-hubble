"""
GoodDeeds.space Backend Server.

This module implements a threaded HTTP server using the standard http.server library.
It serves static frontend files and routes API requests to the handlers module.
"""

import os
import sys
import json
import mimetypes
import traceback
from urllib.parse import urlparse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from email_templates import load_dotenv_file

# Auto-load git-ignored `.env` before reading PORT or initializing handlers
if os.environ.get("GOODDEEDS_SKIP_DOTENV") != "1":
    load_dotenv_file()

from database import init_db
from handlers import handle_api_request

HOST = (os.environ.get("HOST") or "127.0.0.1").strip() or "127.0.0.1"
PORT = int(os.environ.get("PORT", 8080))
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://accounts.google.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://accounts.google.com; "
    "font-src 'self' data: https://fonts.gstatic.com; "
    "img-src 'self' data: blob: https:; "
    "connect-src 'self' https://accounts.google.com https://oauth2.googleapis.com; "
    "frame-src 'self' blob: https://accounts.google.com; "
    "frame-ancestors 'none'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


def get_allowed_cors_origins(host_header: str = "") -> set:
    """Returns the set of explicitly trusted origins for CORS (never wildcard `*`)."""
    allowed = {
        "https://gooddeeds.space",
        "https://www.gooddeeds.space",
    }
    raw_custom = (os.environ.get("CORS_ALLOWED_ORIGINS") or "").strip()
    if raw_custom:
        for item in raw_custom.split(","):
            cand = item.strip().rstrip("/")
            if cand and cand != "*":
                allowed.add(cand)

    for env_key in ("PUBLIC_BASE_URL", "RENDER_EXTERNAL_URL"):
        raw_url = (os.environ.get(env_key) or "").strip()
        if raw_url:
            parsed = urlparse(raw_url)
            if parsed.scheme and parsed.netloc:
                allowed.add(f"{parsed.scheme}://{parsed.netloc}")

    host_clean = (host_header or "").strip()
    host_only = host_clean.split(":")[0].lower()
    if host_only in ("localhost", "127.0.0.1"):
        allowed.add("http://localhost")
        allowed.add("http://127.0.0.1")
        allowed.add(f"http://localhost:{PORT}")
        allowed.add(f"http://127.0.0.1:{PORT}")
        if ":" in host_clean:
            allowed.add(f"http://{host_clean.lower()}")
    elif host_only.endswith(".googlers.com"):
        allowed.add(f"http://{host_clean.lower()}")
        allowed.add(f"https://{host_clean.lower()}")
    return allowed


class GoodDeedsServerHandler(BaseHTTPRequestHandler):
    """
    HTTP Request Handler for GoodDeeds.space.
    
    Handles security & origin-restricted CORS headers, routes API requests to handlers.py,
    and serves static frontend files.
    """

    def send_security_headers(self):
        """Sends baseline HTTP security headers (CSP, HSTS, X-Content-Type-Options, X-Frame-Options)."""
        self.send_header("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")

    def _matched_cors_origin(self) -> str:
        """Returns the validated request Origin if it belongs to our own allowed origins, else ''."""
        req_headers = getattr(self, "headers", None) or {}
        req_origin = (req_headers.get("Origin") or req_headers.get("origin") or "").strip().rstrip("/")
        if not req_origin:
            return ""
        host_hdr = (req_headers.get("Host") or req_headers.get("host") or "").strip()
        if req_origin in get_allowed_cors_origins(host_hdr):
            return req_origin
        return ""

    def send_cors_headers(self):
        """Sends origin-restricted CORS headers only for trusted own origins (never `*`)."""
        self.send_header("Vary", "Origin")
        matched_origin = self._matched_cors_origin()
        if matched_origin:
            self.send_header("Access-Control-Allow-Origin", matched_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        """Handles preflight OPTIONS requests for CORS, rejecting untrusted cross-origin preflights."""
        req_headers = getattr(self, "headers", None) or {}
        req_origin = (req_headers.get("Origin") or req_headers.get("origin") or "").strip()
        if req_origin and not self._matched_cors_origin():
            self.send_response(403)
            self.send_security_headers()
            self.send_header("Vary", "Origin")
            self.end_headers()
            return
        self.send_response(204)
        self.send_security_headers()
        self.send_cors_headers()
        self.end_headers()

    def handle_request(self, method):
        """
        Routes the request based on the path.
        
        If the path starts with '/api/' or '/auth/', it reads the body and delegates to
        handlers.handle_api_request. Otherwise, it serves static files (GET only).
        """
        if self.path.startswith("/api/") or self.path.startswith("/auth/"):
            content_len = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_len) if content_len > 0 else b""
            try:
                status, headers, resp_body = handle_api_request(method, self.path, self.headers, body_bytes)
            except Exception:
                traceback.print_exc(file=sys.stderr)
                status = 500
                headers = {"Content-Type": "application/json"}
                resp_body = json.dumps({"success": False, "error": "Internal Server Error"})

            self.send_response(status)
            self.send_security_headers()
            self.send_cors_headers()
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            for k, v in headers.items():
                if k.lower() not in ("cache-control", "pragma", "expires"):
                    self.send_header(k, v)
            self.end_headers()
            if isinstance(resp_body, str):
                resp_body = resp_body.encode("utf-8")
            self.wfile.write(resp_body)
        else:
            if method != "GET":
                self.send_response(405)
                self.send_security_headers()
                self.end_headers()
                return
            self.serve_static_file()

    def do_HEAD(self):
        """Handles HEAD requests (used by cloud health checks and load balancers)."""
        self.send_response(200)
        self.send_security_headers()
        self.send_cors_headers()
        self.send_header("Content-Type", "text/html")
        self.end_headers()

    def do_GET(self):
        """Handles GET requests."""
        self.handle_request("GET")

    def do_POST(self):
        """Handles POST requests."""
        self.handle_request("POST")

    def do_PUT(self):
        """Handles PUT requests."""
        self.handle_request("PUT")

    def do_DELETE(self):
        """Handles DELETE requests."""
        self.handle_request("DELETE")

    def serve_static_file(self):
        """
        Serves static files from the static/ directory.
        
        Resolves the file path, guesses the MIME type, and writes the file content
        to the response. Defaults to serving index.html for SPA routing support.
        """
        path = self.path.split("?")[0].split("#")[0]
        if path == "/":
            path = "/index.html"
        
        file_path = os.path.normpath(os.path.join(STATIC_DIR, path.lstrip("/")))
        if not file_path.startswith(STATIC_DIR) or not os.path.exists(file_path) or os.path.isdir(file_path):
            file_path = os.path.join(STATIC_DIR, "index.html")

        if not os.path.exists(file_path):
            self.send_response(404)
            self.send_security_headers()
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"404 - Static File Not Found")
            return

        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            if file_path.endswith(".js"):
                mime_type = "application/javascript"
            elif file_path.endswith(".css"):
                mime_type = "text/css"
            elif file_path.endswith(".html"):
                mime_type = "text/html"
            else:
                mime_type = "application/octet-stream"

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_security_headers()
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            print(f"⚠️ Static file serving error ({self.path}): {e}", file=sys.stderr)
            self.send_response(500)
            self.send_security_headers()
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"500 Internal Server Error")

def run():
    """
    Initializes the database and starts the HTTP server.
    
    Defaults to binding 127.0.0.1:<PORT> behind Caddy (overridable via HOST env var).
    """
    print("Initializing SQLite database & demo seed data...")
    init_db()
    if (os.environ.get("SEED_SHOWCASE_DATA") or "").strip().lower() in ("1", "true", "yes"):
        try:
            from scripts.seed_demo_showcase import seed_showcase
            seed_showcase()
        except Exception as exc:
            print(f"⚠️ Warning: SEED_SHOWCASE_DATA skipped ({exc})")
    server_address = (HOST, PORT)
    httpd = ThreadingHTTPServer(server_address, GoodDeedsServerHandler)
    print(f"☀️ gooddeeds.space backend server running cleanly on http://{HOST}:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server gracefully...")
        httpd.server_close()

if __name__ == "__main__":
    run()
