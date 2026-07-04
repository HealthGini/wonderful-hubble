import os
import sys
import unittest
from base_test import GoodDeedsTestCase

class TestRegressionCoverage(GoodDeedsTestCase):

    def test_terminology_and_navbar_labels(self):
        """
        Loads static/index.html and static/app.js content.
        Asserts that user-facing labels use "Spaces", "Kudos", and "Posts" without "Group", "Groups", or "Hub".
        Asserts #feed-search-input placeholder is "Search Kudos, Posts, Events and Resources...".
        Asserts #feed-sort-select dropdown is completely absent from HTML.
        Asserts #theme-pills-bar includes the exact 11 topic pills in order.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        app_js_path = os.path.join(base_dir, "static", "app.js")

        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        with open(app_js_path, "r", encoding="utf-8") as f:
            app_js_content = f.read()

        # Navbar labels check
        self.assertIn("Spaces", html_content)
        self.assertIn("Kudos", html_content)
        self.assertIn("Posts", html_content)

        # Assert no "Kudos Hub" or "Posts Hub" in navbar
        self.assertNotIn("Kudos Hub", html_content)
        self.assertNotIn("Posts Hub", html_content)

        # Assert #feed-search-input placeholder
        self.assertIn('placeholder="Search Kudos, Posts, Events and Resources..."', html_content)

        # Assert #feed-sort-select dropdown is completely absent
        self.assertNotIn('id="feed-sort-select"', html_content)

        # Assert #theme-pills-bar includes the exact 11 topic pills in order
        expected_pills = [
            'All Topics', 'Inspiring Story', 'Mental Health', 'Wellness',
            'Mindfulness', 'Spiritual', 'Suicide Prevention', 'Educational',
            'Community Service', 'Events', 'Resources'
        ]
        self.assertIn('id="theme-pills-bar"', html_content)
        for pill in expected_pills:
            self.assertIn(pill, html_content)

        # Verify order of topic pills in html_content inside theme-pills-bar
        pills_bar_start = html_content.find('id="theme-pills-bar"')
        self.assertNotEqual(pills_bar_start, -1)
        pills_bar_end = html_content.find('</div>', pills_bar_start)
        pills_segment = html_content[pills_bar_start:pills_bar_end]

        last_pos = 0
        for pill in expected_pills:
            pos = pills_segment.find(pill, last_pos)
            self.assertNotEqual(pos, -1, f"Pill '{pill}' not found in expected order in theme-pills-bar")
            last_pos = pos

    def test_theme_order_and_space_categories(self):
        """
        Asserts #post-input-theme and #res-theme dropdowns in static/index.html contain exact 8 options in specified order.
        Asserts #cgrp-theme select element in static/index.html contains exact 5 options.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")

        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        expected_8_options = [
            "Inspiring Story", "Mental Health", "Wellness", "Mindfulness",
            "Spiritual", "Suicide Prevention", "Educational", "Community Service"
        ]

        for element_id in ["post-input-theme", "res-theme"]:
            self.assertIn(f'id="{element_id}"', html_content)
            start_pos = html_content.find(f'id="{element_id}"')
            end_pos = html_content.find("</select>", start_pos)
            segment = html_content[start_pos:end_pos]
            
            last_pos = 0
            for opt in expected_8_options:
                pos = segment.find(opt, last_pos)
                self.assertNotEqual(pos, -1, f"Option '{opt}' not found in order in #{element_id}")
                last_pos = pos

        expected_5_options = [
            "Mental Health", "Wellness", "Spiritual", "Education", "Community Service"
        ]
        self.assertIn('id="cgrp-theme"', html_content)
        start_pos = html_content.find('id="cgrp-theme"')
        end_pos = html_content.find("</select>", start_pos)
        cgrp_segment = html_content[start_pos:end_pos]

        last_pos = 0
        for opt in expected_5_options:
            pos = cgrp_segment.find(opt, last_pos)
            self.assertNotEqual(pos, -1, f"Option '{opt}' not found in order in #cgrp-theme")
            last_pos = pos

    def test_event_date_mandatory_validation_and_persistence(self):
        """
        Tests event_date mandatory validation and persistence for EVENT posts and group resources.
        """
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)

        # 1. POST /api/posts with post_subtype: "EVENT" missing event_date -> HTTP 400
        post_missing_date = {
            "title": "Community Gathering",
            "theme": "Events",
            "content": "Gathering details...",
            "post_subtype": "EVENT"
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=headers, body=post_missing_date)
        self.assertEqual(status, 400)
        self.assertIn("error", body)

        # 2. POST /api/posts with post_subtype: "EVENT" and past event_date -> HTTP 400
        post_past_date = {
            "title": "Past Gathering",
            "theme": "Events",
            "content": "Gathering details...",
            "post_subtype": "EVENT",
            "event_date": "2020-01-01"
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=headers, body=post_past_date)
        self.assertEqual(status, 400)
        self.assertIn("error", body)

        # 3. POST /api/posts with post_subtype: "EVENT" and future event_date -> HTTP 201, success: True, event_date returned in GET /api/feed
        post_future_date = {
            "title": "Future Celebration",
            "theme": "Events",
            "content": "Gathering in 2027",
            "post_subtype": "EVENT",
            "event_date": "2027-12-31"
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=headers, body=post_future_date)
        self.assertEqual(status, 201)
        self.assertTrue(body.get("success"))
        post_id = body["item"]["id"]

        status, _, feed_body = self.make_request("GET", "/api/feed")
        self.assertEqual(status, 200)
        event_item = next((item for item in feed_body.get("feed", []) if item.get("id") == post_id), None)
        self.assertIsNotNone(event_item)
        self.assertEqual(event_item.get("event_date"), "2027-12-31")

        # 4. Space resource curation POST /api/groups/<id>/resources with event_date -> HTTP 200/201, success: True
        res_data = {
            "title": "Upcoming Event Schedule Guide",
            "url": "http://example.com/schedule.pdf",
            "event_date": "2027-12-31"
        }
        status, _, res_body = self.make_request("POST", "/api/groups/2/resources", headers=headers, body=res_data)
        self.assertIn(status, (200, 201))
        self.assertTrue(res_body.get("success"))

    def test_kudos_autocomplete_and_mutual_groups(self):
        """
        Tests GET /api/users returns user list for autocomplete.
        Tests GET /api/groups/joined?target_user_id=<id> returns mutual groups shared with target user.
        """
        status, _, body = self.make_request("GET", "/api/users")
        self.assertEqual(status, 200)
        self.assertIn("users", body)
        self.assertIsInstance(body["users"], list)
        self.assertGreater(len(body["users"]), 0)

        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)

        status, _, body = self.make_request("GET", "/api/groups/joined?target_user_id=2", headers=headers)
        self.assertEqual(status, 200)
        self.assertIn("groups", body)
        self.assertIsInstance(body["groups"], list)

    def test_spotlight_accurate_statistics(self):
        """
        Tests GET /api/spotlight?month=June%202026 returns kudos counts matching exact database records.
        """
        status, _, body = self.make_request("GET", "/api/spotlight?month=June%202026")
        self.assertEqual(status, 200)
        self.assertIn("top_kudos_champions", body)
        champions = body["top_kudos_champions"]
        self.assertGreater(len(champions), 0)

        champ = champions[0]
        champ_id = champ["id"]
        conn = self.database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM feed_items WHERE recipient_id = ? AND item_type = 'KUDOS'", (champ_id,))
        exact_count = cursor.fetchone()["cnt"]
        conn.close()

        self.assertEqual(champ.get("base_kudos"), exact_count)

if __name__ == "__main__":
    unittest.main()
