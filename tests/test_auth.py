import unittest
from base_test import BaseTestCase

class TestAuth(BaseTestCase):

    def test_signup_success(self):
        """Tests successful user registration and password hashing."""
        signup_data = {
            "email": "testuser@example.com",
            "username": "TestUser",
            "password": "Password123!",
            "phone": "123-456-7890",
            "bio": "Test bio"
        }
        status, _, body = self.make_request("POST", "/api/auth/signup", body=signup_data)
        
        self.assertEqual(status, 201)
        self.assertIn("token", body)
        self.assertIn("user", body)
        self.assertEqual(body["user"]["email"], signup_data["email"])
        self.assertEqual(body["user"]["username"], signup_data["username"])
        self.assertNotIn("password_hash", body["user"])

        # Verify password is encrypted in database
        conn = self.database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE email = ?", (signup_data["email"],))
        row = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(row)
        pw_hash = row["password_hash"]
        self.assertNotEqual(pw_hash, signup_data["password"])
        self.assertEqual(pw_hash, self.database.hash_password(signup_data["password"]))

    def test_signup_missing_fields(self):
        """Tests signup fails with missing fields."""
        signup_data = {
            "email": "testuser@example.com",
            # missing username and password
        }
        status, _, body = self.make_request("POST", "/api/auth/signup", body=signup_data)
        self.assertEqual(status, 400)
        self.assertIn("error", body)

    def test_signup_duplicate_email(self):
        """Tests signup fails if email already exists."""
        # 'maya@gooddeeds.space' is seeded
        signup_data = {
            "email": "maya@gooddeeds.space",
            "username": "NewMaya",
            "password": "Password123!"
        }
        status, _, body = self.make_request("POST", "/api/auth/signup", body=signup_data)
        self.assertEqual(status, 400)
        self.assertIn("error", body)
        self.assertIn("email", body["error"].lower())

    def test_signup_duplicate_username(self):
        """Tests signup fails if username already exists."""
        # 'Maya_Lin' is seeded
        signup_data = {
            "email": "newmaya@gooddeeds.space",
            "username": "Maya_Lin",
            "password": "Password123!"
        }
        status, _, body = self.make_request("POST", "/api/auth/signup", body=signup_data)
        self.assertEqual(status, 400)
        self.assertIn("error", body)
        self.assertIn("username", body["error"].lower())

    def test_login_success_email(self):
        """Tests successful login with email."""
        # Maya_Lin with password 'password123' is seeded
        login_data = {
            "email": "maya@gooddeeds.space",
            "password": "password123"
        }
        status, _, body = self.make_request("POST", "/api/auth/login", body=login_data)
        self.assertEqual(status, 200)
        self.assertIn("token", body)
        self.assertEqual(body["user"]["username"], "Maya_Lin")

    def test_login_success_username(self):
        """Tests successful login using username instead of email."""
        login_data = {
            "email": "Maya_Lin",
            "password": "password123"
        }
        status, _, body = self.make_request("POST", "/api/auth/login", body=login_data)
        self.assertEqual(status, 200)
        self.assertIn("token", body)
        self.assertEqual(body["user"]["email"], "maya@gooddeeds.space")

    def test_login_invalid_password(self):
        """Tests login failure with wrong password."""
        login_data = {
            "email": "maya@gooddeeds.space",
            "password": "wrongpassword"
        }
        status, _, body = self.make_request("POST", "/api/auth/login", body=login_data)
        self.assertEqual(status, 401)
        self.assertIn("error", body)

    def test_login_nonexistent_user(self):
        """Tests login failure for non-existent user."""
        login_data = {
            "email": "nobody@gooddeeds.space",
            "password": "password123"
        }
        status, _, body = self.make_request("POST", "/api/auth/login", body=login_data)
        self.assertEqual(status, 401)
        self.assertIn("error", body)

    def test_get_me_authenticated(self):
        """Tests retrieving current user profile with valid token."""
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)
        
        status, _, body = self.make_request("GET", "/api/auth/me", headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual(body["user"]["username"], "Maya_Lin")

    def test_get_me_unauthenticated(self):
        """Tests retrieving current user profile fails when unauthenticated."""
        status, _, body = self.make_request("GET", "/api/auth/me")
        self.assertEqual(status, 401)

    def test_logout(self):
        """Tests session destruction on logout."""
        token = self.get_token("maya@gooddeeds.space")
        headers = self.get_auth_headers(token)
        
        # Verify session exists in DB
        conn = self.database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM sessions WHERE token = ?", (token,))
        self.assertEqual(cursor.fetchone()["count"], 1)
        conn.close()

        # Logout
        status, _, body = self.make_request("POST", "/api/auth/logout", headers=headers)
        self.assertEqual(status, 200)
        self.assertTrue(body["success"])

        # Verify session is deleted in DB
        conn = self.database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM sessions WHERE token = ?", (token,))
        self.assertEqual(cursor.fetchone()["count"], 0)
        conn.close()

        # Try to use token again
        status, _, _ = self.make_request("GET", "/api/auth/me", headers=headers)
        self.assertEqual(status, 401)

if __name__ == "__main__":
    unittest.main()
