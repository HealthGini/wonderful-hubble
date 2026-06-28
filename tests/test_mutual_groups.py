import unittest
from base_test import BaseTestCase

class TestMutualGroups(BaseTestCase):

    def test_mutual_groups_query(self):
        """Tests querying mutual groups between sender and recipient."""
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)

        # Query groups shared between Maya (user 1) and Arthur (user 4)
        status, _, body = self.make_request("GET", "/api/groups/joined?target_user_id=4", headers=headers)
        self.assertEqual(status, 200)
        self.assertIn("groups", body)

        # Also verify /api/groups/common endpoint
        status2, _, body2 = self.make_request("GET", "/api/groups/common?target_user_id=4", headers=headers)
        self.assertEqual(status2, 200)
        self.assertEqual(body, body2)

    def test_kudos_creation_validates_mutual_groups(self):
        """Tests Kudos creation validation of mutual group tagging."""
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)

        # First, find a group that Maya and Arthur share vs one they don't
        conn = self.database.get_db()
        cursor = conn.cursor()
        
        # Ensure Maya (user 1) and Arthur (user 4) are both members of group 1, but Arthur is NOT in group 3
        cursor.execute("INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (1, 1)")
        cursor.execute("INSERT OR IGNORE INTO group_members (group_id, user_id) VALUES (1, 4)")
        cursor.execute("DELETE FROM group_members WHERE group_id = 3 AND user_id = 4")
        conn.commit()
        conn.close()

        # Try creating Kudos tagging non-mutual group 3
        invalid_kudos = {
            "recipient_id": 4,
            "content": "Thanks for mutual test!",
            "group_ids": [3]
        }
        status, _, body = self.make_request("POST", "/api/kudos", headers=headers, body=invalid_kudos)
        self.assertEqual(status, 400)
        self.assertIn("tagged groups must be shared", body["error"].lower())

        # Try creating Kudos tagging mutual group 1
        valid_kudos = {
            "recipient_id": 4,
            "content": "Thanks for mutual test valid!",
            "group_ids": [1]
        }
        status, _, body = self.make_request("POST", "/api/kudos", headers=headers, body=valid_kudos)
        self.assertEqual(status, 201)
        self.assertTrue(body["success"])

if __name__ == "__main__":
    unittest.main()
