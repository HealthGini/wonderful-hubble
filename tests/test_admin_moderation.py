import unittest
from base_test import BaseTestCase

class TestAdminModeration(BaseTestCase):

    def test_group_admin_promotion_and_demotion(self):
        """Tests that an existing group admin can promote and demote group members."""
        # Elena (user 3) is group admin of Group 1 in seed data.
        token = self.get_token("elena@gooddeeds.space")
        headers = self.get_auth_headers(token)

        # Promote Maya (user 1) to admin in Group 1
        status, _, body = self.make_request(
            "POST",
            "/api/admin/moderation/group-member-role",
            headers=headers,
            body={"group_id": 1, "user_id": 1, "is_admin": 1}
        )
        self.assertEqual(status, 200)
        self.assertTrue(body.get("success"))

        # Verify in group roster that Maya is now admin
        status, _, body = self.make_request("GET", "/api/groups/1")
        roster = body["group"]["roster"]
        maya = next(m for m in roster if m["id"] == 1)
        self.assertEqual(maya["is_admin"], 1)

        # Demote Maya back to regular member using secondary endpoint format
        status, _, body = self.make_request(
            "POST",
            "/api/groups/1/members/role",
            headers=headers,
            body={"target_user_id": 1, "is_admin": 0}
        )
        self.assertEqual(status, 200)

        status, _, body = self.make_request("GET", "/api/groups/1")
        roster = body["group"]["roster"]
        maya = next(m for m in roster if m["id"] == 1)
        self.assertEqual(maya["is_admin"], 0)

    def test_site_super_admin_moderation(self):
        """Tests that a site super admin can moderate any group even if not a member/group admin."""
        # Set Arthur (user 4) as site super admin in DB directly for test
        conn = self.database.get_db()
        conn.execute("UPDATE users SET is_site_admin = 1 WHERE id = 4")
        conn.commit()

        token = self.get_token("arthur@gooddeeds.space")
        headers = self.get_auth_headers(token)

        # Arthur promotes Marcus (user 2) in Group 1
        status, _, body = self.make_request(
            "POST",
            "/api/admin/moderation/group-member-role",
            headers=headers,
            body={"group_id": 1, "user_id": 2, "is_admin": 1}
        )
        self.assertEqual(status, 200)

        status, _, body = self.make_request("GET", "/api/groups/1")
        marcus = next(m for m in body["group"]["roster"] if m["id"] == 2)
        self.assertEqual(marcus["is_admin"], 1)

    def test_auto_insert_non_member_on_promotion(self):
        """Tests that promoting a non-member automatically inserts them into group_members."""
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)

        status, _, body = self.make_request(
            "POST",
            "/api/admin/moderation/group-member-role",
            headers=headers,
            body={"group_id": 2, "user_id": 3, "is_admin": 1}
        )
        self.assertEqual(status, 200)

        status, _, body = self.make_request("GET", "/api/groups/2")
        elena = next(m for m in body["group"]["roster"] if m["id"] == 3)
        self.assertEqual(elena["is_admin"], 1)

    def test_unauthorized_member_forbidden(self):
        """Tests that a non-admin, non-super-admin user gets HTTP 403 Forbidden."""
        # Marcus (user 2) is regular member of Group 1
        token = self.get_token("marcus@gooddeeds.space")
        headers = self.get_auth_headers(token)

        status, _, _ = self.make_request(
            "POST",
            "/api/admin/moderation/group-member-role",
            headers=headers,
            body={"group_id": 1, "user_id": 4, "is_admin": 1}
        )
        self.assertEqual(status, 403)

    def test_unauthenticated_forbidden(self):
        """Tests that unauthenticated requests return 401."""
        status, _, _ = self.make_request(
            "POST",
            "/api/admin/moderation/group-member-role",
            body={"group_id": 1, "user_id": 4, "is_admin": 1}
        )
        self.assertEqual(status, 401)
