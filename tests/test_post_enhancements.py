import unittest
import json
from base_test import BaseTestCase

class TestPostEnhancements(BaseTestCase):

    def test_create_posts_with_new_themes(self):
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)

        new_themes = [
            ("Wellness", "Wellness Post Title", "Content focused on daily wellness habits."),
            ("Mindfulness", "Mindfulness Post Title", "Content focused on meditation and grounding."),
        ]

        for theme_name, title, content in new_themes:
            post_data = {
                "title": title,
                "theme": theme_name,
                "content": content,
                "resource_url": "https://example.com/guide.pdf"
            }
            status, _, body = self.make_request("POST", "/api/posts", headers=headers, body=post_data)
            self.assertEqual(status, 201, f"Failed to create post with theme {theme_name}")
            self.assertTrue(body.get("success"))
            self.assertIn("item", body)
            self.assertEqual(body["item"]["theme"], theme_name)
            self.assertEqual(body["item"]["title"], title)

    def test_feed_filter_by_new_themes(self):
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)

        new_themes = ["Wellness", "Mindfulness"]
        created_items = {}

        for theme_name in new_themes:
            post_data = {
                "title": f"Title for {theme_name}",
                "theme": theme_name,
                "content": f"Exploring {theme_name} practice in the community.",
            }
            status, _, body = self.make_request("POST", "/api/posts", headers=headers, body=post_data)
            self.assertEqual(status, 201)
            created_items[theme_name] = body["item"]["id"]

        for theme_name in new_themes:
            status, _, body = self.make_request("GET", f"/api/feed?theme={theme_name}")
            self.assertEqual(status, 200)
            items = body.get("feed", [])
            self.assertGreater(len(items), 0, f"Expected items for theme {theme_name}")

            for item in items:
                self.assertEqual(item["theme"], theme_name)

            item_ids = [item["id"] for item in items]
            self.assertIn(created_items[theme_name], item_ids)

    def test_create_post_invalid_theme(self):
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)
        post_data = {
            "title": "Invalid Theme Post",
            "theme": "InvalidThemeName",
            "content": "This post uses an unsupported theme."
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=headers, body=post_data)
        self.assertEqual(status, 400)
        self.assertFalse(body.get("success", True))
        self.assertIn("Invalid theme", body.get("error", ""))

    def test_seed_post_updates_and_subtypes(self):
        status, _, body = self.make_request("GET", "/api/feed")
        self.assertEqual(status, 200)
        feed = body.get("feed", [])
        post4 = next((item for item in feed if "Free Online Tutoring & Mentorship Fair This Saturday" in (item.get("title") or "")), None)
        self.assertIsNotNone(post4)
        self.assertIn(post4["theme"], ["Educational", "Education"])
        self.assertIn(post4["post_subtype"], ["EVENT", "Upcoming Community Event"])

if __name__ == "__main__":
    unittest.main()
