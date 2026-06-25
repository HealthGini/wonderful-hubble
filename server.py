import os
import sys
import mimetypes
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from database import init_db
from handlers import handle_api_request

PORT = int(os.environ.get("PORT", 8080))
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

class GoodDeedsServerHandler(BaseHTTPRequestHandler):
    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors_headers()
        self.end_headers()

    def handle_request(self, method):
        if self.path.startswith("/api/"):
            content_len = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_len) if content_len > 0 else b""
            status, headers, resp_body = handle_api_request(method, self.path, self.headers, body_bytes)
            self.send_response(status)
            self.send_cors_headers()
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(resp_body.encode("utf-8"))
        else:
            if method != "GET":
                self.send_response(405)
                self.end_headers()
                return
            self.serve_static_file()

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def do_PUT(self):
        self.handle_request("PUT")

    def do_DELETE(self):
        self.handle_request("DELETE")

    def serve_static_file(self):
        path = self.path.split("?")[0].split("#")[0]
        if path == "/":
            path = "/index.html"
        
        file_path = os.path.normpath(os.path.join(STATIC_DIR, path.lstrip("/")))
        if not file_path.startswith(STATIC_DIR) or not os.path.exists(file_path) or os.path.isdir(file_path):
            file_path = os.path.join(STATIC_DIR, "index.html")

        if not os.path.exists(file_path):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
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
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"500 Server Error: {str(e)}".encode("utf-8"))

def run():
    print("Initializing SQLite database & demo seed data...")
    init_db()
    server_address = ("0.0.0.0", PORT)
    httpd = ThreadingHTTPServer(server_address, GoodDeedsServerHandler)
    print(f"☀️ gooddeeds.space backend server running cleanly on http://0.0.0.0:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server gracefully...")
        httpd.server_close()

if __name__ == "__main__":
    run()
