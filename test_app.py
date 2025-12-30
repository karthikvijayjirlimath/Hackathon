import unittest
import os
from main import app

class EmilyAppTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
        self.client = app.test_client()

    def login(self, email, password):
        return self.client.post('/login', data=dict(
            email=email,
            password=password
        ), follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_login_page_loads(self):
        """Test that the login page loads successfully."""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Provider Portal', response.data)

    def test_successful_login(self):
        """Test login with correct credentials."""
        response = self.login('provider@example.com', 'password123')
        self.assertIn(b'Enhanced medical intelligence', response.data)
        self.assertIn(b'Logout', response.data)

    def test_failed_login(self):
        """Test login with incorrect credentials."""
        response = self.login('provider@example.com', 'wrongpassword')
        self.assertIn(b'Login Unsuccessful', response.data)

    def test_protected_index(self):
        """Test that index page redirects to login when not authenticated."""
        response = self.client.get('/', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)

    def test_authenticated_index(self):
        """Test that index page loads for authenticated user."""
        self.login('provider@example.com', 'password123')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Medical Bills', response.data)

    def test_logout(self):
        """Test logout functionality."""
        self.login('provider@example.com', 'password123')
        response = self.logout()
        self.assertIn(b'Please sign in', response.data)
        
        # Verify index is protected again
        response = self.client.get('/', follow_redirects=False)
        self.assertEqual(response.status_code, 302)

    def test_404_page(self):
        """Test that a non-existent page returns a 404 error."""
        response = self.client.get('/non-existent-page')
        self.assertEqual(response.status_code, 404)
        self.assertIn(b'404', response.data)

if __name__ == '__main__':
    unittest.main()
