import unittest
from base_test import BaseTestCase

class TestInvitations(BaseTestCase):

    def test_send_invite_by_username_existing(self):
        """Tests sending an invitation to an existing user by username."""
        # Marcus (user 2) invites Elena (user 3) to Group 2.
        # Elena is NOT in Group 2 in seed data.
        token = self.get_token("marcus@gooddeeds.space")
        headers = self.get_auth_headers(token)
        invite_data = {
            "emails": "Elena_Wellness", # Username of Elena
            "message": "Join Education group!"
        }
        status, _, body = self.make_request("POST", "/api/groups/2/invite", headers=headers, body=invite_data)
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])

        # Verify invitation is created in DB (pending status)
        conn = self.database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM group_invitations WHERE group_id = 2 AND recipient_username = ?", ("Elena_Wellness",))
        invite = cursor.fetchone()
        self.assertIsNotNone(invite)
        self.assertEqual(invite["status"], "PENDING")
        self.assertEqual(invite["sender_id"], 2)

        # Verify email was logged for Elena's email (elena@gooddeeds.space)
        cursor.execute("SELECT * FROM email_outbox ORDER BY id DESC LIMIT 1")
        email = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(email)
        self.assertEqual(email["recipient_email"], "elena@gooddeeds.space")
        self.assertIn("invited to join", email["subject"])

    def test_send_invite_by_email_new(self):
        """Tests sending an invitation to a new email address."""
        token = self.get_token("marcus@gooddeeds.space")
        headers = self.get_auth_headers(token)
        invite_data = {
            "emails": "new_guest@example.com",
            "message": "Welcome!"
        }
        status, _, body = self.make_request("POST", "/api/groups/2/invite", headers=headers, body=invite_data)
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])
        
        # Verify invitation created
        conn = self.database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM group_invitations WHERE group_id = 2 AND recipient_username = ?", ("new_guest@example.com",))
        invite = cursor.fetchone()
        self.assertIsNotNone(invite)

        # Verify email logged
        cursor.execute("SELECT * FROM email_outbox ORDER BY id DESC LIMIT 1")
        email = cursor.fetchone()
        conn.close()
        self.assertEqual(email["recipient_email"], "new_guest@example.com")

    def test_invite_unauthenticated(self):
        """Tests that sending an invitation fails when unauthenticated."""
        invite_data = {"emails": "Elena_Wellness"}
        status, _, _ = self.make_request("POST", "/api/groups/2/invite", body=invite_data)
        self.assertEqual(status, 401)

    def test_invite_nonexistent_group(self):
        """Tests sending an invitation to a non-existent group."""
        token = self.get_token("marcus@gooddeeds.space")
        headers = self.get_auth_headers(token)
        invite_data = {"emails": "Elena_Wellness"}
        status, _, _ = self.make_request("POST", "/api/groups/999/invite", headers=headers, body=invite_data)
        self.assertEqual(status, 404)

    def test_invite_missing_emails(self):
        """Tests sending invitation with missing recipient emails/usernames."""
        token = self.get_token("marcus@gooddeeds.space")
        headers = self.get_auth_headers(token)
        status, _, body = self.make_request("POST", "/api/groups/2/invite", headers=headers, body={})
        self.assertEqual(status, 400)
        self.assertIn("error", body)

    def test_get_pending_invitations(self):
        """Tests retrieving pending invitations for a user."""
        # Create a new group where we can invite someone.
        # Maya (user 1) creates Group 4.
        token_maya = self.get_token("maya@gooddeeds.space")
        headers_maya = self.get_auth_headers(token_maya)
        status, _, body = self.make_request("POST", "/api/groups", headers=headers_maya, body={"name": "Test Group 4", "description": "G4"})
        g4_id = body["id"]

        # Maya invites Elena (who is NOT in G4)
        invite_data = {
            "emails": "Elena_Wellness",
            "message": "Join G4!"
        }
        self.make_request("POST", f"/api/groups/{g4_id}/invite", headers=headers_maya, body=invite_data)

        # Now login as Elena and check pending invites
        token_elena = self.get_token("elena@gooddeeds.space")
        headers_elena = self.get_auth_headers(token_elena)
        status, _, body = self.make_request("GET", "/api/invitations/pending", headers=headers_elena)
        self.assertEqual(status, 200)
        invites = body.get("invitations", [])
        self.assertEqual(len(invites), 1)
        self.assertEqual(invites[0]["group_name"], "Test Group 4")
        self.assertEqual(invites[0]["sender_name"], "Maya_Lin")

    def test_accept_invitation(self):
        """Tests accepting a group invitation."""
        token_maya = self.get_token("maya@gooddeeds.space")
        headers_maya = self.get_auth_headers(token_maya)
        _, _, body = self.make_request("POST", "/api/groups", headers=headers_maya, body={"name": "Test Group 5", "description": "G5"})
        g5_id = body["id"]

        # Maya invites Elena
        self.make_request("POST", f"/api/groups/{g5_id}/invite", headers=headers_maya, body={"emails": "Elena_Wellness"})

        # Elena logins
        token_elena = self.get_token("elena@gooddeeds.space")
        headers_elena = self.get_auth_headers(token_elena)
        
        # Get invite ID
        _, _, body = self.make_request("GET", "/api/invitations/pending", headers=headers_elena)
        invite_id = body["invitations"][0]["invite_id"]

        # Accept
        status, _, body = self.make_request("POST", "/api/invitations/respond", headers=headers_elena, body={"invite_id": invite_id, "action": "accept"})
        self.assertEqual(status, 200)
        self.assertIn("accepted", body["message"])
        self.assertEqual(body["group_id"], g5_id)

        # Verify she is now in the group
        status, _, body = self.make_request("GET", f"/api/groups/{g5_id}", headers=headers_elena)
        self.assertTrue(body["group"]["is_joined"])

    def test_reject_invitation(self):
        """Tests declining a group invitation."""
        token_maya = self.get_token("maya@gooddeeds.space")
        headers_maya = self.get_auth_headers(token_maya)
        _, _, body = self.make_request("POST", "/api/groups", headers=headers_maya, body={"name": "Test Group 6", "description": "G6"})
        g6_id = body["id"]

        # Maya invites Elena
        self.make_request("POST", f"/api/groups/{g6_id}/invite", headers=headers_maya, body={"emails": "Elena_Wellness"})

        # Elena logins
        token_elena = self.get_token("elena@gooddeeds.space")
        headers_elena = self.get_auth_headers(token_elena)
        
        # Get invite ID
        _, _, body = self.make_request("GET", "/api/invitations/pending", headers=headers_elena)
        invite_id = body["invitations"][0]["invite_id"]

        # Reject
        status, _, body = self.make_request("POST", "/api/invitations/respond", headers=headers_elena, body={"invite_id": invite_id, "action": "reject"})
        self.assertEqual(status, 200)
        self.assertIn("declined", body["message"])

        # Verify she is NOT in the group
        status, _, body = self.make_request("GET", f"/api/groups/{g6_id}", headers=headers_elena)
        self.assertFalse(body["group"]["is_joined"])

        # Verify invite is no longer pending
        status, _, body = self.make_request("GET", "/api/invitations/pending", headers=headers_elena)
        self.assertEqual(len(body.get("invitations", [])), 0)

    def test_respond_nonexistent_invite(self):
        """Tests responding to a non-existent invitation."""
        token = self.get_token("elena@gooddeeds.space")
        headers = self.get_auth_headers(token)
        status, _, _ = self.make_request("POST", "/api/invitations/respond", 
                                                 headers=headers,
                                                 body={"invite_id": 999, "action": "accept"})
        self.assertEqual(status, 404)

if __name__ == "__main__":
    unittest.main()
