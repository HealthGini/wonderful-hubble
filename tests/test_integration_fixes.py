import os
import sys
import io
import unittest
from base_test import BaseTestCase
import server

class DummyServerHandler(server.GoodDeedsServerHandler):
    def __init__(self, path):
        self.path = path
        self.headers_sent = {}
        self.response_code = None
        self.wfile = io.BytesIO()

    def send_response(self, code, message=None):
        self.response_code = code

    def send_header(self, keyword, value):
        self.headers_sent[keyword] = value

    def end_headers(self):
        pass

class TestIntegrationFixes(BaseTestCase):

    def test_static_asset_cache_control_headers(self):
        """Tests that static assets (.js, .css, .html) are served with cache control headers."""
        for asset_path in ["/app.js", "/style.css", "/index.html", "/"]:
            handler = DummyServerHandler(asset_path)
            handler.serve_static_file()
            self.assertEqual(handler.response_code, 200)
            self.assertEqual(handler.headers_sent.get("Cache-Control"), "no-cache, no-store, must-revalidate")
            self.assertEqual(handler.headers_sent.get("Pragma"), "no-cache")
            self.assertEqual(handler.headers_sent.get("Expires"), "0")

    def test_initial_feed_query_authenticated_and_unauthenticated(self):
        """Tests that initial feed queries for unauthenticated and authenticated users operate cleanly."""
        # 1. Unauthenticated feed query
        status, _, body = self.make_request("GET", "/api/feed?sort=smart")
        self.assertEqual(status, 200)
        self.assertIn("feed", body)
        self.assertIsInstance(body["feed"], list)

        # 2. Authenticated feed query
        token = self.get_token("maya@gooddeeds.space")
        self.assertIsNotNone(token)
        headers = self.get_auth_headers(token)
        status, _, body = self.make_request("GET", "/api/feed?sort=smart", headers=headers)
        self.assertEqual(status, 200)
        self.assertIn("feed", body)
        self.assertIsInstance(body["feed"], list)
