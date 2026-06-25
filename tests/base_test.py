import os
import sys
import unittest
import tempfile
import shutil
import json

# Add workspace root to sys.path to ensure we can import database and handlers
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(TESTS_DIR)
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

class BaseTestCase(unittest.TestCase):
    temp_db_dir = None
    temp_db_file = None

    @classmethod
    def setUpClass(cls):
        # Create a temporary directory for the database to avoid collision
        cls.temp_db_dir = tempfile.mkdtemp()
        cls.temp_db_file = os.path.join(cls.temp_db_dir, "test_gooddeeds.db")
        os.environ["DB_PATH"] = cls.temp_db_file
        
        # Import database and handlers after setting DB_PATH
        import database
        import handlers
        
        # Explicitly overwrite the loaded DB_PATH to bypass module caching
        database.DB_PATH = cls.temp_db_file
        
        cls.database = database
        cls.handlers = handlers

    @classmethod
    def tearDownClass(cls):
        # Clean up temp directory
        if cls.temp_db_dir and os.path.exists(cls.temp_db_dir):
            shutil.rmtree(cls.temp_db_dir)
        if "DB_PATH" in os.environ:
            del os.environ["DB_PATH"]

    def setUp(self):
        # Fresh database for every test
        if os.path.exists(self.temp_db_file):
            os.remove(self.temp_db_file)
        self.database.init_db()

    def make_request(self, method, path, headers=None, body=None):
        """Helper to make simulated API requests to handlers."""
        if headers is None:
            headers = {}
        body_bytes = b""
        if body is not None:
            body_bytes = json.dumps(body).encode("utf-8")
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(body_bytes))
        
        status, resp_headers, resp_body = self.handlers.handle_api_request(
            method, path, headers, body_bytes
        )
        
        # Decode body
        try:
            if isinstance(resp_body, bytes):
                decoded_body = resp_body.decode("utf-8")
            else:
                decoded_body = resp_body
            resp_data = json.loads(decoded_body) if decoded_body else {}
        except Exception:
            resp_data = decoded_body if decoded_body else {}
            
        return status, resp_headers, resp_data

    def get_token(self, email, password="password123"):
        """Helper to login and get session token."""
        status, _, body = self.make_request(
            "POST", "/api/auth/login", body={"email": email, "password": password}
        )
        if status == 200:
            return body.get("token")
        return None

    def get_auth_headers(self, token):
        """Helper to generate auth headers."""
        return {"Authorization": f"Bearer {token}"}
