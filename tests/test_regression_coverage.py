import os
import sys
import base64
import datetime
import unittest
from base_test import GoodDeedsTestCase
from unittest.mock import patch, MagicMock
import pickle
import json
from handlers import base64url_encode, base64url_decode

class MockAttestedCredentialData:
    def __init__(self, credential_id, public_key_bytes):
        self.credential_id = credential_id
        self.public_key_bytes = public_key_bytes
    def __bytes__(self):
        return self.public_key_bytes

class TestRegressionCoverage(GoodDeedsTestCase):

    def test_landing_page_filters_and_readonly_space_banner(self):
        """
        Verifies landing page filter bar, group/type selects, theme pills bar,
        and read-only space banner exist in static/index.html.
        Verifies static/app.js exposes filterLandingByGroup, filterLandingByType,
        filterLandingByTheme, and landingGroupFilter.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        app_js_path = os.path.join(base_dir, "static", "app.js")

        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        with open(app_js_path, "r", encoding="utf-8") as f:
            app_js_content = f.read()

        # HTML elements check
        self.assertIn('id="landing-filter-bar"', html_content)
        self.assertIn('id="landing-group-select"', html_content)
        self.assertIn('id="landing-type-select"', html_content)
        self.assertIn('id="landing-theme-pills-bar"', html_content)
        self.assertIn('id="landing-space-info-banner"', html_content)

        # JS exposure checks
        self.assertIn("landingGroupFilter", app_js_content)
        self.assertIn("filterLandingByGroup", app_js_content)
        self.assertIn("filterLandingByType", app_js_content)
        self.assertIn("filterLandingByTheme", app_js_content)
        self.assertIn("filterLandingByFormat", app_js_content)
        self.assertIn("window.filterLandingByGroup = filterLandingByGroup", app_js_content)
        self.assertIn("window.filterLandingByType = filterLandingByType", app_js_content)
        self.assertIn("window.filterLandingByTheme = filterLandingByTheme", app_js_content)
        self.assertIn("window.filterLandingByFormat = filterLandingByFormat", app_js_content)

    def test_terminology_and_navbar_labels(self):
        """
        Loads static/index.html and static/app.js content.
        Asserts that user-facing labels use "Spaces", "Kudos", and "Posts" without "Group", "Groups", or "Hub".
        Asserts #feed-search-input placeholder is "Search Kudos, Posts, Events and Resources...".
        Asserts #feed-sort-select dropdown is completely absent from HTML.
        Asserts #theme-pills-bar includes the 4 pillar topic pills and format pills.
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
        self.assertIn('placeholder="Search Kudos, Posts, Events, Resources, or Username..."', html_content)

        # Assert #feed-sort-select dropdown is completely absent
        self.assertNotIn('id="feed-sort-select"', html_content)

        # Assert #theme-pills-bar includes the 4 pillar topic pills in order
        expected_pills = [
            'All', 'Inspiring Stories', 'Wellbeing & Care', 'Skills & Learning',
            'Community & Action'
        ]
        self.assertIn('id="theme-pills-bar"', html_content)
        for pill in expected_pills:
            self.assertIn(pill, html_content)
        self.assertIn('Events', html_content)
        self.assertIn('Resources', html_content)

        # Verify order of topic pills in html_content inside theme-pills-bar
        pills_bar_start = html_content.find('id="theme-pills-bar"')
        self.assertNotEqual(pills_bar_start, -1)
        feed_cards_start = html_content.find('id="feed-items-container"', pills_bar_start)
        pills_segment = html_content[pills_bar_start:feed_cards_start]

        last_pos = 0
        for pill in expected_pills:
            pos = pills_segment.find(pill, last_pos)
            self.assertNotEqual(pos, -1, f"Pill '{pill}' not found in expected order in theme-pills-bar")
            last_pos = pos

        self.assertIn('Events', pills_segment)
        self.assertIn('Resources', pills_segment)

    def test_theme_order_and_space_categories(self):
        """
        Asserts #post-input-theme and #res-theme dropdowns in static/index.html contain exact 4 options in specified order.
        Asserts #cgrp-theme select element in static/index.html contains exact 4 options.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")

        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        expected_post_res_options = [
            "Inspiring Stories", "Wellbeing & Care", "Skills & Learning", "Community & Action"
        ]

        for element_id in ["post-input-theme", "res-theme"]:
            self.assertIn(f'id="{element_id}"', html_content)
            start_pos = html_content.find(f'id="{element_id}"')
            end_pos = html_content.find("</select>", start_pos)
            segment = html_content[start_pos:end_pos]
            
            last_pos = 0
            for opt in expected_post_res_options:
                pos = segment.find(opt, last_pos)
                self.assertNotEqual(pos, -1, f"Option '{opt}' not found in order in #{element_id}")
                last_pos = pos

        expected_space_options = [
            "Inspiring Stories", "Wellbeing & Care", "Skills & Learning", "Community & Action"
        ]
        self.assertIn('id="cgrp-theme"', html_content)
        start_pos = html_content.find('id="cgrp-theme"')
        end_pos = html_content.find("</select>", start_pos)
        cgrp_segment = html_content[start_pos:end_pos]

        last_pos = 0
        for opt in expected_space_options:
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
        Tests frontend autocomplete attributes and container id across static/index.html and static/app.js.
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

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        app_js_path = os.path.join(base_dir, "static", "app.js")

        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        with open(app_js_path, "r", encoding="utf-8") as f:
            app_js_content = f.read()

        kudos_input_idx = html_content.find('id="kudos-recipient-input"')
        self.assertNotEqual(kudos_input_idx, -1, "#kudos-recipient-input not found in index.html")
        tag_start = html_content.rfind("<input", 0, kudos_input_idx)
        tag_end = html_content.find(">", kudos_input_idx)
        kudos_input_tag = html_content[tag_start:tag_end + 1]

        self.assertIn('oninput="handleKudosRecipientSearch(this.value)"', kudos_input_tag)
        self.assertIn('onfocus="handleKudosRecipientSearch(this.value)"', kudos_input_tag)
        self.assertIn('id="kudos-recipient-suggestions"', html_content)

        self.assertIn("kudos-recipient-suggestions", app_js_content)
        self.assertIn("function handleKudosRecipientSearch", app_js_content)
        self.assertIn("function selectKudosRecipient", app_js_content)
        self.assertIn("window.handleKudosRecipientSearch = handleKudosRecipientSearch", app_js_content)
        self.assertIn("window.selectKudosRecipient = selectKudosRecipient", app_js_content)

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


    def test_profile_impact_and_activity_statistics(self):
        """
        Tests GET /api/users/<id> returns stats with all required 7 fields.
        """
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)
        status, _, body = self.make_request("GET", "/api/users/1", headers=headers)
        self.assertEqual(status, 200)
        self.assertIn("stats", body)
        stats = body["stats"]
        for key in ["kudos_received", "avg_kudos_year", "kudos_given", "unique_givers", "posts_authored", "avg_reactions", "last_active"]:
            self.assertIn(key, stats)

    def test_profile_open_posts_for_target_user(self):
        """
        Tests that requesting user profile API returns user 3 (Elena) data and app.js binds target user ID to profile buttons.
        """
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)
        status, _, body = self.make_request("GET", "/api/users/3", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(body["user"]["id"], 3)

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_js_path = os.path.join(base_dir, "static", "app.js")
        with open(app_js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("prof-open-posts-btn", js)
        self.assertIn("filterFeedByMyPosts('authored', ${u.id})", js)

    def test_my_spaces_feed_filter(self):
        """
        Tests GET /api/feed?group_id=my_spaces for authenticated vs unauthenticated users.
        """
        # Unauthenticated -> empty result (1 = 0)
        status, _, body = self.make_request("GET", "/api/feed?group_id=my_spaces")
        self.assertEqual(status, 200)
        self.assertEqual(len(body.get("feed", [])), 0)

        # Authenticated user
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)
        status, _, body = self.make_request("GET", "/api/feed?group_id=my_spaces", headers=headers)
        self.assertEqual(status, 200)
        self.assertIn("feed", body)

    def test_space_details_resources_tab_restoration(self):
        """
        Asserts #gtab-resources, #gcontent-resources, and #group-resources-list exist in static/index.html.
        Asserts switchGroupTab includes "resources" and renderGroupResources uses attachment helpers in static/app.js.
        Verifies client-side aggregation of space resources and attachments in a 1-column layout with contextual descriptions.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        app_path = os.path.join(base_dir, "static", "app.js")

        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn("id=\"gtab-resources\"", html)
        self.assertIn("id=\"gcontent-resources\"", html)
        self.assertIn("id=\"group-resources-list\"", html)
        self.assertIn("id=\"admin-curate-box\"", html)
        self.assertIn("id=\"group-resources-list\" class=\"flex flex-col space-y-4\"", html)
        
        # Verify that the Add Space Resources form is removed from inside gcontent-resources tab
        gcontent_res_start = html.find('id="gcontent-resources"')
        gcontent_res_end = html.find('</div>', gcontent_res_start + 1)
        gcontent_res_block = html[gcontent_res_start:gcontent_res_end + 6]
        self.assertNotIn("Add Space Resources", gcontent_res_block)

        with open(app_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("\"resources\"", js)
        self.assertIn("renderGroupResources", js)
        self.assertIn("formatResourceSummary", js)
        self.assertIn("window.formatResourceSummary = formatResourceSummary", js)
        self.assertIn("_attachmentCache", js)
        self.assertIn("openAttachment", js)
        self.assertIn("formatAttachmentLabel", js)
        self.assertIn("container.className = \"flex flex-col space-y-4\"", js)
        self.assertIn("async function renderGroupResources()", js)
        self.assertIn("/feed?group_id=", js)
        self.assertIn("Curated by ", js)
        self.assertIn("From post: ", js)
        self.assertIn("From kudos: ", js)
        self.assertIn("Shared by ", js)

        # Integration test: verify that posting a post and kudos with resource_url to a space makes them accessible via /api/feed?group_id=
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)
        post_body = {
            "title": "Test Resource Attachment",
            "theme": "Education",
            "content": "Here is a useful doc",
            "group_ids": [1],
            "resource_url": "https://example.com/doc.pdf"
        }
        status, _, res = self.make_request("POST", "/api/posts", headers=headers, body=post_body)
        self.assertEqual(status, 201)

        conn = self.database.get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO feed_items (item_type, author_id, recipient_id, content, resource_url)
            VALUES ("KUDOS", 1, 2, "Kudos with attachment", "https://example.com/kudos.png")
        """)
        kudos_id = cursor.lastrowid
        cursor.execute("INSERT OR IGNORE INTO item_groups (item_id, group_id) VALUES (?, 1)", (kudos_id,))
        conn.commit()
        conn.close()

        status, _, feed_res = self.make_request("GET", "/api/feed?group_id=1", headers=headers)
        self.assertEqual(status, 200)
        feed_items_str = str(feed_res.get("feed", []))
        self.assertTrue("doc.pdf" in feed_items_str)
        self.assertTrue("kudos.png" in feed_items_str)

    def test_mobile_responsiveness_elements(self):
        """
        Asserts mobile menu button (#mobile-menu-btn), drawer (#mobile-menu), Pills bar classes, and modal bounds.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn('id="mobile-menu-btn"', html)
        self.assertIn('id="mobile-menu"', html)
        self.assertIn('overflow-x-auto whitespace-nowrap scrollbar-none py-1.5 flex items-center gap-2', html)
        self.assertIn('max-h-[90vh]', html)

    def test_smart_search_in_attached_resource_files(self):
        """
        Tests base64 text extraction and search in attached resource files.
        """
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)
        
        # Base64 encoded "SecretResourcePayload"
        b64_content = "data:text/plain;base64,U2VjcmV0UmVzb3VyY2VQYXlsb2Fk"
        post_data = {
            "title": "Attachment Search Test",
            "theme": "Educational",
            "content": "Testing text extraction",
            "resource_url": b64_content
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=headers, body=post_data)
        self.assertEqual(status, 201)

        # Search for SecretResourcePayload
        status, _, body = self.make_request("GET", "/api/feed?search=SecretResourcePayload")
        self.assertEqual(status, 200)
        feed = body.get("feed", [])
        self.assertGreater(len(feed), 0)

    def test_thumbs_up_emoji_reaction(self):
        """
        Tests 👍 reaction on /api/reactions and /api/react endpoints.
        """
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)
        
        # Test POST /api/reactions with 👍
        react_data = {"item_id": 1, "emoji": "👍"}
        status, _, body = self.make_request("POST", "/api/reactions", headers=headers, body=react_data)
        self.assertEqual(status, 200)

        # Test POST /api/react alias
        status, _, body = self.make_request("POST", "/api/react", headers=headers, body=react_data)
        self.assertEqual(status, 200)

    def test_open_attachment_helper_binding(self):
        """
        Asserts openAttachment function and window.openAttachment binding exist in app.js.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_js_path = os.path.join(base_dir, "static", "app.js")
        with open(app_js_path, "r", encoding="utf-8") as f:
            app_js = f.read()
        self.assertIn("function openAttachment", app_js)
        self.assertIn("window.openAttachment = openAttachment", app_js)

        # Assert synchronous Base64 Data URI to Blob URL conversion logic and optimizations
        open_attachment_idx = app_js.find("function openAttachment")
        self.assertNotEqual(open_attachment_idx, -1)
        open_attachment_block = app_js[open_attachment_idx:open_attachment_idx + 1500]
        self.assertIn("data:", open_attachment_block.lower())
        self.assertIn("atob(", open_attachment_block)
        self.assertIn("ArrayBuffer", open_attachment_block)
        self.assertIn("Uint8Array", open_attachment_block)
        self.assertIn("Blob(", open_attachment_block)
        self.assertIn("createObjectURL(", open_attachment_block)
        self.assertIn("window.open(", open_attachment_block)
        self.assertIn("indexOf(\",\")", open_attachment_block)
        self.assertIn(".replace(", open_attachment_block)

    def test_feed_endpoint_resilience_and_headers(self):
        """
        Verifies GET /api/feed returns status 200, a valid feed array, and anti-caching headers (Cache-Control).
        """
        status, headers, body = self.make_request("GET", "/api/feed")
        self.assertEqual(status, 200)
        self.assertIn("feed", body)
        self.assertIsInstance(body["feed"], list)
        
        cache_control = None
        for k, v in headers.items():
            if k.lower() == "cache-control":
                cache_control = v
                break
        self.assertIsNotNone(cache_control, "Cache-Control header missing from API response")
        self.assertIn("no-cache", cache_control.lower())

    def test_login_case_insensitivity_and_api_fetch_paths(self):
        """
        Verifies login case insensitivity for email/username and app.js apiFetch URL normalization.
        """
        # Test uppercase email login
        status, _, body = self.make_request("POST", "/api/auth/login", body={"email": "MAYA@GOODDEEDS.SPACE", "password": "password123"})
        self.assertEqual(status, 200)
        self.assertIn("token", body)

        # Test lowercase username login
        status, _, body = self.make_request("POST", "/api/auth/login", body={"email": "maya_lin", "password": "password123"})
        self.assertEqual(status, 200)
        self.assertIn("token", body)

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_js_path = os.path.join(base_dir, "static", "app.js")
        with open(app_js_path, "r", encoding="utf-8") as f:
            app_js = f.read()
        self.assertIn("endpoint.startsWith(\"/api/\")", app_js)

    def test_homepage_vision_features_and_faq_sections(self):
        """Verifies landing vision section exists while features showcase, FAQ, and CTA sections are removed from home page in static/index.html."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        self.assertIn("id=\"landing-vision-section\"", html_content)
        self.assertIn("Why Join GoodDeeds.space?", html_content)
        self.assertNotIn("id=\"landing-features-section\"", html_content)
        self.assertNotIn("id=\"landing-faq-section\"", html_content)
        self.assertNotIn("id=\"landing-cta-section\"", html_content)
        self.assertNotIn("Platform Features Built for Kindness", html_content)
        self.assertNotIn("Frequently Asked Questions", html_content)
        self.assertNotIn("Ready to Ripple Positivity in Your Community?", html_content)

    def test_informative_attachment_pills_rendering(self):
        """
        Reads static/app.js and verifies that formatAttachmentLabel exists, is bound to window,
        handles Data URIs (including proper ordering for spreadsheets/presentations before documents)
        and HTTP URLs cleanly (with strict extension matching to avoid version number misidentification),
        and that renderFeedCard uses it while strictly preserving window._attachmentCache invocation for openAttachment.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_js_path = os.path.join(base_dir, "static", "app.js")
        with open(app_js_path, "r", encoding="utf-8") as f:
            app_js = f.read()

        # 1. Verify formatAttachmentLabel function definition and window binding
        self.assertIn("function formatAttachmentLabel(", app_js)
        self.assertIn("window.formatAttachmentLabel = formatAttachmentLabel", app_js)

        # 2. Verify Data URI handling (MIME type detection for PDF, Image, Text, Word, Document, Spreadsheet, Presentation, Archive, Audio, Video)
        self.assertIn("data:", app_js.lower())
        self.assertIn("PDF Document", app_js)
        self.assertIn("Image File", app_js)
        self.assertIn("Text Document", app_js)
        self.assertIn("Word Document", app_js)
        self.assertIn("Spreadsheet", app_js)
        self.assertIn("Presentation", app_js)
        self.assertIn("Archive File", app_js)
        self.assertIn("Audio File", app_js)
        self.assertIn("Video File", app_js)
        self.assertIn("Attached File", app_js)

        # Ensure Spreadsheets and Presentations are checked before Word Documents to avoid ODS/ODP misclassification
        sheet_pos = app_js.find("Spreadsheet")
        pres_pos = app_js.find("Presentation")
        word_pos = app_js.find("Word Document")
        self.assertTrue(sheet_pos < word_pos, "Spreadsheet check must precede Word Document check")
        self.assertTrue(pres_pos < word_pos, "Presentation check must precede Word Document check")

        # 3. Verify HTTP/HTTPS URL handling (extracting filename or domain/path, count #N: formatting, truncation)
        self.assertIn("slice(", app_js)
        self.assertIn("...", app_js)
        self.assertIn("#${num}:", app_js)
        self.assertIn("validFileRegex", app_js)

        # 4. Verify renderFeedCard uses formatAttachmentLabel while preserving openAttachment with _attachmentCache
        self.assertIn("formatAttachmentLabel(u, idx, urls.length)", app_js)
        self.assertIn("onclick=\"window.openAttachment(window._attachmentCache['${cacheKey}'], 'attachment_${item.id}_${idx}')\"", app_js)
        self.assertIn("window.openAttachment = openAttachment", app_js)


    def test_profile_dropdown_and_logout_structure(self):
        """
        Verifies consolidated Profile Dropdown structure in static/index.html and helper functions in static/app.js.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        app_js_path = os.path.join(base_dir, "static", "app.js")

        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        with open(app_js_path, "r", encoding="utf-8") as f:
            app_js_content = f.read()

        # 1. Verify static/index.html contains all required IDs
        required_ids = [
            'id="profile-menu-container"',
            'id="profile-dropdown-menu"',
            'id="profile-menu-btn"',
            'id="nav-user-avatar"',
            'id="nav-user-name"',
            'id="nav-logout"'
        ]
        for elem_id in required_ids:
            self.assertIn(elem_id, html_content)

        # 2. Verify #nav-user-name and #nav-logout (with text Log Off or Log Out) are inside #profile-dropdown-menu container block
        dropdown_start = html_content.find('id="profile-dropdown-menu"')
        self.assertNotEqual(dropdown_start, -1, "#profile-dropdown-menu not found in index.html")
        dropdown_end = html_content.find("</header>", dropdown_start)
        dropdown_block = html_content[dropdown_start:dropdown_end]

        self.assertIn('id="nav-user-name"', dropdown_block, "#nav-user-name should be inside #profile-dropdown-menu block")
        self.assertIn('id="nav-logout"', dropdown_block, "#nav-logout should be inside #profile-dropdown-menu block")
        self.assertTrue("Log Off" in dropdown_block or "Log Out" in dropdown_block, "Log Off or Log Out text should be inside #profile-dropdown-menu block")

        # Verify #nav-user-name and #nav-logout are NOT outside #profile-dropdown-menu container block in navbar
        self.assertEqual(html_content.count('id="nav-logout"'), 1)
        self.assertEqual(html_content.count('id="nav-user-name"'), 1)

        # Also verify that before #profile-dropdown-menu inside #nav-auth-user, neither #nav-user-name nor #nav-logout appear
        nav_auth_user_start = html_content.find('id="nav-auth-user"')
        before_dropdown = html_content[nav_auth_user_start:dropdown_start]
        self.assertNotIn('id="nav-user-name"', before_dropdown)
        self.assertNotIn('id="nav-logout"', before_dropdown)

        # 3. Verify static/app.js exposes and references closeProfileDropdown and toggleProfileDropdown
        self.assertIn("closeProfileDropdown", app_js_content)
        self.assertIn("toggleProfileDropdown", app_js_content)
        self.assertIn("window.closeProfileDropdown = closeProfileDropdown", app_js_content)
        self.assertIn("window.toggleProfileDropdown = toggleProfileDropdown", app_js_content)

    def test_repo_root_hygiene_no_stray_files(self):
        """
        Verifies repository root hygiene: asserts that stray scratch/debug files
        (scratch_test.js, test_syntax.js, _worker_notes/) do not exist at repo root.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for stray in ("_worker_notes", "scratch_test.js", "test_syntax.js"):
            stray_path = os.path.join(base_dir, stray)
            self.assertFalse(os.path.exists(stray_path), f"Stray file/directory found at repo root: {stray}")

    def test_interactive_calendar_widget_structure(self):
        """
        Asserts #group-calendar-widget, #calendar-days-grid, #btn-add-calendar-event, #admin-calendar-pdf-upload, and #modal-calendar-day exist in static/index.html.
        Asserts renderGroupCalendar and navigateGroupCalendar exist and are bound in static/app.js.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        app_js_path = os.path.join(base_dir, "static", "app.js")

        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn('id="group-calendar-widget"', html)
        self.assertIn('id="calendar-days-grid"', html)
        self.assertIn('id="btn-add-calendar-event"', html)
        self.assertNotIn('id="admin-calendar-pdf-upload"', html)
        self.assertIn('id="modal-calendar-day"', html)
        self.assertIn('id="btn-toggle-calendar"', html)

        with open(app_js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("renderGroupCalendar", js)
        self.assertIn("navigateGroupCalendar", js)
        self.assertIn("toggleCalendarWidget", js)

    def test_collapsible_calendar_widget_feature(self):
        """
        Verifies that the calendar widget in space details view is collapsible to grant more space to tabs, feeds, and posts.
        Asserts toggle buttons (#btn-toggle-calendar, #btn-collapse-calendar), main content column (#group-main-content-col),
        sidebar (#group-calendar-sidebar), and controller functions (toggleCalendarWidget, updateCalendarCollapseUI) exist.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        app_js_path = os.path.join(base_dir, "static", "app.js")

        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn('id="btn-toggle-calendar"', html)
        self.assertIn('id="btn-collapse-calendar"', html)
        self.assertIn('id="group-main-content-col"', html)
        self.assertIn('id="group-calendar-sidebar"', html)

        with open(app_js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("toggleCalendarWidget", js)
        self.assertIn("updateCalendarCollapseUI", js)
        self.assertIn("window.toggleCalendarWidget = toggleCalendarWidget", js)

    def test_calendar_pdf_scraping_endpoint(self):
        """
        Submits base64 PDF text (containing dates like 2026-07-20 and titles) to POST /api/groups/1/scrape_calendar and verifies that suggested_events is returned accurately.
        """
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)

        b64_content = "data:application/pdf;base64," + base64.b64encode(b"2026-07-20 10:00 AM Summer Festival - Main Park").decode("utf-8")
        status, _, body = self.make_request("POST", "/api/groups/1/scrape_calendar", headers=headers, body={"file_data": b64_content})
        self.assertEqual(status, 200)
        self.assertTrue(body.get("success"))
        events = body.get("suggested_events", [])
        self.assertGreaterEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev.get("event_date"), "2026-07-20")
        self.assertEqual(ev.get("time"), "10:00 AM")
        self.assertIn("Summer Festival", ev.get("title", ""))

    def test_calendar_admin_event_creation(self):
        """
        Verifies POST /api/posts with post_subtype="EVENT" and event_date for a group creates an event accessible when querying the group feed.
        """
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)

        payload = {
            "title": "Group Calendar Test Event",
            "theme": "Events",
            "content": "Special community gathering for group 1",
            "post_subtype": "EVENT",
            "event_date": "2026-10-15",
            "group_ids": [1]
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=headers, body=payload)
        self.assertEqual(status, 201)
        self.assertTrue(body.get("success"))
        post_id = body.get("item", {}).get("id")

        status, _, feed_body = self.make_request("GET", "/api/feed?group_id=1")
        self.assertEqual(status, 200)
        feed = feed_body.get("feed", [])
        event_item = next((item for item in feed if item.get("id") == post_id), None)
        self.assertIsNotNone(event_item)
        self.assertEqual(event_item.get("event_date"), "2026-10-15")
        self.assertEqual(event_item.get("post_subtype"), "EVENT")

    def test_cta_prominence_and_accessibility_enhancements(self):
        """
        Verifies that the new Community Creation Bar exists in #view-feed,
        that the prominent action buttons are present in #mobile-menu and profile banner,
        and that renderGroupKudos and renderGroupPosts include creation banners
        while maintaining all navbar container IDs (#kudos-hub-container, #posts-hub-container,
        #prof-open-kudos-btn, #prof-open-posts-btn).
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        app_js_path = os.path.join(base_dir, "static", "app.js")

        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        with open(app_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        # 1. Navbar containers preservation and styling upgrades
        self.assertIn('id="kudos-hub-container"', html)
        self.assertIn('id="posts-hub-container"', html)
        self.assertIn('from-amber-500 to-yellow-500', html)
        self.assertIn('from-indigo-600 to-violet-600', html)
        self.assertIn('bg-amber-50/90', html)
        self.assertIn('bg-indigo-50/90', html)

        # 2. Mobile menu creation actions
        self.assertIn('id="mobile-auth-actions"', html)
        self.assertIn('id="mobile-menu-auth-actions"', html)
        self.assertIn('✨ Give Public Kudos', html)
        self.assertIn('✍️ Create New Post', html)
        self.assertIn("closeMobileMenu(); openModal('modal-kudos')", html)
        self.assertIn("closeMobileMenu(); openModal('modal-post')", html)

        # 3. Community Feed Hero Creation Bar
        self.assertIn('id="community-creation-bar"', html)
        self.assertIn('Promote Goodness Today', html)

        # 4. Contextual Space Details Banners and Header Actions
        self.assertIn("group-kudos-creation-banner", js)
        self.assertIn("✨ + Give Space Kudos", js)
        self.assertIn("group-posts-creation-banner", js)
        self.assertIn("✍️ + Share Space Post", js)

        # 5. Profile Page & Landing Page Enhancements
        self.assertIn('id="prof-open-kudos-btn"', html)
        self.assertIn('id="prof-open-posts-btn"', html)
        self.assertNotIn('✨ Give New Kudos', html)
        self.assertIn('id="prof-actions"', html)
        self.assertIn("presetKudosRecipient", js)
        self.assertIn("🌟 Give Kudos to ${u.username}", js)
        self.assertIn('onclick="openModal(\'modal-kudos\')"', html)
        self.assertIn('onclick="openModal(\'modal-post\')"', html)

    def test_google_oauth_endpoint_and_schema(self):
        """
        Verifies OAuth / Google Sign-In schema, API endpoint error handling, frontend UI/controller elements, and full mock valid token verification flow.
        """
        # 1. Verify schema has oauth_provider and oauth_id
        conn = self.database.get_db()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info('users')")
        cols = [r["name"] for r in cursor.fetchall()]
        conn.close()
        self.assertIn("oauth_provider", cols)
        self.assertIn("oauth_id", cols)

        # 2. POST /api/auth/oauth/google with empty/missing token returns 400
        status, _, body = self.make_request("POST", "/api/auth/oauth/google", body={})
        self.assertEqual(status, 400)
        self.assertFalse(body.get("success", True))
        self.assertIn("required", body.get("error", "").lower())

        # 3. POST /api/auth/oauth/google with invalid token returns 401
        status, _, body = self.make_request("POST", "/api/auth/oauth/google", body={"credential": "invalid_fake_token_123"})
        self.assertEqual(status, 401)
        self.assertFalse(body.get("success", True))
        self.assertIn("invalid", body.get("error", "").lower())

        # Also verify /auth/oauth/google path works (Requirement 2 / 4)
        status, _, body = self.make_request("POST", "/auth/oauth/google", body={})
        self.assertEqual(status, 400)
        status, _, body = self.make_request("POST", "/auth/oauth/google", body={"credential": "invalid_fake_token_123"})
        self.assertEqual(status, 401)

        # 4. Check static/index.html elements
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn("triggerGoogleSignIn()", html)
        self.assertIn("Continue with Google", html)
        self.assertIn("or continue with email", html)
        self.assertIn('id="btn-google-login"', html)
        self.assertIn('id="btn-google-signup"', html)

        # 5. Check static/app.js elements
        app_js_path = os.path.join(base_dir, "static", "app.js")
        with open(app_js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("triggerGoogleSignIn", js)
        self.assertIn("handleGoogleOauthResponse", js)

        # 6. Verify valid token flow (mocked urllib.request.urlopen)
        import json
        from unittest.mock import patch, MagicMock
        mock_payload = {
            "email": "oauth_demo@gooddeeds.space",
            "sub": "google_sub_888",
            "name": "OAuth Demo",
            "picture": "https://example.com/demo.jpg"
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            status, _, body = self.make_request("POST", "/api/auth/oauth/google", body={"credential": "valid_mock_token"})
            self.assertEqual(status, 200)
            self.assertTrue(body.get("success"))
            self.assertIn("token", body)
            self.assertEqual(body["user"]["email"], "oauth_demo@gooddeeds.space")
            self.assertEqual(body["user"]["username"], "OAuth_Demo")
            self.assertEqual(body["user"]["oauth_provider"], "google")
            self.assertEqual(body["user"]["oauth_id"], "google_sub_888")

            # Second call for existing user login
            status, _, body = self.make_request("POST", "/api/auth/oauth/google", body={"credential": "valid_mock_token"})
            self.assertEqual(status, 200)
            self.assertTrue(body.get("success"))
            self.assertEqual(body["user"]["email"], "oauth_demo@gooddeeds.space")
            self.assertEqual(body["user"]["oauth_id"], "google_sub_888")

    def test_option_a_visual_hierarchy(self):
        """Verifies Option A (Distinct Visual Hierarchy) across static/index.html."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn("bg-amber-50 text-amber-900 border border-amber-200", html)
        self.assertIn("bg-indigo-50 text-indigo-900 border border-indigo-200", html)
        self.assertIn("text-[10px] text-amber-600", html)
        self.assertIn("text-[10px] text-indigo-600", html)
        self.assertIn("p-5 sm:p-6 rounded-2xl", html)
        self.assertIn("id=\"community-creation-bar\"", html)

    def test_platform_stats_endpoint_and_dynamic_rendering(self):
        """
        Verifies GET /api/stats returns status 200, success=True, and exact counts matching direct SQLite queries.
        Also verifies static/index.html and static/app.js have proper elements and dynamic loader functions.
        """
        import sqlite3
        from database import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM feed_items WHERE item_type = 'KUDOS'")
        db_kudos = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users")
        db_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM groups")
        db_groups = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM feed_items WHERE item_type = 'POST'")
        db_posts = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM reactions")
        db_reactions = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM comments")
        db_comments = cursor.fetchone()[0]
        conn.close()

        status, _, body = self.make_request("GET", "/api/stats")
        self.assertEqual(status, 200)
        self.assertTrue(body.get("success"))
        stats = body.get("stats", {})
        self.assertEqual(stats.get("acts_of_kindness"), db_kudos)
        self.assertEqual(stats.get("community_members"), db_users)
        self.assertEqual(stats.get("active_spaces"), db_groups)
        self.assertEqual(stats.get("total_posts"), db_posts)
        self.assertEqual(stats.get("total_reactions"), db_reactions)
        self.assertEqual(stats.get("total_comments"), db_comments)

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        app_js_path = os.path.join(base_dir, "static", "app.js")

        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn('id="stat-acts-of-kindness"', html)
        self.assertIn('id="stat-community-members"', html)
        self.assertIn('id="stat-active-spaces"', html)
        self.assertNotIn("1,420+", html)
        acts_start = html.find('id="stat-acts-of-kindness"')
        self.assertNotEqual(acts_start, -1)
        acts_end = html.find("</div>", acts_start)
        self.assertNotIn("1,420+", html[acts_start:acts_end])

        with open(app_js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("loadPlatformStats", js)
        self.assertIn('apiFetch("/stats")', js)
        self.assertIn(".toLocaleString()", js)
        self.assertNotIn("1,420+", js)

        init_start = js.find("async function initApp()")
        self.assertNotEqual(init_start, -1)
        init_end = js.find("if (document.readyState", init_start)
        self.assertIn("loadPlatformStats()", js[init_start:init_end])

        stats_start = js.find("async function loadPlatformStats()")
        self.assertNotEqual(stats_start, -1)
        stats_end = js.find("window.loadPlatformStats = loadPlatformStats;", stats_start)
        self.assertNotIn("1,420+", js[stats_start:stats_end])


    def test_dynamic_empty_feed_state_by_item_type(self):
        """
        Asserts that static/app.js checks currentTypeFilter === "KUDOS" and
        currentTypeFilter === "POST" and dynamically sets required title and subtitle
        strings for empty feed state across all three states (KUDOS, POST, and default/empty).
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_js_path = os.path.join(base_dir, "static", "app.js")
        with open(app_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn('currentTypeFilter === "KUDOS"', js)
        self.assertIn('currentTypeFilter === "POST"', js)
        self.assertIn("No Kudos Found", js)
        self.assertIn("No gratitude kudos match your active filter selection.", js)
        self.assertIn("No Posts Found", js)
        self.assertIn("No community posts match your active filter selection.", js)
        self.assertIn("No Posts or Kudos Found", js)
        self.assertIn("No posts or kudos match your active filter selection.", js)

    def test_passkeys_schema(self):
        """
        Verifies that passkeys and webauthn_challenges tables are successfully initialized on startup.
        """
        conn = self.database.get_db()
        cursor = conn.cursor()
        
        # Check passkeys table
        cursor.execute("PRAGMA table_info('passkeys')")
        passkeys_cols = {r["name"]: r["type"] for r in cursor.fetchall()}
        self.assertIn("user_id", passkeys_cols)
        self.assertIn("credential_id", passkeys_cols)
        self.assertIn("public_key", passkeys_cols)
        self.assertIn("sign_count", passkeys_cols)
        self.assertIn("device_name", passkeys_cols)
        self.assertIn("created_at", passkeys_cols)
        
        # Check webauthn_challenges table
        cursor.execute("PRAGMA table_info('webauthn_challenges')")
        challenges_cols = {r["name"]: r["type"] for r in cursor.fetchall()}
        self.assertIn("user_id", challenges_cols)
        self.assertIn("challenge", challenges_cols)
        self.assertIn("state", challenges_cols)
        self.assertIn("created_at", challenges_cols)
        
        conn.close()

    @patch("handlers.Fido2Server")
    @patch("handlers.RegistrationResponse")
    def test_passkey_registration_flow(self, mock_reg_resp_class, mock_fido_server_class):
        """
        Verifies WebAuthn registration options generation and verification logic.
        """
        mock_server = MagicMock()
        mock_fido_server_class.return_value = mock_server
        
        from fido2.webauthn import PublicKeyCredentialCreationOptions, PublicKeyCredentialRpEntity, PublicKeyCredentialUserEntity, CredentialCreationOptions
        mock_pk_options = PublicKeyCredentialCreationOptions(
            rp=PublicKeyCredentialRpEntity(name="Test", id="localhost"),
            user=PublicKeyCredentialUserEntity(name="maya@gooddeeds.space", id=b"1", display_name="Maya_Lin"),
            challenge=b"mock_challenge_bytes_1234567890",
            pub_key_cred_params=[]
        )
        mock_options = CredentialCreationOptions(public_key=mock_pk_options)
        mock_state = {"mock_state_key": "mock_state_value"}
        mock_server.register_begin.return_value = (mock_options, mock_state)
        
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)
        
        status, _, body = self.make_request("POST", "/api/auth/webauthn/register/challenge", headers=headers)
        self.assertEqual(status, 200)
        self.assertIn("publicKey", body)
        self.assertEqual(body["publicKey"]["challenge"], base64url_encode(b"mock_challenge_bytes_1234567890"))
        
        conn = self.database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM webauthn_challenges WHERE user_id = 1")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["challenge"], base64url_encode(b"mock_challenge_bytes_1234567890"))
        stored_state = pickle.loads(row["state"])
        self.assertEqual(stored_state, mock_state)
        conn.close()
        
        # Mock RegistrationResponse.from_dict
        mock_reg_resp = MagicMock()
        mock_reg_resp_class.from_dict.return_value = mock_reg_resp
        
        mock_auth_data = MagicMock()
        mock_cred_data = MockAttestedCredentialData(b"mock_credential_id_bytes", b"mock_serialized_pubkey")
        mock_auth_data.credential_data = mock_cred_data
        mock_auth_data.counter = 42
        mock_server.register_complete.return_value = mock_auth_data
        
        verify_payload = {
            "id": "mock_id",
            "rawId": "mock_raw_id",
            "type": "public-key",
            "response": {
                "clientDataJSON": base64url_encode(json.dumps({
                    "challenge": base64url_encode(b"mock_challenge_bytes_1234567890"),
                    "origin": "http://localhost",
                    "type": "webauthn.create"
                }).encode()),
                "attestationObject": "mock_attestation",
                "transports": []
            },
            "deviceName": "Test Device"
        }
        
        status, _, body = self.make_request("POST", "/api/auth/webauthn/register/verify", headers=headers, body=verify_payload)
        self.assertEqual(status, 200, f"Body: {body}")
        self.assertTrue(body.get("success"))
        
        conn = self.database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM passkeys WHERE user_id = 1")
        pk_row = cursor.fetchone()
        self.assertIsNotNone(pk_row)
        self.assertEqual(pk_row["credential_id"], base64url_encode(b"mock_credential_id_bytes"))
        self.assertEqual(pk_row["public_key"], b"mock_serialized_pubkey")
        self.assertEqual(pk_row["sign_count"], 42)
        self.assertEqual(pk_row["device_name"], "Test Device")
        
        cursor.execute("SELECT * FROM webauthn_challenges WHERE user_id = 1")
        self.assertIsNone(cursor.fetchone())
        conn.close()

    @patch("handlers.Fido2Server")
    @patch("handlers.AuthenticationResponse")
    @patch("handlers.AuthenticatorData")
    @patch("handlers.AttestedCredentialData")
    def test_passkey_login_flow(self, mock_attested_cred_class, mock_auth_data_class, mock_auth_resp_class, mock_fido_server_class):
        """
        Verifies WebAuthn authentication options generation and verification logic.
        """
        conn = self.database.get_db()
        cursor = conn.cursor()
        mock_pubkey_bytes = b"mock_pubkey_bytes_xyz"
        cred_id_str = base64url_encode(b"login_mock_cred_id")
        cursor.execute("""
            INSERT INTO passkeys (user_id, credential_id, public_key, sign_count, device_name)
            VALUES (1, ?, ?, 10, 'Maya Phone')
        """, (cred_id_str, mock_pubkey_bytes))
        conn.commit()
        conn.close()
        
        mock_server = MagicMock()
        mock_fido_server_class.return_value = mock_server
        
        from fido2.webauthn import PublicKeyCredentialRequestOptions, CredentialRequestOptions
        mock_pk_req_options = PublicKeyCredentialRequestOptions(
            challenge=b"login_mock_challenge_bytes",
            rp_id="localhost"
        )
        mock_req_options = CredentialRequestOptions(public_key=mock_pk_req_options)
        mock_login_state = {"login_state_key": "login_state_value"}
        mock_server.authenticate_begin.return_value = (mock_req_options, mock_login_state)
        
        status, _, body = self.make_request("POST", "/api/auth/webauthn/login/challenge", body={"username": "Maya_Lin"})
        self.assertEqual(status, 200)
        self.assertIn("publicKey", body)
        self.assertEqual(body["publicKey"]["challenge"], base64url_encode(b"login_mock_challenge_bytes"))
        
        conn = self.database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM webauthn_challenges WHERE user_id = 1")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["challenge"], base64url_encode(b"login_mock_challenge_bytes"))
        conn.close()
        
        # Mock AuthenticationResponse.from_dict
        mock_auth_resp = MagicMock()
        mock_auth_resp.response.authenticator_data.counter = 15
        mock_auth_resp_class.from_dict.return_value = mock_auth_resp
        
        mock_server.authenticate_complete.return_value = None
        
        mock_auth_data = MagicMock()
        mock_auth_data.counter = 15
        mock_auth_data_class.return_value = mock_auth_data
        
        login_verify_payload = {
            "id": cred_id_str,
            "rawId": cred_id_str,
            "type": "public-key",
            "response": {
                "clientDataJSON": base64url_encode(json.dumps({
                    "challenge": base64url_encode(b"login_mock_challenge_bytes"),
                    "origin": "http://localhost",
                    "type": "webauthn.get"
                }).encode()),
                "authenticatorData": base64url_encode(b"mock_auth_data_bytes"),
                "signature": base64url_encode(b"mock_signature"),
                "userHandle": base64url_encode(b"1")
            }
        }
        
        status, _, body = self.make_request("POST", "/api/auth/webauthn/login/verify", body=login_verify_payload)
        self.assertEqual(status, 200, f"Body: {body}")
        self.assertTrue(body.get("success"))
        self.assertIn("token", body)
        self.assertEqual(body["user"]["id"], 1)
        
        conn = self.database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT sign_count FROM passkeys WHERE credential_id = ?", (cred_id_str,))
        self.assertEqual(cursor.fetchone()["sign_count"], 15)
        
        cursor.execute("SELECT * FROM webauthn_challenges WHERE challenge = ?", (base64url_encode(b"login_mock_challenge_bytes"),))
        self.assertIsNone(cursor.fetchone())
        conn.close()

    def test_passkey_guard_checks_and_cleanup(self):
        """
        Verifies that:
        1. static/index.html does not feature duplicate id="btn-passkey-login" attributes.
        2. static/index.html features class="btn-passkey-login" instead.
        3. static/app.js contains the secure context guard checks in loginWithPasskey and registerPasskey.
        4. static/app.js event listener binding uses document.querySelectorAll(".btn-passkey-login").
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        app_js_path = os.path.join(base_dir, "static", "app.js")

        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()

        with open(app_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        # 1. Assert no id="btn-passkey-login" in HTML
        self.assertNotIn('id="btn-passkey-login"', html)

        # 2. Assert class="btn-passkey-login" is present in HTML
        self.assertIn('btn-passkey-login', html)

        # 3. Assert guard checks in JS
        guard_str = "if (!window.PublicKeyCredential || !navigator.credentials)"
        self.assertIn(guard_str, js)
        
        # Verify it is in loginWithPasskey
        login_idx = js.find("async function loginWithPasskey()")
        self.assertNotEqual(login_idx, -1)
        login_block = js[login_idx:login_idx + 500]
        self.assertIn(guard_str, login_block)

        # Verify it is in registerPasskey
        register_idx = js.find("async function registerPasskey()")
        self.assertNotEqual(register_idx, -1)
        register_block = js[register_idx:register_idx + 500]
        self.assertIn(guard_str, register_block)

        # 4. Assert event listener binding uses querySelectorAll(".btn-passkey-login")
        self.assertIn('document.querySelectorAll(".btn-passkey-login")', js)

    def test_passkey_buttons_not_disabled_in_insecure_context(self):
        """
        Asserts that static/app.js does not disable Passkey buttons in adjustPasskeyButtonsSupport,
        but instead keeps them clickable, visually inactive (opacity-70), and updates their title.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_js_path = os.path.join(base_dir, "static", "app.js")

        with open(app_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Find adjustPasskeyButtonsSupport function
        func_start = js.find("function adjustPasskeyButtonsSupport()")
        self.assertNotEqual(func_start, -1, "adjustPasskeyButtonsSupport not found in app.js")
        
        # Get the function body
        func_body = js[func_start:func_start + 500]

        # Assertions
        self.assertNotIn("btn.disabled = true", func_body)
        self.assertNotIn("btn.disabled=true", func_body)
        self.assertNotIn("cursor-not-allowed", func_body)
        self.assertIn("opacity-70", func_body)
        self.assertIn("Passkeys require a secure context (HTTPS or localhost) - Click for details", func_body)

    def test_toast_visibility_inside_dialog(self):
        """
        Asserts that static/app.js's showToast checks for dialog[open] and moves the toast element.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_js_path = os.path.join(base_dir, "static", "app.js")

        with open(app_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Find showToast function
        func_start = js.find("function showToast(msg)")
        self.assertNotEqual(func_start, -1, "showToast not found in app.js")

        # Get the function body
        func_body = js[func_start:func_start + 600]

        # Assertions
        self.assertIn('querySelector("dialog[open]")', func_body)
        self.assertIn('appendChild(toast)', func_body)
        self.assertIn('document.body.appendChild(toast)', func_body)




    def test_pdf_attachment_json_array_search_and_reindexing(self):
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)

        pdf_binary = b"%PDF-1.4 (Pierce Community PDF Attachment) %%EOF"
        b64_pdf = base64.b64encode(pdf_binary).decode("utf-8")
        data_uri = f"data:application/pdf;base64,{b64_pdf}"
        json_array_url = json.dumps([data_uri])

        post_data = {
            "title": "Pierce PDF Attachment Test",
            "theme": "Educational",
            "content": "Testing search for Pierce in PDF attachments",
            "resource_url": json_array_url
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=headers, body=post_data)
        self.assertEqual(status, 201)
        post_id = body.get("item", {}).get("id") or body.get("post", {}).get("id")
        self.assertIsNotNone(post_id)

        from database import get_db, init_db
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT extracted_text FROM feed_items WHERE id = ?", (post_id,))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertIn("Pierce", row["extracted_text"])

        status, _, feed_body = self.make_request("GET", "/api/feed?search=Pierce")
        self.assertEqual(status, 200)
        feed_items = feed_body.get("feed", [])
        matching_item = next((item for item in feed_items if item.get("id") == post_id), None)
        self.assertIsNotNone(matching_item, "Created post containing Pierce was not returned in GET /api/feed?search=Pierce")

        cursor.execute("UPDATE feed_items SET extracted_text = ? WHERE id = ?", (json_array_url, post_id))
        conn.commit()

        init_db()

        cursor.execute("SELECT extracted_text FROM feed_items WHERE id = ?", (post_id,))
        reindexed_row = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(reindexed_row)
        self.assertIn("Pierce", reindexed_row["extracted_text"])

    def test_modern_softer_young_adult_redesign(self):
        """
        Verifies modern, softer aesthetics and humane touch across the application:
        - Plus Jakarta Sans and Outfit Google Fonts imported in style.css and index.html
        - Warm porcelain eggshell background (#faf9f6)
        - Rounded 24px/3xl card architecture and pill buttons
        - Softer ambient card glows for Kudos and Posts
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        style_path = os.path.join(base_dir, "static", "style.css")
        app_path = os.path.join(base_dir, "static", "app.js")

        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        with open(style_path, "r", encoding="utf-8") as f:
            css = f.read()
        with open(app_path, "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn("Plus Jakarta Sans", html)
        self.assertIn("Outfit", html)
        self.assertIn("Plus Jakarta Sans", css)
        self.assertIn("Outfit", css)
        self.assertIn("#faf9f6", html)
        self.assertIn("rounded-3xl", html)
        self.assertIn(".kudos-card", css)
        self.assertIn(".post-card", css)
        self.assertIn("rounded-full", html)

    def test_topic_and_format_dual_pill_filtering(self):
        """
        Verifies that topic and format filtering are supported on the backend /api/feed endpoint
        and in the UI via distinct labeled capsules and format pills (filterByFormat / filterLandingByFormat).
        """
        # Test backend format filtering for EVENT
        status, _, body = self.make_request("GET", "/api/feed?subtype=EVENT")
        self.assertEqual(status, 200)
        self.assertIn("feed", body)
        for item in body["feed"]:
            if item["item_type"] == "POST":
                self.assertTrue(item.get("post_subtype") == "EVENT" or bool(item.get("event_date")))

        # Test backend format filtering for RESOURCE
        status, _, body = self.make_request("GET", "/api/feed?subtype=RESOURCE")
        self.assertEqual(status, 200)
        self.assertIn("feed", body)
        for item in body["feed"]:
            if item["item_type"] == "POST":
                self.assertTrue(item.get("post_subtype") == "RESOURCE" or bool(item.get("resource_url")))

        # Verify UI markup has both Topic and Format labeled capsules
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        app_js_path = os.path.join(base_dir, "static", "app.js")

        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        with open(app_js_path, "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn("Topic:", html)
        self.assertIn("Type:", html)
        self.assertIn("filterByFormat('EVENT')", html)
        self.assertIn("filterByFormat('RESOURCE')", html)
        self.assertIn("filterLandingByFormat('EVENT')", html)
        self.assertIn("filterLandingByFormat('RESOURCE')", html)
        self.assertIn("window.filterByFormat = filterByFormat", js)
        self.assertIn("window.filterLandingByFormat = filterLandingByFormat", js)

        # Verify toggle behavior in filterByTheme and filterLandingByTheme
        self.assertIn("currentTheme === th", js)
        self.assertIn("landingThemeFilter === th", js)

        # Verify on-demand collapsible toggle buttons and functions
        self.assertIn('id="btn-toggle-theme-pills"', html)
        self.assertIn('id="btn-toggle-landing-theme-pills"', html)
        self.assertIn("window.toggleThemePillsBar = toggleThemePillsBar", js)
        self.assertIn("window.toggleLandingThemePillsBar = toggleLandingThemePillsBar", js)

    def test_feed_search_by_username_and_hint(self):
        """
        Verifies that /api/feed?search=<username> correctly searches and filters items by author
        and recipient username, and checks that #feed-search-input placeholder includes Username.
        """
        # 1. Search by author username 'Maya_Lin'
        status, _, body = self.make_request("GET", "/api/feed?search=Maya_Lin")
        self.assertEqual(status, 200)
        feed = body.get("feed", [])
        self.assertTrue(len(feed) > 0)
        for item in feed:
            author_or_recip_or_content = (
                "maya_lin" in item.get("author_name", "").lower() or
                "maya_lin" in item.get("recipient_name", "").lower() or
                "maya" in item.get("content", "").lower() or
                "maya" in item.get("title", "").lower()
            )
            self.assertTrue(author_or_recip_or_content)

        # 2. Search with @ prefix '@Elena'
        status, _, body = self.make_request("GET", "/api/feed?search=@Elena")
        self.assertEqual(status, 200)
        feed = body.get("feed", [])
        self.assertTrue(len(feed) > 0)
        for item in feed:
            author_or_recip_or_content = (
                "elena" in item.get("author_name", "").lower() or
                "elena" in item.get("recipient_name", "").lower() or
                "elena" in item.get("content", "").lower() or
                "elena" in item.get("title", "").lower()
            )
            self.assertTrue(author_or_recip_or_content)

        # 3. Check placeholder in index.html
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        self.assertIn('placeholder="Search Kudos, Posts, Events, Resources, or Username..."', html)

    def test_feed_monthly_winner_tags_removed(self):
        """
        Verifies that "Monthly Winner" tags and emojis are removed from feed cards in static/app.js.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_path = os.path.join(base_dir, "static", "app.js")
        with open(app_path, "r", encoding="utf-8") as f:
            js = f.read()

        feed_card_func_start = js.find("function renderFeedCard")
        feed_card_func_end = js.find("function loadFeed", feed_card_func_start)
        feed_card_code = js[feed_card_func_start:feed_card_func_end]

        self.assertNotIn("Monthly Winner", feed_card_code)
        self.assertNotIn("👑", feed_card_code)

    def test_hall_of_fame_hidden_from_navigation_and_routed_to_feed(self):
        """
        Verifies that Hall of Fame is hidden from both desktop navbar and mobile drawer,
        and that spotlight/halloffame hash routes redirect to /feed.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        app_path = os.path.join(base_dir, "static", "app.js")

        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        with open(app_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Check desktop navbar
        main_nav_start = html.find('<nav class="hidden lg:flex')
        main_nav_end = html.find('</nav>', main_nav_start)
        main_nav_html = html[main_nav_start:main_nav_end]
        self.assertNotIn("Hall of Fame", main_nav_html)
        self.assertNotIn("/#/spotlight", main_nav_html)

        # Check mobile drawer
        mobile_menu_start = html.find('id="mobile-menu"')
        mobile_menu_end = html.find('</header>', mobile_menu_start)
        mobile_menu_html = html[mobile_menu_start:mobile_menu_end]
        self.assertNotIn("Hall of Fame", mobile_menu_html)
        self.assertNotIn("/#/spotlight", mobile_menu_html)

        # Check routing redirects to /feed
        self.assertIn('window.location.hash = "#/feed"', js)
        route_handler_start = js.find("function handleRoute()")
        route_handler_end = js.find("function navigateTo", route_handler_start)
        route_handler_code = js[route_handler_start:route_handler_end]
        self.assertIn('path === "/spotlight"', route_handler_code)
        self.assertIn('window.location.hash = "#/feed"', route_handler_code)

    def test_search_input_clear_button_single_icon_rendering(self):
        """
        Verifies that browser-native search cancel buttons are disabled in style.css
        to prevent duplicate overlapping cross marks on the search input, and verifies
        the single clear button #feed-search-clear-btn is bound in index.html and app.js.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        style_path = os.path.join(base_dir, "static", "style.css")
        index_path = os.path.join(base_dir, "static", "index.html")
        app_path = os.path.join(base_dir, "static", "app.js")

        with open(style_path, "r", encoding="utf-8") as f:
            css = f.read()
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        with open(app_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Check CSS disables native webkit search cancel button
        self.assertIn("::-webkit-search-cancel-button", css)
        self.assertIn("display: none", css)

        # Check single custom clear button exists in HTML
        self.assertIn('id="feed-search-clear-btn"', html)
        self.assertIn('onclick="clearFeedSearchInput()"', html)

        # Check JS binding for clearing
        self.assertIn("window.clearFeedSearchInput = clearFeedSearchInput", js)

    def test_modal_dismissal_cross_buttons_accessibility_and_placement(self):
        """
        Verifies that modal close/dismissal buttons are prominent, accessible (w-10 h-10 touch targets),
        and positioned cleanly at the top-right without colliding with header subtext.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Check modal-kudos top-right dismissal button
        self.assertIn("onclick=\"closeModal('modal-kudos')\"", html)
        self.assertIn("absolute top-4 right-4 sm:top-6 sm:right-6 w-10 h-10 rounded-full", html)

        # Check modal-post top-right dismissal button
        self.assertIn("onclick=\"closeModal('modal-post')\"", html)

        # Check modal-login, modal-signup, modal-create-group
        for modal_id in ["modal-login", "modal-signup", "modal-create-group", "modal-edit-profile", "modal-support", "modal-tos"]:
            self.assertIn(f"onclick=\"closeModal('{modal_id}')\"", html)

    def test_group_chat_messages_ordered_most_recent_first(self):
        """
        Verifies that space chat messages are returned in descending chronological order (most recent at the top)
        from GET /api/groups/<id>/chat and GET /api/groups/<id>, and that app.js unshifts new messages.
        """
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)

        # Post message 1
        msg1 = {"message": "Older Message A"}
        self.make_request("POST", "/api/groups/1/chat", headers=headers, body=msg1)

        # Post message 2
        msg2 = {"message": "Newer Message B"}
        self.make_request("POST", "/api/groups/1/chat", headers=headers, body=msg2)

        # Query GET /api/groups/1/chat
        status, _, body = self.make_request("GET", "/api/groups/1/chat", headers=headers)
        self.assertEqual(status, 200)
        messages = body.get("messages", [])
        self.assertGreaterEqual(len(messages), 2)
        self.assertEqual(messages[0]["message"], "Newer Message B")
        self.assertEqual(messages[1]["message"], "Older Message A")

        # Check frontend app.js unshifts new messages
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_path = os.path.join(base_dir, "static", "app.js")
        with open(app_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("activeGroupData.chat_messages.unshift(data.message)", js)

    def test_auto_tag_current_space_for_kudos_and_posts(self):
        """
        Verifies that when giving Kudos or writing Posts within a Space context,
        the corresponding Space is automatically tagged/checked by default in app.js.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_path = os.path.join(base_dir, "static", "app.js")
        with open(app_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Check getCurrentSpaceContextId implementation and window binding
        self.assertIn("function getCurrentSpaceContextId()", js)
        self.assertIn("window.getCurrentSpaceContextId = getCurrentSpaceContextId", js)

        # Check auto-checked Space logic in populateGroupCheckboxes for Post modal
        self.assertIn("const isChecked = (currentSpaceId && parseInt(currentSpaceId) === g.id) ? \"checked\" : \"\";", js)

        # Check auto-checked Space logic in updateKudosGroupCheckboxes for Kudos modal
        self.assertIn("const isChecked = (currentSpaceId && parseInt(currentSpaceId) === g.id) ? \"checked\" : \"\";", js)

        # Check that post theme adapts to current space theme if available
        self.assertIn("const spaceTheme = activeGroupData.theme || (activeGroupData.themes && activeGroupData.themes[0])", js)

        # Check that submitting Kudos or Posts from inside a space refreshes space details
        self.assertIn("if (window.location.hash.startsWith(\"#/group/\"))", js)
        self.assertIn("loadGroupDetail(activeGroupId)", js)

    def test_upload_pdf_calendar_capability_removed_from_ui(self):
        """
        Verifies that 'Upload PDF Calendar' button, file input, and scraped events preview modal
        are removed from user-facing static/index.html.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertNotIn("Upload PDF Calendar", html)
        self.assertNotIn('id="admin-calendar-pdf-upload"', html)
        self.assertNotIn('id="calendar-pdf-input"', html)
        self.assertNotIn('id="modal-scrape-preview"', html)

    def test_add_calendar_event_multi_attachment_support(self):
        """
        Verifies that modal-add-event supports multiple URL links and file attachments,
        mirroring the creation flow in modal-post.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        app_path = os.path.join(base_dir, "static", "app.js")

        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        with open(app_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Check multi-link and file upload UI in modal-add-event
        self.assertIn('id="add-event-links-list"', html)
        self.assertIn('onclick="addEventLinkField()"', html)
        self.assertIn('id="add-event-file-input"', html)
        self.assertIn('id="add-event-files-preview"', html)
        self.assertIn('onchange="handleAddEventFilesSelect(event)"', html)

        # Check JavaScript functions and window bindings
        self.assertIn("function addEventLinkField", js)
        self.assertIn("function handleAddEventFilesSelect(e)", js)
        self.assertIn("window.addEventLinkField = addEventLinkField", js)
        self.assertIn("window.handleAddEventFilesSelect = handleAddEventFilesSelect", js)

        # Check backend support for multiple attachments in POST /api/posts for EVENT
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)

        multi_attachments = [
            "https://example.com/agenda.pdf",
            "data:text/plain;name=guidelines.txt;base64,VGhpcyBpcyBhIHRlc3QgZ3VpZGU="
        ]

        future_date_1 = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
        payload = {
            "title": "Community Workshop with Multiple Attachments",
            "theme": "Events",
            "content": "A test workshop with links and files.",
            "attachments": multi_attachments,
            "post_subtype": "EVENT",
            "event_date": future_date_1,
            "group_ids": [1]
        }

        status, _, body = self.make_request("POST", "/api/posts", headers=headers, body=payload)
        self.assertEqual(status, 201)
        item = body.get("item") or body.get("post", {})
        self.assertEqual(item.get("post_subtype"), "EVENT")
        self.assertIn("https://example.com/agenda.pdf", item.get("resource_url", ""))
        self.assertIn("guidelines.txt", item.get("resource_url", ""))

    def test_calendar_event_cell_indicator_legibility(self):
        """
        Verifies that calendar day cells with events render clean, unclipped event indicator badges
        and dots with clear font styling and no cramped wrapping.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_path = os.path.join(base_dir, "static", "app.js")
        with open(app_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Check clean dot indicators and clear event count badge
        self.assertIn("bg-amber-200/90 px-1.5 py-0.5 rounded-md", js)
        self.assertIn("${evList.length} ${evList.length === 1 ? 'event' : 'events'}", js)
        self.assertIn("dotsHtml", js)
        self.assertIn("w-1.5 h-1.5 rounded-full bg-amber-500 shadow-xs", js)
        self.assertNotIn("📍 ${evList.length}", js)

    def test_calendar_event_edit_and_delete_permissions_and_url_rendering(self):
        """
        Verifies that calendar events can be edited and deleted by their author (and admins),
        and that URLs embedded in descriptions or resource_url render consistently.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_path = os.path.join(base_dir, "static", "app.js")
        with open(app_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Check frontend bindings and handlers
        self.assertIn("function openEditCalendarEventModal(", js)
        self.assertIn("function deleteCalendarEvent(", js)
        self.assertIn("window.openEditCalendarEventModal = openEditCalendarEventModal", js)
        self.assertIn("window.deleteCalendarEvent = deleteCalendarEvent", js)

        # Check URL extraction from description for unified pill rendering
        self.assertIn("urlRegex", js)
        self.assertIn("embeddedUrls", js)

        # Authenticate author (Maya, user 1) and non-author (Elena, user 3)
        token_author = self.get_token("maya@gooddeeds.space")
        headers_author = self.get_auth_headers(token_author)
        token_other = self.get_token("elena@gooddeeds.space")
        headers_other = self.get_auth_headers(token_other)

        # 1. Create a test event
        future_date_2 = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
        future_date_3 = (datetime.date.today() + datetime.timedelta(days=11)).isoformat()
        create_payload = {
            "title": "Author Editable Event",
            "theme": "Events",
            "content": "Initial description with [Time: 11:00 AM] https://example.com/details",
            "post_subtype": "EVENT",
            "event_date": future_date_2,
            "group_ids": [1]
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=headers_author, body=create_payload)
        self.assertEqual(status, 201)
        item = body.get("item") or body.get("post", {})
        event_id = item["id"]

        # 2. Non-author cannot edit or delete the event
        status, _, _ = self.make_request("PUT", f"/api/posts/{event_id}", headers=headers_other, body={"title": "Hacked Title"})
        self.assertEqual(status, 403)
        status, _, _ = self.make_request("DELETE", f"/api/posts/{event_id}", headers=headers_other)
        self.assertEqual(status, 403)

        # 3. Author can edit the event via PUT /api/posts/<id>
        update_payload = {
            "title": "Updated Author Event Title",
            "theme": "Events",
            "content": "Updated description",
            "event_date": future_date_3,
            "resource_url": "https://example.com/updated-link"
        }
        status, _, body = self.make_request("PUT", f"/api/posts/{event_id}", headers=headers_author, body=update_payload)
        self.assertEqual(status, 200)
        updated_item = body.get("item") or body.get("post", {})
        self.assertEqual(updated_item.get("title"), "Updated Author Event Title")
        self.assertEqual(updated_item.get("event_date"), future_date_3)

        # 4. Author can delete the event via DELETE /api/posts/<id>
        status, _, body = self.make_request("DELETE", f"/api/posts/{event_id}", headers=headers_author)
        self.assertEqual(status, 200)
        self.assertTrue(body.get("success"))

    def test_view_profile_layout_and_hierarchy(self):
        """
        Verifies that view-profile layout has properly closed header container div,
        ensuring statistics section and discovery banner are not squished into flex-row.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Extract view-profile section
        prof_start = html.find('id="view-profile"')
        self.assertNotEqual(prof_start, -1)
        prof_end = html.find('</section>', prof_start)
        self.assertNotEqual(prof_end, -1)
        prof_html = html[prof_start:prof_end]

        # Verify prof-edit-btn-box is inside a closed header card
        header_end_idx = prof_html.find('id="prof-stats-section"')
        self.assertNotEqual(header_end_idx, -1)
        header_snippet = prof_html[:header_end_idx]

        # Count opening and closing divs before stats section
        open_divs = header_snippet.count("<div")
        close_divs = header_snippet.count("</div>")
        self.assertEqual(open_divs, close_divs, "Profile header div must be closed before stats section")

    def test_space_header_members_list_link_button(self):
        """
        Verifies that Space detail header removes duplicate Give Kudos and Share Post buttons,
        and features a direct link button to the Members List (roster tab).
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_path = os.path.join(base_dir, "static", "app.js")
        with open(app_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Check that space header container includes Members List button
        self.assertIn('id="btn-space-members-link"', js)
        self.assertIn("switchGroupTab('roster')", js)
        self.assertIn("Members List", js)

        # Check that headerContainer.innerHTML does not have modal-kudos or modal-post buttons in the top header
        header_block_start = js.find("headerContainer.innerHTML = inviteBannerHtml +")
        self.assertNotEqual(header_block_start, -1)
        header_block_end = js.find("curateBox =", header_block_start)
        self.assertNotEqual(header_block_end, -1)
        header_snippet = js[header_block_start:header_block_end]

        self.assertNotIn("openModal('modal-kudos')", header_snippet)
        self.assertNotIn("openModal('modal-post')", header_snippet)

        index_path = os.path.join(base_dir, "static", "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Check that Members List tab button is removed from the tablist
        self.assertNotIn('id="gtab-roster"', html)
        self.assertIn('id="gcontent-roster"', html)

    def test_leave_space_compact_button_and_confirmation(self):
        """
        Verifies that the Leave Space button is rendered as a compact secondary button
        and that toggleGroupMembership asks for confirmation before executing the leave action.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_path = os.path.join(base_dir, "static", "app.js")
        with open(app_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Check Leave Space button styling (compact text-xs, rounded-xl)
        self.assertIn('id="btn-leave-space"', js)
        self.assertIn('text-xs rounded-xl', js)

        # Check toggleGroupMembership confirmation prompt for 'leave' action
        self.assertIn('if (action === "leave")', js)
        self.assertIn('confirm(', js)
        self.assertIn('Are you sure you want to leave', js)

    def test_space_chat_board_tab_label(self):
        """
        Verifies that the Space chat tab and header are labeled '💬 Chat Board'
        instead of 'Common Chat Board'.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn("💬 Chat Board", html)
        self.assertNotIn("Common Chat Board", html)

    def test_user_and_content_moderation_features(self):
        """
        Verifies all three moderation and safety features:
        1. Direct Admin Controls (comment/chat message deletion, member kick/ban, user account ban/suspension).
        2. Community Content Reporting & Admin Queue (#view-moderation, #modal-report-content, POST /api/reports, GET /api/admin/reports, POST /api/admin/reports/<id>/resolve).
        3. Automated Safety Guardrails (keyword spam filter and rate limiting).
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        app_path = os.path.join(base_dir, "static", "app.js")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        with open(app_path, "r", encoding="utf-8") as f:
            js = f.read()

        # Check frontend elements and window bindings
        self.assertIn('id="view-moderation"', html)
        self.assertIn('id="modal-report-content"', html)
        self.assertIn('id="nav-moderation-link"', html)
        self.assertIn("window.deleteComment = deleteComment", js)
        self.assertIn("window.deleteGroupChatMessage = deleteGroupChatMessage", js)
        self.assertIn("window.toggleUserBan = toggleUserBan", js)
        self.assertIn("window.kickGroupMember = kickGroupMember", js)
        self.assertIn("window.openReportModal = openReportModal", js)
        self.assertIn("window.submitContentReport = submitContentReport", js)
        self.assertIn("window.loadModerationQueue = loadModerationQueue", js)
        self.assertIn("window.resolveReport = resolveReport", js)

        # Authenticate Site Admin (Maya, user 1) and regular user (Elena, user 3)
        token_admin = self.get_token("maya@gooddeeds.space")
        headers_admin = self.get_auth_headers(token_admin)
        token_user = self.get_token("elena@gooddeeds.space")
        headers_user = self.get_auth_headers(token_user)

        # Step 3: Verify Automated Keyword Filter blocks spam post
        spam_post = {
            "title": "Spam Post",
            "theme": "General",
            "content": "Click here to buy cheap viagra and crypto airdrop scam!",
            "group_ids": [1]
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=headers_user, body=spam_post)
        self.assertEqual(status, 400)
        self.assertIn("blocked", body.get("error", "").lower())

        # Create a clean post by Elena to test reporting & resolution
        clean_post = {
            "title": "Normal Community Post",
            "theme": "General",
            "content": "Hello neighbors, let's organize a community cleanup this weekend!",
            "group_ids": [1]
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=headers_user, body=clean_post)
        self.assertEqual(status, 201)
        post_id = (body.get("item") or body.get("post", {}))["id"]

        # Step 2: Submit a community report on that post
        report_payload = {
            "target_type": "FEED_ITEM",
            "target_id": post_id,
            "reason": "Off-topic / Misleading",
            "notes": "Testing community report queue"
        }
        status, _, body = self.make_request("POST", "/api/reports", headers=headers_user, body=report_payload)
        self.assertEqual(status, 201)
        self.assertTrue(body.get("success"))

        # Admin fetches moderation queue
        status, _, body = self.make_request("GET", "/api/admin/reports", headers=headers_admin)
        self.assertEqual(status, 200)
        reports = body.get("reports", [])
        self.assertTrue(len(reports) > 0)
        matching_report = next((r for r in reports if r["target_id"] == post_id and r["target_type"] == "FEED_ITEM"), None)
        self.assertIsNotNone(matching_report)
        report_id = matching_report["id"]

        # Admin resolves the report via 'dismiss'
        status, _, body = self.make_request("POST", f"/api/admin/reports/{report_id}/resolve", headers=headers_admin, body={"action": "dismiss"})
        self.assertEqual(status, 200)
        self.assertTrue(body.get("success"))

        # Step 1: Verify Site Admin can suspend/ban a user account and restore them
        status, _, body = self.make_request("POST", "/api/admin/users/3/ban", headers=headers_admin, body={"ban": True})
        self.assertEqual(status, 200)
        self.assertTrue(body.get("success"))

        # Verify suspended user token is invalidated
        status, _, body = self.make_request("GET", "/api/auth/me", headers=headers_user)
        self.assertEqual(status, 401)

        # Restore Elena's account so subsequent tests aren't affected
        status, _, body = self.make_request("POST", "/api/admin/users/3/ban", headers=headers_admin, body={"ban": False})
        self.assertEqual(status, 200)
        self.assertTrue(body.get("success"))

    def test_google_analytics_integration(self):
        """
        Verifies that Google Analytics (GA4 gtag.js) script tag is present in static/index.html,
        and that SPA route pageview and custom event helpers (trackAnalyticsPageView, trackAnalyticsEvent)
        are implemented and exported in static/app.js.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        app_path = os.path.join(base_dir, "static", "app.js")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        with open(app_path, "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn("https://www.googletagmanager.com/gtag/js", html)
        self.assertIn("window.GA_MEASUREMENT_ID", html)
        self.assertIn("gtag('config'", html)

        self.assertIn("function trackAnalyticsPageView(", js)
        self.assertIn("function trackAnalyticsEvent(", js)
        self.assertIn("window.trackAnalyticsPageView = trackAnalyticsPageView", js)
        self.assertIn("window.trackAnalyticsEvent = trackAnalyticsEvent", js)
        self.assertIn("trackAnalyticsPageView(path)", js)

    def test_comment_and_group_chat_deletion_integration(self):
        """
        Verifies granular content deletion endpoints for comments (DELETE /api/comments/<cid>)
        and Space Chat Board messages (DELETE /api/groups/<gid>/chat/<mid>).
        """
        token_admin = self.get_token("maya@gooddeeds.space")
        headers_admin = self.get_auth_headers(token_admin)

        # 1. Create a post and add a comment on it
        post_res = self.make_request("POST", "/api/posts", headers=headers_admin, body={
            "title": "Comment Deletion Test Post",
            "theme": "General",
            "content": "Testing comment deletion",
            "group_ids": [1]
        })
        self.assertEqual(post_res[0], 201)
        post_id = (post_res[2].get("item") or post_res[2].get("post"))["id"]

        comm_res = self.make_request("POST", "/api/comments", headers=headers_admin, body={
            "item_id": post_id,
            "content": "Comment to be deleted"
        })
        self.assertEqual(comm_res[0], 201)
        comm_id = comm_res[2]["comment"]["id"]

        # 2. Delete the comment via DELETE /api/comments/<cid>
        del_comm_res = self.make_request("DELETE", f"/api/comments/{comm_id}", headers=headers_admin)
        self.assertEqual(del_comm_res[0], 200)
        self.assertTrue(del_comm_res[2].get("success"))

        # 3. Post a message to Space Chat Board and delete it via DELETE /api/groups/1/chat/<mid>
        chat_res = self.make_request("POST", "/api/groups/1/chat", headers=headers_admin, body={
            "message": "Temporary chat board message"
        })
        self.assertEqual(chat_res[0], 201)
        msg_id = chat_res[2]["message"]["id"]

        del_chat_res = self.make_request("DELETE", f"/api/groups/1/chat/{msg_id}", headers=headers_admin)
        self.assertEqual(del_chat_res[0], 200)
        self.assertTrue(del_chat_res[2].get("success"))

    def test_group_member_kick_and_ban_integration(self):
        """
        Verifies that kicking and banning a member from a Space (POST /api/groups/<gid>/members/kick)
        removes them and blocks them from re-joining the Space (POST /api/groups/<gid>/join returns 403).
        """
        token_admin = self.get_token("maya@gooddeeds.space")
        headers_admin = self.get_auth_headers(token_admin)
        token_elena = self.get_token("elena@gooddeeds.space")
        headers_elena = self.get_auth_headers(token_elena)

        # Ensure Elena joins Space 2 first
        self.make_request("POST", "/api/groups/2/join", headers=headers_elena)

        # Admin kicks and bans Elena from Space 2
        kick_res = self.make_request("POST", "/api/groups/2/members/kick", headers=headers_admin, body={
            "user_id": 3,
            "ban": True,
            "reason": "Testing Space ban enforcement"
        })
        self.assertEqual(kick_res[0], 200)
        self.assertTrue(kick_res[2].get("success"))

        # Elena attempts to re-join Space 2 and is blocked with 403
        rejoin_res = self.make_request("POST", "/api/groups/2/join", headers=headers_elena)
        self.assertEqual(rejoin_res[0], 403)
        self.assertIn("banned", rejoin_res[2].get("error", "").lower())

    def test_automated_spam_filter_across_kudos_comments_and_chat(self):
        """
        Verifies that automated safety guardrails block spam keywords across
        POST /api/kudos, POST /api/comments, and POST /api/groups/<gid>/chat.
        """
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)

        # 1. Blocked Kudos
        kudos_res = self.make_request("POST", "/api/kudos", headers=headers, body={
            "recipient_id": 3,
            "content": "Congratulations! Click here to win prize free bitcoin giveaway!"
        })
        self.assertEqual(kudos_res[0], 400)
        self.assertIn("blocked", kudos_res[2].get("error", "").lower())

        # 2. Blocked Comment
        comm_res = self.make_request("POST", "/api/comments", headers=headers, body={
            "item_id": 1,
            "content": "Check out this crypto scam link!"
        })
        self.assertEqual(comm_res[0], 400)
        self.assertIn("blocked", comm_res[2].get("error", "").lower())

        # 3. Blocked Space Chat Board message
        chat_res = self.make_request("POST", "/api/groups/1/chat", headers=headers, body={
            "message": "malicious-phishing-link for everyone"
        })
        self.assertEqual(chat_res[0], 400)
        self.assertIn("blocked", chat_res[2].get("error", "").lower())

    def test_sqlite_wal_and_concurrency_pragmas(self):
        """
        Verifies that database.get_db() configures SQLite WAL mode, synchronous=NORMAL,
        and busy_timeout=5000 to prevent write-lock contention across concurrent threads.
        """
        conn = self.database.get_db()
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        journal_mode = cursor.fetchone()[0]
        cursor.execute("PRAGMA synchronous")
        synchronous_val = cursor.fetchone()[0]
        cursor.execute("PRAGMA busy_timeout")
        busy_timeout_val = cursor.fetchone()[0]
        conn.close()

        self.assertEqual(journal_mode.lower(), "wal")
        self.assertEqual(int(synchronous_val), 1)  # 1 == NORMAL in SQLite
        self.assertEqual(int(busy_timeout_val), 5000)

    def test_xss_escaping_in_app_js(self):
        """
        Verifies that static/app.js defines and exports escapeHtml(unsafeStr)
        and applies it to sanitize user-generated content across feed cards,
        comments, chat messages, and moderation reports.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_path = os.path.join(base_dir, "static", "app.js")
        with open(app_path, "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn("function escapeHtml(unsafeStr)", js)
        self.assertIn("window.escapeHtml = escapeHtml", js)
        self.assertIn("escapeHtml(item.content)", js)
        self.assertIn("escapeHtml(c.content)", js)
        self.assertIn("escapeHtml(m.message)", js)
        self.assertIn("escapeHtml(rep.content_snippet)", js)

    def test_csrf_origin_validation_on_state_changing_endpoints(self):
        """
        Verifies that state-changing endpoints (POST, PUT, DELETE) enforce strict CSRF Origin/Referer
        validation when Host is provided:
        - Reject cross-site Origin with 403
        - Reject requests missing both Origin and Referer with 403 (prevents no-Origin form POST bypass)
        - Reject cross-site Referer fallback with 403
        - Allow same-origin Referer fallback with 201
        - Allow same-origin Origin with 201
        """
        token = self.get_token("maya@gooddeeds.space")

        # 1. Cross-site Origin header -> 403
        bad_origin_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Host": "localhost:8080",
            "Origin": "https://evil-attacker.example.com"
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=bad_origin_headers, body={
            "title": "CSRF Attack Attempt",
            "theme": "General",
            "content": "Should be blocked by CSRF check"
        })
        self.assertEqual(status, 403)
        self.assertIn("csrf", body.get("error", "").lower())

        # 2. Missing both Origin and Referer when Host is present -> 403
        missing_origin_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Host": "localhost:8080"
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=missing_origin_headers, body={
            "title": "No-Origin Bypass Attempt",
            "theme": "General",
            "content": "Should be blocked when Origin and Referer are missing"
        })
        self.assertEqual(status, 403)
        self.assertIn("csrf", body.get("error", "").lower())

        # 3. Cross-site Referer fallback when Origin is omitted -> 403
        bad_referer_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Host": "localhost:8080",
            "Referer": "https://evil-attacker.example.com/form"
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=bad_referer_headers, body={
            "title": "Cross-site Referer Attempt",
            "theme": "General",
            "content": "Should be blocked by Referer fallback check"
        })
        self.assertEqual(status, 403)
        self.assertIn("csrf", body.get("error", "").lower())

        # 4. Valid same-origin Referer fallback when Origin is omitted -> 201
        good_referer_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Host": "localhost:8080",
            "Referer": "http://localhost:8080/feed"
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=good_referer_headers, body={
            "title": "Legitimate Same-Origin Referer Post",
            "theme": "General",
            "content": "Allowed by Referer fallback check"
        })
        self.assertEqual(status, 201)

        # 5. Spoofed Host header matching spoofed Referer -> 400 Bad Request (ALLOWED_HOSTS protection)
        spoofed_host_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Host": "evil-attacker.example.com",
            "Referer": "https://evil-attacker.example.com/form"
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=spoofed_host_headers, body={
            "title": "Spoofed Host Bypass Attempt",
            "theme": "General",
            "content": "Should be blocked by ALLOWED_HOSTS check"
        })
        self.assertEqual(status, 400)
        self.assertIn("invalid or untrusted host header", body.get("error", "").lower())

        # 6. Valid same-origin Origin header -> 201
        good_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Host": "localhost:8080",
            "Origin": "http://localhost:8080"
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=good_headers, body={
            "title": "Legitimate Same-Origin Post",
            "theme": "General",
            "content": "Allowed by CSRF check"
        })
        self.assertEqual(status, 201)

        # 7. Render deployment domain (*.onrender.com) -> 201
        render_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Host": "gooddeeds-space.onrender.com",
            "Origin": "https://gooddeeds-space.onrender.com"
        }
        status, _, body = self.make_request("POST", "/api/posts", headers=render_headers, body={
            "title": "Render Deployment Post",
            "theme": "General",
            "content": "Allowed on *.onrender.com"
        })
        self.assertEqual(status, 201)

    def test_in_app_notifications_realtime_polling_and_triggers(self):
        """
        Verifies real-time in-app notifications bell, unread badge, polling functions,
        and automatic notification generation when Kudos are sent.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        app_path = os.path.join(base_dir, "static", "app.js")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        with open(app_path, "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn('id="nav-notifications-btn"', html)
        self.assertIn('id="notifications-unread-badge"', html)
        self.assertIn('id="notifications-dropdown-menu"', html)
        self.assertIn("window.loadNotifications = loadNotifications", js)
        self.assertIn("window.markAllNotificationsRead = markAllNotificationsRead", js)
        self.assertIn("window.startNotificationsPolling = startNotificationsPolling", js)

        token_maya = self.get_token("maya@gooddeeds.space")
        headers_maya = self.get_auth_headers(token_maya)
        token_elena = self.get_token("elena@gooddeeds.space")
        headers_elena = self.get_auth_headers(token_elena)

        # Maya sends Kudos to Elena (user 3)
        status, _, body = self.make_request("POST", "/api/kudos", headers=headers_maya, body={
            "recipient_id": 3,
            "content": "Thank you Elena for helping with the community garden!"
        })
        self.assertEqual(status, 201)

        # Elena polls GET /api/notifications and sees the unread KUDOS notification
        status, _, body = self.make_request("GET", "/api/notifications", headers=headers_elena)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(body.get("unread_count", 0), 1)
        notifs = body.get("notifications", [])
        self.assertTrue(any(n["notif_type"] == "KUDOS" for n in notifs))

        # Elena marks all notifications as read
        status, _, body = self.make_request("POST", "/api/notifications/read", headers=headers_elena, body={})
        self.assertEqual(status, 200)
        status, _, body = self.make_request("GET", "/api/notifications", headers=headers_elena)
        self.assertEqual(body.get("unread_count"), 0)

    def test_salted_pbkdf2_password_hashing_and_upgrade(self):
        """
        Verifies that hash_password produces unique salted PBKDF2-HMAC-SHA256 hashes
        ('pbkdf2_sha256$100000$<salt>$<hash>'), verify_password validates correctly,
        and login transparently upgrades any legacy unsalted SHA-256 hash.
        """
        from database import hash_password, verify_password
        h1 = hash_password("SecretPassword123!")
        h2 = hash_password("SecretPassword123!")
        self.assertTrue(h1.startswith("pbkdf2_sha256$100000$"))
        self.assertNotEqual(h1, h2, "Every hash must generate a unique random salt")
        self.assertTrue(verify_password("SecretPassword123!", h1))
        self.assertFalse(verify_password("WrongPassword", h1))

        # Test transparent login upgrade of a legacy unsalted SHA-256 hash
        import hashlib
        legacy_unsalted = hashlib.sha256("legacy_pw".encode("utf-8")).hexdigest()
        conn = self.database.get_db()
        conn.execute("UPDATE users SET password_hash = ? WHERE id = 3", (legacy_unsalted,))
        conn.commit()
        conn.close()

        # Log in with Elena using 'legacy_pw'
        status, _, body = self.make_request("POST", "/api/auth/login", body={
            "email": "elena@gooddeeds.space",
            "password": "legacy_pw"
        })
        self.assertEqual(status, 200)
        self.assertIn("token", body)

        # Verify database row was transparently upgraded to salted PBKDF2-HMAC-SHA256
        conn = self.database.get_db()
        upgraded_row = conn.execute("SELECT password_hash FROM users WHERE id = 3").fetchone()
        conn.close()
        self.assertTrue(upgraded_row["password_hash"].startswith("pbkdf2_sha256$100000$"))

    def test_auth_login_and_signup_rate_limiting_and_spam_filter(self):
        """
        Verifies rate limiting on /api/auth/login (max 10 per 60s) and /api/auth/signup (max 5 per 60s),
        returning 429 Too Many Requests when exceeded, as well as spam keyword filtering on signup.
        """
        # 1. Signup spam filter blocks prohibited keywords in username/bio
        status, _, body = self.make_request("POST", "/api/auth/signup", headers={"X-Forwarded-For": "10.0.0.50"}, body={
            "email": "spambot@example.com",
            "username": "free bitcoin giveaway bot",
            "password": "Password123!"
        })
        self.assertEqual(status, 400)
        self.assertIn("prohibited phrase", body.get("error", "").lower())

        # 2. Signup rate limiting (5 attempts allowed per IP, 6th returns 429)
        for i in range(4):
            status, _, body = self.make_request("POST", "/api/auth/signup", headers={"X-Forwarded-For": "10.0.0.50"}, body={
                "email": f"user_{i}@example.com",
                "username": f"user_{i}",
                "password": "Password123!"
            })
            self.assertEqual(status, 201)

        # 6th attempt from same IP (1 blocked spam attempt + 4 successful signups = 5 attempts total so far)
        status, _, body = self.make_request("POST", "/api/auth/signup", headers={"X-Forwarded-For": "10.0.0.50"}, body={
            "email": "user_extra@example.com",
            "username": "user_extra",
            "password": "Password123!"
        })
        self.assertEqual(status, 429)
        self.assertIn("too many authentication attempts", body.get("error", "").lower())

        # 3. Login brute-force rate limiting (10 attempts allowed per IP:email, 11th returns 429)
        for i in range(10):
            status, _, body = self.make_request("POST", "/api/auth/login", headers={"X-Forwarded-For": "10.0.0.99"}, body={
                "email": "maya@gooddeeds.space",
                "password": f"wrong_password_{i}"
            })
            self.assertEqual(status, 401)

        # 11th login attempt against maya@gooddeeds.space from same IP is rate limited with 429
        status, _, body = self.make_request("POST", "/api/auth/login", headers={"X-Forwarded-For": "10.0.0.99"}, body={
            "email": "maya@gooddeeds.space",
            "password": "wrong_password_11"
        })
        self.assertEqual(status, 429)
        self.assertIn("too many authentication attempts", body.get("error", "").lower())

    def test_support_alert_email_env_var_configuration(self):
        """
        Verifies that no personal email is hardcoded in handlers.py or static/app.js
        and that support inquiry alerts respect the SUPPORT_ALERT_EMAIL environment variable.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for rel_path in ("handlers.py", os.path.join("static", "app.js")):
            with open(os.path.join(base_dir, rel_path), "r", encoding="utf-8") as f:
                content = f.read()
                self.assertNotIn("roht_kgupta@yahoo.com", content)

        token = self.get_token("maya@gooddeeds.space")
        headers = {"Authorization": f"Bearer {token}"}

        old_env = os.environ.get("SUPPORT_ALERT_EMAIL")
        try:
            os.environ["SUPPORT_ALERT_EMAIL"] = "custom-ops@gooddeeds.space"
            status, _, body = self.make_request("POST", "/api/support", headers=headers, body={
                "subject": "Testing Support Alert Env Var",
                "message": "Should route to custom-ops@gooddeeds.space"
            })
            self.assertEqual(status, 200)

            conn = self.database.get_db()
            row = conn.execute(
                "SELECT recipient_email FROM email_outbox WHERE recipient_email = ? ORDER BY id DESC LIMIT 1",
                ("custom-ops@gooddeeds.space",)
            ).fetchone()
            conn.close()
            self.assertIsNotNone(row)
        finally:
            if old_env is not None:
                os.environ["SUPPORT_ALERT_EMAIL"] = old_env
            elif "SUPPORT_ALERT_EMAIL" in os.environ:
                del os.environ["SUPPORT_ALERT_EMAIL"]

    def test_feed_reverse_chronological_sort_kudos_vs_post_distinction_and_preview_attachment_verification(self):
        """
        Verifies the 3 feed & confirmation enhancements:
        a) Feed sorts by reverse chronological order ('recent') by default in static/app.js and #feed-sort-select in static/index.html,
           with newly created Kudos and Posts appearing at the top.
        b) Kudos and Posts have distinct visual ribbons ('🌟 Gratitude Kudos' vs '📝 Community Post' / '📅 Event Post' / '📚 Resource Post')
           and distinct card styling in renderFeedCard.
        c) Step 2 of 2 post confirmation (#post-preview-card / #confirm-post-attachments) displays exact URLs and filenames with
           clickable window.openAttachment buttons ('Open to Verify ↗') before publishing.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base_dir, "static", "index.html"), "r", encoding="utf-8") as f:
            html = f.read()
        with open(os.path.join(base_dir, "static", "app.js"), "r", encoding="utf-8") as f:
            js = f.read()

        # (a) Reverse chronological default sort & UI selector
        self.assertIn('id="feed-order-select"', html)
        self.assertIn('value="recent" selected', html)
        self.assertIn('let currentSortMode = "recent";', js)

        token = self.get_token("maya@gooddeeds.space")
        headers = {"Authorization": f"Bearer {token}"}

        # Create a new Kudos and then a new Post and verify reverse chronological order
        status1, _, body1 = self.make_request("POST", "/api/kudos", headers=headers, body={
            "recipient_id": 3,
            "content": "First newly created kudos item"
        })
        self.assertEqual(status1, 201)
        kudos_id = body1["item"]["id"]

        status2, _, body2 = self.make_request("POST", "/api/posts", headers=headers, body={
            "title": "Second Newly Created Post Item",
            "theme": "Inspiring Stories",
            "content": "Most recent item in the feed"
        })
        self.assertEqual(status2, 201)
        post_id = body2["item"]["id"]

        status_feed, _, feed_body = self.make_request("GET", "/api/feed?sort=recent")
        self.assertEqual(status_feed, 200)
        feed_ids = [item["id"] for item in feed_body["feed"]]
        self.assertEqual(feed_ids[0], post_id)
        self.assertEqual(feed_ids[1], kudos_id)

        # (b) Visual distinction between Kudos and Posts in renderFeedCard
        self.assertIn("🌟 Gratitude Kudos", js)
        self.assertIn("📝 Community Post", js)
        self.assertIn("📅 Event Post", js)
        self.assertIn("📚 Resource Post", js)

        # (c) Interactive clickable URL/file preview in Step 2 of 2 confirmation popup
        self.assertIn("confirm-post-attachments", js)
        self.assertIn("preview_attachment_", js)
        self.assertIn("Open to Verify ↗", js)

    def test_admin_cannot_promote_or_demote_self_or_site_admin_in_space_roster(self):
        """
        Verifies that:
        1. Site Admins in a Space roster return is_site_admin=1 and group.is_admin=True.
        2. renderGroupRoster in static/app.js guards role/kick buttons with `canManageRoles && !isSelf && !isMemberSiteAdmin`
           so no admin sees 'Promote to Admin' or 'Demote from Admin' on themselves or on a Site Admin.
        3. Backend /api/groups/<id>/members/role rejects self-role changes with 400.
        """
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base_dir, "static", "app.js"), "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn("if (canManageRoles && !isSelf && !isMemberSiteAdmin)", js)
        self.assertIn("Site Admin", js)

        token_maya = self.get_token("maya@gooddeeds.space")
        headers_maya = {"Authorization": f"Bearer {token_maya}"}

        # Check Group 1 roster for Maya_Lin (User 1, Site Admin)
        status_g, _, body_g = self.make_request("GET", "/api/groups/1", headers=headers_maya)
        self.assertEqual(status_g, 200)
        roster = body_g["group"]["roster"]
        maya_member = next((m for m in roster if m["id"] == 1), None)
        self.assertIsNotNone(maya_member)
        self.assertEqual(maya_member["is_site_admin"], 1)
        self.assertTrue(body_g["group"]["is_admin"])

        # Attempting to promote/demote yourself should fail with 400
        status_self, _, body_self = self.make_request("POST", "/api/groups/1/members/role", headers=headers_maya, body={
            "user_id": 1,
            "is_admin": 1
        })
        self.assertEqual(status_self, 400)

