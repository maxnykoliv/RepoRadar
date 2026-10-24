from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import Favorite

User = get_user_model()

REPO = {
    "repo_id": 45717250,
    "full_name": "encode/django-rest-framework",
    "html_url": "https://github.com/encode/django-rest-framework",
    "description": "Web APIs for Django.",
    "stargazers_count": 28000,
    "forks_count": 6800,
    "language": "Python",
}


class RegisterTests(APITestCase):
    url = "/api/auth/register/"

    def register(self, **overrides):
        payload = {"username": "alice", "email": "alice@example.com", "password": "s3cure-Passw0rd"}
        return self.client.post(self.url, payload | overrides, format="json")

    def test_register_then_login(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("password", response.json())

        response = self.client.post(
            "/api/auth/login/",
            {"username": "alice", "password": "s3cure-Passw0rd"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        self.assertIn("refresh", response.json())

    def test_password_is_hashed(self):
        self.register()
        user = User.objects.get(username="alice")
        self.assertNotEqual(user.password, "s3cure-Passw0rd")
        self.assertTrue(user.check_password("s3cure-Passw0rd"))

    def test_duplicate_username_rejected(self):
        self.register()
        response = self.register(email="other@example.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json())

    def test_duplicate_email_rejected_case_insensitively(self):
        self.register()
        response = self.register(username="alice2", email="ALICE@example.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json())

    def test_email_is_required(self):
        response = self.client.post(
            self.url, {"username": "alice", "password": "s3cure-Passw0rd"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_weak_passwords_rejected(self):
        for password in ("12345678", "password", "alice1234"):
            with self.subTest(password=password):
                response = self.register(password=password)
                self.assertEqual(response.status_code, 400)
                self.assertIn("password", response.json())


class FavoriteTests(APITestCase):
    url = "/api/favorites/"

    def setUp(self):
        self.alice = User.objects.create_user("alice", "alice@example.com", "pw-alice-123")
        self.bob = User.objects.create_user("bob", "bob@example.com", "pw-bob-123")
        self.client.force_authenticate(self.alice)

    def add(self, **overrides):
        return self.client.post(self.url, REPO | overrides, format="json")

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.add().status_code, 401)
        self.assertEqual(self.client.delete(f"{self.url}1/").status_code, 401)

    def test_add_and_list(self):
        response = self.add()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["repo_id"], REPO["repo_id"])
        self.assertEqual(body["stargazers_count"], 28000)
        self.assertEqual(body["language"], "Python")

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([f["full_name"] for f in response.json()], [REPO["full_name"]])

    def test_null_description_and_language_from_github_are_accepted(self):
        response = self.add(description=None, language=None)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["description"], "")
        self.assertEqual(response.json()["language"], "")

    def test_duplicate_returns_conflict(self):
        self.add()
        response = self.add()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Favorite.objects.filter(user=self.alice).count(), 1)

    def test_same_repo_can_be_saved_by_different_users(self):
        self.add()
        self.client.force_authenticate(self.bob)
        self.assertEqual(self.add().status_code, 201)

    def test_user_only_sees_own_favorites(self):
        self.add()
        self.client.force_authenticate(self.bob)
        self.assertEqual(self.client.get(self.url).json(), [])

    def test_delete(self):
        self.add()
        response = self.client.delete(f"{self.url}{REPO['repo_id']}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Favorite.objects.exists())

    def test_delete_missing_returns_404(self):
        self.assertEqual(self.client.delete(f"{self.url}999/").status_code, 404)

    def test_cannot_delete_another_users_favorite(self):
        self.add()
        self.client.force_authenticate(self.bob)
        response = self.client.delete(f"{self.url}{REPO['repo_id']}/")
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Favorite.objects.filter(user=self.alice).exists())

    def test_validation(self):
        cases = {
            "repo_id": 0,
            "html_url": "https://evil.example.com/a/b",
            "full_name": "",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                response = self.add(**{field: value})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())

    def test_user_field_cannot_be_spoofed(self):
        self.add(user=self.bob.pk)
        self.assertEqual(Favorite.objects.get().user, self.alice)
