import unittest
from base_test import BaseTestCase

class TestGroups(BaseTestCase):

    def test_list_groups(self):
        """Tests listing all groups."""
        status, _, body = self.make_request("GET", "/api/groups")
        self.assertEqual(status, 200)
        groups = body.get("groups", [])
        self.assertEqual(len(groups), 3)
        self.assertEqual(groups[0]["name"], "🌱 Mental Health & Peer Listening")

    def test_join_leave_group(self):
        """Tests joining and leaving a group using an existing non-member user."""
        # Elena (user 3) is NOT in Group 2 (Education) in seed data.
        token = self.get_token("elena@gooddeeds.space")
        headers = self.get_auth_headers(token)
        
        # Verify not joined initially
        status, _, body = self.make_request("GET", "/api/groups/2", headers=headers)
        self.assertEqual(status, 200)
        self.assertFalse(body["group"]["is_joined"])

        # Join Group 2
        status, _, body = self.make_request("POST", "/api/groups/2/join", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(body["action"], "join")

        # Verify joined and in roster
        status, _, body = self.make_request("GET", "/api/groups/2", headers=headers)
        self.assertEqual(status, 200)
        self.assertTrue(body["group"]["is_joined"])
        self.assertTrue(any(m["id"] == 3 for m in body["group"]["roster"]))

        # Leave Group 2
        status, _, body = self.make_request("POST", "/api/groups/2/leave", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(body["action"], "leave")

        # Verify left
        status, _, body = self.make_request("GET", "/api/groups/2", headers=headers)
        self.assertEqual(status, 200)
        self.assertFalse(body["group"]["is_joined"])

    def test_group_detail_and_roster(self):
        """Tests retrieving group details and member roster."""
        status, _, body = self.make_request("GET", "/api/groups/1")
        self.assertEqual(status, 200)
        group = body.get("group", {})
        self.assertEqual(group["name"], "🌱 Mental Health & Peer Listening")
        self.assertIn("roster", group)
        self.assertEqual(len(group["roster"]), 4) # 4 seeded members
        
        # Verify Elena is admin
        elena = next(m for m in group["roster"] if m["username"] == "Elena_Wellness")
        self.assertEqual(elena["is_admin"], 1)

    def test_group_chat(self):
        """Tests retrieving and posting messages to group chat."""
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)

        # 1. Get messages (Group 1)
        status, _, body = self.make_request("GET", "/api/groups/1/chat", headers=headers)
        self.assertEqual(status, 200)
        msgs = body.get("messages", [])
        self.assertEqual(len(msgs), 2) # 2 seeded messages

        # 2. Post new message
        msg_data = {"message": "Hello from Maya!"}
        status, _, body = self.make_request("POST", "/api/groups/1/chat", headers=headers, body=msg_data)
        self.assertEqual(status, 201)
        new_msg = body.get("message", {})
        self.assertEqual(new_msg["message"], msg_data["message"])
        self.assertEqual(new_msg["author_name"], "Maya_Lin")

        # 3. Verify it is in chat list and group detail
        status, _, body = self.make_request("GET", "/api/groups/1/chat", headers=headers)
        msgs = body.get("messages", [])
        self.assertEqual(len(msgs), 3)

        status, _, body = self.make_request("GET", "/api/groups/1", headers=headers)
        chat_msgs = body["group"]["chat_messages"]
        self.assertTrue(any(m["message"] == msg_data["message"] for m in chat_msgs))

    def test_curate_resource_admin_success(self):
        """Tests that a group admin can curate resources."""
        # Elena (user 3) is admin of Group 1 (Mental Health)
        token = self.get_token("elena@gooddeeds.space")
        headers = self.get_auth_headers(token)

        resource_data = {
            "title": "Admin Curated Resource",
            "url": "https://admin.curated.org",
            "resource_type": "URL",
            "theme": "Mental Health"
        }

        status, _, body = self.make_request("POST", "/api/groups/1/resources", headers=headers, body=resource_data)
        self.assertEqual(status, 201)
        self.assertTrue(body["success"])

        # Verify it was added
        status, _, body = self.make_request("GET", "/api/groups/1/resources", headers=headers)
        resources = body.get("resources", [])
        self.assertEqual(len(resources), 3)
        added_res = next(r for r in resources if r["url"] == resource_data["url"])
        self.assertEqual(added_res["title"], resource_data["title"])

        # Verify in group details
        status, _, body = self.make_request("GET", "/api/groups/1", headers=headers)
        group_resources = body["group"]["resources"]
        self.assertTrue(any(r["title"] == resource_data["title"] for r in group_resources))

    def test_curate_resource_non_admin_forbidden(self):
        """Tests that a non-admin cannot curate resources."""
        # Maya (user 1) is NOT admin of Group 1 (Elena is admin)
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)

        resource_data = {
            "title": "Hack Attempt",
            "url": "https://hack.org",
            "resource_type": "URL",
            "theme": "Mental Health"
        }

        status, _, body = self.make_request("POST", "/api/groups/1/resources", headers=headers, body=resource_data)
        self.assertEqual(status, 403)
        self.assertIn("only group admins can curate", body["error"].lower())

    def test_curate_resource_unauthenticated(self):
        """Tests that resource curation fails when unauthenticated."""
        resource_data = {
            "title": "Unauth Attempt",
            "url": "https://unauth.org",
        }
        status, _, _ = self.make_request("POST", "/api/groups/1/resources", body=resource_data)
        self.assertEqual(status, 401)

if __name__ == "__main__":
    unittest.main()
