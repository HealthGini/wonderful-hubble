import os
import sys
import io
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(TESTS_DIR)
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

from tests.base_test import BaseTestCase
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

    def test_ui_regressions_compliance(self):
        """Verifies static HTML and JS satisfy 100% of UI regression requirements."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        html_path = os.path.join(base_dir, "static", "index.html")
        js_path = os.path.join(base_dir, "static", "app.js")

        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        with open(js_path, "r", encoding="utf-8") as f:
            js_content = f.read()

        # 1. Navbar Dropdowns
        self.assertIn("👥 Spaces", html_content)
        self.assertIn("Browse Spaces & Create New →", html_content)
        self.assertIn("My Joined Spaces", html_content)
        self.assertIn("🌟 Kudos", html_content)
        self.assertIn("📝 Posts", html_content)
        self.assertNotIn("👥 Groups", html_content)
        self.assertNotIn("🌟 Kudos Hub", html_content)
        self.assertNotIn("📝 Posts Hub", html_content)

        # 2. Feed Toolbar
        self.assertIn('placeholder="Search Kudos, Posts, Events and Resources..."', html_content)
        self.assertNotIn('id="feed-sort-select"', html_content)
        self.assertIn('id="theme-pills-bar"', html_content)
        for topic in ["All Topics", "✨ Inspiring Story", "🌱 Mental Health", "🌿 Wellness", "🧘 Mindfulness", "🕊️ Spiritual", "🛡️ Suicide Prevention", "🎓 Educational", "🤝 Community Service", "📅 Events", "📎 Resources"]:
            self.assertIn(topic, html_content)

        # 3. Create Post Modal
        self.assertIn('placeholder="e.g. Free Senior Tutoring & Mentorship Workshop"', html_content)
        self.assertIn('name="post_subtype"', html_content)
        self.assertIn('id="post-event-date-container"', html_content)
        self.assertIn('id="post-input-theme"', html_content)
        for th in ["Inspiring Story", "Mental Health", "Wellness", "Mindfulness", "Spiritual", "Suicide Prevention", "Educational", "Community Service"]:
            self.assertIn(f'value="{th}"', html_content)
        self.assertIn('Files', html_content)
        self.assertIn('*(Attach downloadable guides, flyers, or images)*', html_content)

        # 4. Give Kudos Modal
        self.assertIn('id="kudos-recipient-input"', html_content)
        self.assertIn('id="kudos-recipient-id"', html_content)
        self.assertNotIn('<select id="kudos-recipient"', html_content)

        # 5. Add Space Resources
        self.assertIn('id="curate-step-1"', html_content)
        self.assertIn('id="curate-step-2"', html_content)
        self.assertIn('id="curate-event-date-container"', html_content)

        # 6. Create Community Space Modal
        self.assertIn('<select id="cgrp-theme"', html_content)
        for space_cat in ["Mental Health", "Wellness", "Spiritual", "Education", "Community Service"]:
            self.assertIn(f'value="{space_cat}"', html_content)

        # 7. Space Detail Tabs & Cards
        self.assertIn("👥 Members List", html_content)
        self.assertIn("Enter Space ↗", js_content)
