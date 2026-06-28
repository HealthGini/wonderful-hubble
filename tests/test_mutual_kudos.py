import unittest
from tests.base_test import BaseTestCase

class TestMutualKudos(BaseTestCase):
    def test_mutual_groups_querying(self):
        # Login as Maya (ID 1)
        token = self.get_token("maya@gooddeeds.space")
        self.assertIsNotNone(token)
        headers = self.get_auth_headers(token)

        # Query joined groups without filter
        status, _, data = self.make_request("GET", "/api/groups/joined", headers=headers)
        self.assertEqual(status, 200)
        all_joined = data.get("groups", [])
        self.assertGreater(len(all_joined), 0)

        # Query mutual groups with Marcus (ID 2)
        status, _, data = self.make_request("GET", "/api/groups/joined?target_user_id=2", headers=headers)
        self.assertEqual(status, 200)
        mutual_joined = data.get("groups", [])
        
        status, _, data_common = self.make_request("GET", "/api/groups/common?target_user_id=2", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(mutual_joined, data_common.get("groups", []))

    def test_kudos_creation_validates_shared_groups(self):
        # Login as Maya (ID 1)
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)

        # Create a new user and a new group for isolation
        # Join Maya to group A, but NOT recipient (ID 2) to group A
        conn = self.database.get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO groups (name, description) VALUES ('Maya Only Group', 'Test group')")
        unshared_gid = cursor.lastrowid
        cursor.execute("INSERT INTO group_members (group_id, user_id) VALUES (?, 1)", (unshared_gid,))
        
        # Shared group
        cursor.execute("INSERT INTO groups (name, description) VALUES ('Shared Group X', 'Shared group')")
        shared_gid = cursor.lastrowid
        cursor.execute("INSERT INTO group_members (group_id, user_id) VALUES (?, 1)", (shared_gid,))
        cursor.execute("INSERT INTO group_members (group_id, user_id) VALUES (?, 2)", (shared_gid,))
        conn.commit()
        conn.close()

        # Attempt to create Kudos with unshared group -> expect 400
        payload_fail = {
            "recipient_id": 2,
            "content": "Thank you for helping out!",
            "group_ids": [unshared_gid]
        }
        status, _, data = self.make_request("POST", "/api/kudos", headers=headers, body=payload_fail)
        self.assertEqual(status, 400)
        self.assertIn("Tagged groups must be shared", data.get("error", ""))

        # Create Kudos with shared group -> expect 201
        payload_success = {
            "recipient_id": 2,
            "content": "Thank you for the wonderful collaboration!",
            "group_ids": [shared_gid]
        }
        status, _, data = self.make_request("POST", "/api/kudos", headers=headers, body=payload_success)
        self.assertEqual(status, 201)
        self.assertTrue(data.get("success"))

if __name__ == "__main__":
    unittest.main()
