import unittest
from base_test import BaseTestCase

class TestDatabase(BaseTestCase):

    def test_database_initialization(self):
        """Verifies that all required tables are created during initialization."""
        conn = self.database.get_db()
        cursor = conn.cursor()
        
        # Query sqlite_master to get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row["name"] for row in cursor.fetchall()]
        conn.close()

        required_tables = [
            "users", "sessions", "groups", "group_members", "group_resources",
            "group_messages", "feed_items", "item_groups", "reactions",
            "comments", "email_outbox", "customer_service_inquiries",
            "group_invitations"
        ]

        for table in required_tables:
            self.assertIn(table, tables, f"Table {table} is missing from the database.")

    def test_database_seeding(self):
        """Verifies that demo data is successfully populated on first run."""
        conn = self.database.get_db()
        cursor = conn.cursor()

        # Check users (expecting 4 seeded users)
        cursor.execute("SELECT COUNT(*) as count FROM users")
        user_count = cursor.fetchone()["count"]
        self.assertEqual(user_count, 4, "Expected 4 seeded users.")

        # Check groups (expecting 3 seeded groups)
        cursor.execute("SELECT COUNT(*) as count FROM groups")
        group_count = cursor.fetchone()["count"]
        self.assertEqual(group_count, 3, "Expected 3 seeded groups.")

        # Check group members
        cursor.execute("SELECT COUNT(*) as count FROM group_members")
        member_count = cursor.fetchone()["count"]
        self.assertTrue(member_count > 0, "Expected some seeded group members.")

        # Check feed items (expecting 5 seeded feed items: 2 Kudos, 3 Posts)
        cursor.execute("SELECT COUNT(*) as count FROM feed_items")
        feed_count = cursor.fetchone()["count"]
        self.assertEqual(feed_count, 5, "Expected 5 seeded feed items.")

        conn.close()

if __name__ == "__main__":
    unittest.main()
