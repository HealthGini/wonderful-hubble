import unittest
import json
from base_test import BaseTestCase

class TestFeed(BaseTestCase):

    def test_get_feed_unauthenticated(self):
        """Tests feed retrieval for unauthenticated users (sorted by score/reactions)."""
        status, _, body = self.make_request("GET", "/api/feed")
        self.assertEqual(status, 200)
        feed = body.get("feed", [])
        self.assertEqual(len(feed), 5)
        
        # Verify scores are calculated (only reactions should count)
        # Item 2: 4 reactions (score 4)
        # Item 1: 3 reactions (score 3)
        # Item 5: 3 reactions (score 3)
        # Item 3: 2 reactions (score 2)
        # Item 4: 2 reactions (score 2)
        
        scores = [item["_score"] for item in feed]
        self.assertEqual(scores[0], 4) # Item 2 must be first
        self.assertIn(scores[1], (3, 3))
        
        # Verify scores are descending.
        for i in range(len(scores) - 1):
            self.assertTrue(scores[i] >= scores[i+1], f"Scores not descending: {scores}")

    def test_get_feed_smart_sort_authenticated(self):
        """Tests smart sort for authenticated user (boosts joined groups)."""
        # Login as Elena (user 3). Joined groups: 1, 3. NOT 2.
        token = self.get_token("elena@gooddeeds.space")
        headers = self.get_auth_headers(token)
        
        status, _, body = self.make_request("GET", "/api/feed?sort=smart", headers=headers)
        self.assertEqual(status, 200)
        feed = body.get("feed", [])
        
        # Elena joined Group 1 and 3.
        # Item 2 (G1): 100 + 4 = 104
        # Item 5 (G3): 100 + 3 = 103
        # Item 1 (G3): 100 + 3 = 103
        # Item 3 (G1): 100 + 2 = 102
        # Item 4 (G2): 0 + 2 = 2
        
        scores = [item["_score"] for item in feed]
        self.assertEqual(scores, [104, 103, 103, 102, 2])
        
        # Verify IDs.
        actual_ids = [item["id"] for item in feed]
        self.assertEqual(actual_ids[0], 2)
        self.assertSetEqual(set(actual_ids[1:3]), {1, 5})
        self.assertEqual(actual_ids[3], 3)
        self.assertEqual(actual_ids[4], 4)

    def test_get_feed_recency_sort(self):
        """Tests sorting by recency with explicit timestamps."""
        # Since seed data might have identical timestamps, we manually update them
        # in the DB to ensure different times for testing recency sort.
        conn = self.database.get_db()
        cursor = conn.cursor()
        # Set different timestamps for feed items
        # Item 1: oldest, Item 5: newest
        cursor.execute("UPDATE feed_items SET created_at = '2026-06-25 00:00:01' WHERE id = 1")
        cursor.execute("UPDATE feed_items SET created_at = '2026-06-25 00:00:02' WHERE id = 2")
        cursor.execute("UPDATE feed_items SET created_at = '2026-06-25 00:00:03' WHERE id = 3")
        cursor.execute("UPDATE feed_items SET created_at = '2026-06-25 00:00:04' WHERE id = 4")
        cursor.execute("UPDATE feed_items SET created_at = '2026-06-25 00:00:05' WHERE id = 5")
        conn.commit()
        conn.close()

        status, _, body = self.make_request("GET", "/api/feed?sort=recent")
        self.assertEqual(status, 200)
        feed = body.get("feed", [])
        
        expected_ids = [5, 4, 3, 2, 1]
        actual_ids = [item["id"] for item in feed]
        self.assertEqual(actual_ids, expected_ids)

    def test_get_feed_recency_sort_dynamic(self):
        """Tests recency sorting by dynamically creating a new post."""
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)
        new_post = {
            "title": "Brand New Post",
            "theme": "Education",
            "content": "This should be the absolute newest item.",
            "group_ids": []
        }
        status, _, body = self.make_request("POST", "/api/posts", 
                                                 headers=headers,
                                                 body=new_post)
        self.assertEqual(status, 201)
        new_item_id = body["item"]["id"]

        # Request recent sort feed
        status, _, body = self.make_request("GET", "/api/feed?sort=recent")
        self.assertEqual(status, 200)
        feed = body.get("feed", [])
        self.assertEqual(feed[0]["id"], new_item_id)

    def test_feed_filter_by_theme(self):
        """Tests filtering feed by theme."""
        status, _, body = self.make_request("GET", "/api/feed?theme=Mental Health")
        self.assertEqual(status, 200)
        feed = body.get("feed", [])
        
        # Only Post 2 has theme "Mental Health"
        self.assertEqual(len(feed), 1)
        self.assertEqual(feed[0]["id"], 2)
        self.assertEqual(feed[0]["theme"], "Mental Health")

    def test_feed_filter_by_group(self):
        """Tests filtering feed by group ID."""
        # Filter by Group 3 (Community Action)
        # Seed items in Group 3: Item 1 (Kudos) and Item 5 (Post)
        status, _, body = self.make_request("GET", "/api/feed?group_id=3")
        self.assertEqual(status, 200)
        feed = body.get("feed", [])
        
        self.assertEqual(len(feed), 2)
        item_ids = {item["id"] for item in feed}
        self.assertEqual(item_ids, {1, 5})

    def test_feed_filter_by_type(self):
        """Tests filtering feed by item type (KUDOS/POST)."""
        status, _, body = self.make_request("GET", "/api/feed?filter_type=KUDOS")
        self.assertEqual(status, 200)
        feed = body.get("feed", [])
        self.assertEqual(len(feed), 2)
        for item in feed:
            self.assertEqual(item["item_type"], "KUDOS")

        status, _, body = self.make_request("GET", "/api/feed?filter_type=POST")
        self.assertEqual(status, 200)
        feed = body.get("feed", [])
        self.assertEqual(len(feed), 3)
        for item in feed:
            self.assertEqual(item["item_type"], "POST")

    def test_feed_search(self):
        """Tests text search on feed items."""
        # Search for "Marcus" (matches Item 1 content)
        status, _, body = self.make_request("GET", "/api/feed?search=Marcus")
        self.assertEqual(status, 200)
        feed = body.get("feed", [])
        
        self.assertEqual(len(feed), 1)
        self.assertEqual(feed[0]["id"], 1)
        self.assertIn("Marcus", feed[0]["content"])

        # Search "positivity" (matches Item 1 and Item 2)
        status, _, body = self.make_request("GET", "/api/feed?search=positivity")
        self.assertEqual(status, 200)
        feed = body.get("feed", [])
        self.assertEqual(len(feed), 2)
        self.assertEqual({item["id"] for item in feed}, {1, 2})

if __name__ == "__main__":
    unittest.main()
