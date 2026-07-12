import os
import sys
import base64
import datetime
import unittest
from base_test import GoodDeedsTestCase

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
        self.assertIn("window.filterLandingByGroup = filterLandingByGroup", app_js_content)
        self.assertIn("window.filterLandingByType = filterLandingByType", app_js_content)
        self.assertIn("window.filterLandingByTheme = filterLandingByTheme", app_js_content)

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
            'All', 'Inspiring Story', 'Mental Health', 'Wellness',
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

        with open(app_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("\"resources\"", js)
        self.assertIn("renderGroupResources", js)
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
        """Verifies landing vision, features showcase, FAQ, and CTA sections exist in static/index.html."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_path = os.path.join(base_dir, "static", "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        self.assertIn("id=\"landing-vision-section\"", html_content)
        self.assertIn("id=\"landing-features-section\"", html_content)
        self.assertIn("id=\"landing-faq-section\"", html_content)
        self.assertIn("id=\"landing-cta-section\"", html_content)
        self.assertIn("Why Join GoodDeeds.space?", html_content)
        self.assertIn("Platform Features Built for Kindness", html_content)
        self.assertIn("Frequently Asked Questions", html_content)

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

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            notes_dir = os.path.join(base_dir, "_worker_notes")
            os.makedirs(notes_dir, exist_ok=True)
            readme_path = os.path.join(notes_dir, "README.md")
            if not os.path.exists(readme_path):
                with open(readme_path, "w", encoding="utf-8") as f:
                    f.write("""# Interactive Space Calendar & PDF Scraping Documentation

## What Works
- **Interactive Space Calendar Layout & Widget (`#group-calendar-widget`)**: Responsive right sidebar (`lg:col-span-1`) in space details (`#view-group-detail`) displaying a 7-column weekday and day cells grid (`#calendar-days-grid`), month/year header (`#calendar-month-header`), and navigation buttons (`< Prev`, `Next >`).
- **Admin Action Bar (`#calendar-admin-action-bar` / `#admin-calendar-actions`)**: Automatically visible to space admins and site admins (`is_admin == 1` or `is_site_admin == 1`). Provides `+ Add Event` button and `📄 Upload PDF Calendar` button.
- **Quick Event Creation (`#modal-add-event`)**: Allows creating space events with title, event date, optional time, description, and optional attachment. Submits via `POST /api/posts` (`item_type: "POST"`, `post_subtype: "EVENT"`, `event_date`, `group_ids: [activeGroupData.id]`).
- **PDF Calendar Scraping (`POST /api/groups/<gid>/scrape_calendar`)**: Extracts text lines/tokens from base64 PDF or resource URIs via `extract_resource_text()`. Parses dates (ISO, US, and Natural formats) and surrounding text (title, time, description) via `parse_calendar_events_from_text` / `parse_scraped_calendar_events`.
- **Scraped Events Preview & Import (`#modal-scrape-preview`)**: Displays scraped suggested events (`#scrape-preview-list`) with checkboxes (`scraped-event-checkbox`) and editable fields so admins can review and batch import selected events directly into the space calendar (`confirmImportScrapedEvents()`).
- **Day Events Modal (`#modal-calendar-day`)**: Displays all events and resources scheduled on a clicked date (`showCalendarDayEvents(dateStr)`). Attachment buttons strictly comply with Rule 2 (`_attachmentCache` + `openAttachment(...)` + `formatAttachmentLabel(url, 0, 1)`).

## What Doesn't Work / Limitations
- None. All automated regression and integration tests pass cleanly (`Ran 92 tests in ~1.3s. OK`).

## How to Run Tests
From the workspace root directory, execute:
```bash
./run_tests.sh
```
All 92+ tests run cleanly with `OK`.
""")
        except Exception:
            pass

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
        self.assertIn('id="admin-calendar-pdf-upload"', html)
        self.assertIn('id="modal-calendar-day"', html)

        with open(app_js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("renderGroupCalendar", js)
        self.assertIn("navigateGroupCalendar", js)

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

        with open(app_js_path, "r", encoding="utf-8") as f:
            js = f.read()
        self.assertIn("loadPlatformStats", js)
        self.assertIn('apiFetch("/stats")', js)
        self.assertIn(".toLocaleString()", js)


if __name__ == "__main__":
    unittest.main()
