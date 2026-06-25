import unittest
import json
from base_test import BaseTestCase

class TestPosts(BaseTestCase):

    def test_create_post_success(self):
        """Tests successful Post creation and group tagging."""
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)
        
        post_data = {
            "title": "New Test Post",
            "theme": "Education",
            "content": "This is a new test post content.",
            "resource_url": "http://example.com/resource.pdf",
            "group_ids": [2] # Tag to Education group
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=headers, body=post_data)
        self.assertEqual(status, 201)
        self.assertTrue(body["success"])
        self.assertIn("item", body)
        self.assertEqual(body["item"]["title"], post_data["title"])
        self.assertEqual(body["item"]["item_type"], "POST")
        self.assertEqual(body["item"]["author_name"], "Maya_Lin")
        
        # Verify it was tagged to group 2
        self.assertEqual(len(body["item"]["groups"]), 1)
        self.assertEqual(body["item"]["groups"][0]["id"], 2)

    def test_create_post_unauthorized(self):
        """Tests Post creation fails when unauthenticated."""
        post_data = {
            "title": "New Test Post",
            "theme": "Education",
            "content": "This is a new test post content."
        }
        status, _, _ = self.make_request("POST", "/api/posts", body=post_data)
        self.assertEqual(status, 401)

    def test_create_kudos_success(self):
        """Tests successful Kudos creation and email outbox logging."""
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)
        
        # Arthur_74 (id 4) is recipient
        kudos_data = {
            "recipient_id": 4,
            "content": "Thanks Arthur for the history lesson!",
            "group_ids": [2]
        }
        status, _, body = self.make_request("POST", "/api/kudos", headers=headers, body=kudos_data)
        self.assertEqual(status, 201)
        self.assertTrue(body["success"])
        self.assertIn("item", body)
        self.assertEqual(body["item"]["item_type"], "KUDOS")
        self.assertEqual(body["item"]["recipient_name"], "Arthur_74")

        # Verify email notification was logged in outbox
        conn = self.database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM email_outbox ORDER BY id DESC LIMIT 1")
        email = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(email)
        self.assertEqual(email["recipient_email"], "arthur@gooddeeds.space")
        self.assertIn("You received new Kudos", email["subject"])
        self.assertIn("Thanks Arthur", email["body"])

    def test_create_kudos_unauthorized(self):
        """Tests Kudos creation fails when unauthenticated."""
        kudos_data = {"recipient_id": 4, "content": "Thanks"}
        status, _, _ = self.make_request("POST", "/api/kudos", body=kudos_data)
        self.assertEqual(status, 401)

    def test_create_kudos_invalid_recipient(self):
        """Tests Kudos creation fails if recipient does not exist."""
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)
        kudos_data = {"recipient_id": 999, "content": "Thanks"}
        status, _, body = self.make_request("POST", "/api/kudos", headers=headers, body=kudos_data)
        self.assertEqual(status, 400)
        self.assertIn("recipient user not found", body["error"].lower())

    def test_react_toggle(self):
        """Tests emoji reaction toggling (adding and removing)."""
        token = self.get_token("maya@gooddeeds.space") # User 1
        headers = self.get_auth_headers(token)
        
        # In seed data, User 1 (Maya) already reacted to Item 2 (Post by Elena) with "❤️"
        # Let's verify it is there first
        status, _, body = self.make_request("GET", "/api/feed/2", headers=headers)
        self.assertIn("❤️", body["item"]["user_reactions"])
        
        # Toggle reaction (should remove)
        status, _, body = self.make_request("POST", "/api/reactions", headers=headers, body={"item_id": 2, "emoji": "❤️"})
        self.assertEqual(status, 200)
        self.assertEqual(body["action"], "removed")

        # Verify it is removed
        status, _, body = self.make_request("GET", "/api/feed/2", headers=headers)
        self.assertNotIn("❤️", body["item"]["user_reactions"])

        # Toggle again (should add)
        status, _, body = self.make_request("POST", "/api/reactions", headers=headers, body={"item_id": 2, "emoji": "❤️"})
        self.assertEqual(status, 200)
        self.assertEqual(body["action"], "added")

        # Verify it is added
        status, _, body = self.make_request("GET", "/api/feed/2", headers=headers)
        self.assertIn("❤️", body["item"]["user_reactions"])

    def test_add_comment(self):
        """Tests adding a comment to a feed item."""
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)
        
        comment_data = {
            "item_id": 2,
            "content": "This is a new comment."
        }
        status, _, body = self.make_request("POST", "/api/comments", headers=headers, body=comment_data)
        self.assertEqual(status, 201)
        self.assertTrue(body["success"])
        self.assertIn("comment", body)
        self.assertEqual(body["comment"]["content"], comment_data["content"])
        self.assertEqual(body["comment"]["author_name"], "Maya_Lin")

        # Verify comment is in the feed item
        status, _, body = self.make_request("GET", "/api/feed/2")
        comments = body["item"]["comments"]
        self.assertTrue(any(c["content"] == comment_data["content"] for c in comments))

    def test_direct_links(self):
        """Tests retrieving single items via direct link endpoints."""
        # Test GET /api/posts/2 (POST)
        status, _, body = self.make_request("GET", "/api/posts/2")
        self.assertEqual(status, 200)
        self.assertEqual(body["post"]["id"], 2)
        self.assertEqual(body["post"]["item_type"], "POST")

        # Test GET /api/kudos/1 (KUDOS)
        status, _, body = self.make_request("GET", "/api/kudos/1")
        self.assertEqual(status, 200)
        self.assertEqual(body["kudos"]["id"], 1)
        self.assertEqual(body["kudos"]["item_type"], "KUDOS")

        # Test GET /api/feed/2 (General)
        status, _, body = self.make_request("GET", "/api/feed/2")
        self.assertEqual(status, 200)
        self.assertEqual(body["item"]["id"], 2)

        # Test invalid ID
        status, _, _ = self.make_request("GET", "/api/posts/999")
        self.assertEqual(status, 404)

if __name__ == "__main__":
    unittest.main()
