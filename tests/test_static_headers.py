import unittest
import os
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from base_test import BaseTestCase
import server

class TestStaticHeadersAndStartup(BaseTestCase):
    httpd = None
    server_port = 0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.GoodDeedsServerHandler)
        cls.server_port = cls.httpd.server_port
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        if cls.httpd:
            cls.httpd.shutdown()
            cls.httpd.server_close()
        super().tearDownClass()

    def test_static_asset_cache_headers(self):
        """Verifies static file HTTP responses contain explicit cache control directives."""
        url = f"http://127.0.0.1:{self.server_port}/app.js"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            self.assertEqual(response.status, 200)
            headers = response.headers
            self.assertEqual(headers.get("Cache-Control"), "no-cache, no-store, must-revalidate")
            self.assertEqual(headers.get("Pragma"), "no-cache")
            self.assertEqual(headers.get("Expires"), "0")

    def test_initial_feed_queries_clean(self):
        """Verifies initial feed query returns 200 cleanly and validates structure."""
        status, headers, body = self.make_request("GET", "/api/feed")
        self.assertEqual(status, 200)
        self.assertIn("feed", body)
        self.assertIsInstance(body["feed"], list)

if __name__ == "__main__":
    unittest.main()
